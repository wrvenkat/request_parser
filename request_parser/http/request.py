import copy
import re
import warnings
from io import BytesIO
from itertools import chain
#from urllib.parse import quote, urlencode, urljoin, urlsplit
from urllib import quote, urlencode
    #urljoin, urlsplit

from request_parser.conf.settings import Settings as settings
from request_parser.exceptions.exceptions import (
    ImproperlyConfigured, RequestDataTooBig,
)
from request_parser.files import uploadhandler
from request_parser.http.multipartparser import MultiPartParser, MultiPartParserError, parse_header
from request_parser.utils.datastructures import ImmutableList, MultiValueDict, ImmutableMultiValueDict
from request_parser.utils.encoding import escape_uri_path, iri_to_uri
from request_parser.utils.http import is_same_domain, limited_parse_qsl
from request_parser.http.multipartparser import LazyStream
from request_parser.utils.http import _urlparse as urlparse
from constants import MetaDict

from six import reraise as raise_

RAISE_ERROR = object()
#validates a given string for a format of the form host:port
host_validation_re = re.compile(r"^([a-z0-9.-]+|\[[a-f0-9]*:[a-f0-9\.:]+\])(:\d+)?$")


class UnreadablePostError(IOError):
    pass

class InvalidHttpRequest(Exception):
    """The provided stream is not a request"""

    def __init__(self, message, code=None, params=None):
        super(InvalidHttpRequest, self).__init__(message, code, params)

class RawPostDataException(Exception):
    """
    You cannot access raw_post_data from a request that has
    multipart/* POST data if it has been accessed via POST,
    FILES, etc..
    """
    pass

class NoHostFoundException(Exception):
    """
    Raised when no HOST header is not present in the request.
    """
    pass

class HttpRequest:
    """A basic HTTP request."""

    # The encoding used in GET/POST dicts. None means use default setting.
    _encoding = settings.DEFAULT_CHARSET
    _upload_handlers = []

    def __init__(self, request_stream):
        self._stream = request_stream
        self.request_stream = None

        #read status flags
        self._read_started = False

        #Parsing status flags
        self._parsing_started = False
        self._body_parsing_started = False

        self.GET = QueryDict(mutable=True)
        self.POST = QueryDict(mutable=True)
        self.META = {}
        self.FILES = MultiValueDict()

        #represents a set of properties of an HTTP request
        #that are essential for quick info gathering
        #and those that should be easily changed
        self.method = None
        self.scheme = ''
        self.host = ''
        self.port = ''
        self.path = ''
        self.path_info = ''
        self.protocol_info = ''
        self.content_type = None
        self.content_params = None
        
        self.parse_request_header()

    def __repr__(self):
        if self.method is None or not self.get_full_path():
            return '<%s>' % self.__class__.__name__
        return '<%s: %s %r>' % (self.__class__.__name__, self.method, self.get_full_path())
    
    def get_method(self):
        return self.method

    def get_scheme(self):
        return self.scheme

    def get_host(self):
        return self.host
    
    def get_port(self):
        return str(self.port)

    def get_full_path(self, force_append_slash=False):
        return self._get_full_path(self.path, force_append_slash)

    #QUESTION: What is this used for?
    def get_full_path_info(self, force_append_slash=False):
        return self._get_full_path(self.path_info, force_append_slash)

    def _get_full_path(self, path, force_append_slash):
        """
        Returns the path of a request.
        """
        # RFC 3986 requires query string arguments to be in the ASCII range.
        # Rather than crash if this doesn't happen, we encode defensively.
        return '%s%s%s' % (
            #add a '/' if force_append_slash is true and the path doesn't end with '/'
            escape_uri_path(path),            
            '/' if force_append_slash and not path.endswith('/') else '',
            ('?' + iri_to_uri(self.META.get(MetaDict.ReqLine.QUERY_STRING, ''))) if self.META.get(MetaDict.ReqLine.QUERY_STRING, '') else ''
        )

    def get_raw_uri(self):
        """
        Return an absolute URI from variables available in this request.
        """
        return '{scheme}://{host}{path}'.format(
            scheme=self.scheme,
            host=self.host,
            path=self.get_full_path(),
        )

    def get_protocol_info(self):
        return self.scheme

    def _current_scheme_host(self):
        return '{}://{}'.format(self.scheme, self.host)

    def is_secure(self):
        return self.scheme == 'https'

    def is_ajax(self):
        if 'XMLHttpRequest' in self.META[MetaDict.Info.REQ_HEADERS]:
            return True
        return False

    @property
    def encoding(self):
        return self._encoding

    @encoding.setter
    def encoding(self, val):
        """
        Set the encoding used for GET/POST accesses. If the GET or POST
        dictionary has already been created, remove and recreate it on the
        next access (so that it is decoded correctly).
        """
        #QUESTION: Need to check when the GET/POST dictonary is redone
        self._encoding = val
        if hasattr(self, 'GET'):
            del self.GET
        if hasattr(self, '_post'):
            del self._post

    def _initialize_handlers(self):
        """
        Set the _upload_handlers to an array of upload handlers loaded from
        settings.FILE_UPLOAD_HANDLERS
        """
        self._upload_handlers = [uploadhandler.load_handler(handler, self)
                                 for handler in settings.FILE_UPLOAD_HANDLERS]

    @property
    def upload_handlers(self):
        if not self._upload_handlers:
            # If there are no upload handlers defined, initialize them from settings.
            self._initialize_handlers()
        return self._upload_handlers

    @upload_handlers.setter
    def upload_handlers(self, upload_handlers):
        if hasattr(self, '_files'):
            raise AttributeError("You cannot set the upload handlers after the upload has been processed.")
        self._upload_handlers = upload_handlers

    def parse(self):
        """
        Entry point for the parsing a whole HTTP Request.

        Accepts a stream that represents the request_stream
        """
        self.parse_request_header()
        self.parse_request_body()

    def _parse_file_upload(self, META, post_data):
        """Return a tuple of (POST QueryDict, FILES MultiValueDict)."""
        parser = MultiPartParser(META, post_data, self.upload_handlers, self.encoding)
        self._body_parsing_started = True
        return parser.parse()
    
    def body(self):
        """
        Return body as a raw byte stream.
        """
        if self._parsing_started and not self._body_parsing_started and not hasattr(self, '_body'):
            # Limit the maximum request data size that will be handled in-memory.
            #TODO: Figure out a way to do BufferedReading when in-memory body parsing is not possible
            #QUESTION: How/where is this used - is the self.read() used based on this?
            if (settings.DATA_UPLOAD_MAX_MEMORY_SIZE is not None and
                    int(self.META.get('CONTENT_LENGTH') or 0) > settings.DATA_UPLOAD_MAX_MEMORY_SIZE):
                raise RequestDataTooBig('Request body exceeded settings.DATA_UPLOAD_MAX_MEMORY_SIZE.')

            try:
                #At this point, remember that, self.request_stream points to the start of the body
                self._body = self.request_stream.read()
            except IOError as e:
                raise_(UnreadablePostError(*e.args), e)
                #raise UnreadablePostError(*e.args) from e
        elif self._body_parsing_started:
            raise RawPostDataException("You cannot access body after reading from request's data stream")
        elif not self._parsing_started:
            self.parse_request_header()
            return self.body()
        return self._body

    def parse_request_header(self):
        """
        Parse the request headers and populate the META dictionary.
        """
        #if parsing has already started, then simply return
        if self._parsing_started:
            return

        #create a LazyStream out of the _stream
        if self._stream is None:
            self._stream = BytesIO()
        request_header_stream = LazyStream(self._stream)
        request_header = ''

        #read until we find a '\r\n\r\n' sequence
        request_header_end = -1
        while request_header_end == -1:
            chunk = request_header_stream.read(settings.MAX_HEADER_SIZE)
            self._parsing_started = True
            if not chunk:
                break
            request_header_end = chunk.find(b'\r\n\r\n')
            if request_header_end != -1:
                request_header += chunk[:request_header_end]
            else:
                request_header += chunk
        request_header+= b'\r\n'

        #sanity check
        if request_header_end == -1:
            raise InvalidHttpRequest("Invalid HTTP request.", 400, '')
        
        #account for '\r\n\r\n'
        request_header_end += 4
        #put back anything starting from the request body
        #back onto the stream
        request_header_stream.unget(chunk[request_header_end:])

        #parse the request header
        request_line, request_headers = parse_request_headers(request_header)
        meta_dict = parse_request_line(request_line)

        #populate the properties and META info
        host = ''
        port = None
        #if the request is an HTTP_PROXY request
        if meta_dict[MetaDict.ReqLine.DOMAIN]:
            host = meta_dict[MetaDict.ReqLine.DOMAIN]
        else:
            if 'Host' in request_headers:
                host = request_headers['Host']
                del request_headers['Host']
            else:
                raise NoHostFoundException("No HOST header found in the HTTP request")
        
        #scheme
        if meta_dict[MetaDict.ReqLine.SCHEME]:
            self.scheme = meta_dict[MetaDict.ReqLine.SCHEME].lower()
        else:
            self.scheme = 'UNKNOWN'

        #populate the server host and port
        host, port = split_domain_port(host)
        self.host = host
        if not port:
            if meta_dict[MetaDict.ReqLine.SCHEME].lower() == 'https':
                port = 443
            elif meta_dict[MetaDict.ReqLine.SCHEME].lower() == 'http':
                port = 80
            else:
                #invalid port no.
                port = 65536
        self.port = port

        self.method = meta_dict[MetaDict.ReqLine.METHOD]
        self.path = meta_dict[MetaDict.ReqLine.PATH]
        self.protocol_info = meta_dict[MetaDict.ReqLine.PROTO_INFO]        
        self.content_type = parse_header(request_headers.get('Content-Type'))[0]        
        self.META[MetaDict.Info.QUERY_STRING] = meta_dict[MetaDict.ReqLine.QUERY_STRING]
        self.GET = QueryDict(self.META[MetaDict.ReqLine.QUERY_STRING]) if self.META[MetaDict.ReqLine.QUERY_STRING] else QueryDict(mutable=True)
        #Add a immutable version of request_headers dictionary into META dictionary
        self.META[MetaDict.Info.REQ_HEADERS] = ImmutableMultiValueDict(request_headers)

        #complete the call by assigning the start of body to the request body start
        self.request_stream = request_header_stream

    def _mark_post_parse_error(self):
        self._post = QueryDict()
        self._files = MultiValueDict()

    def parse_request_body(self):
        """
        Parse request body according to the content-type if there's a body.        
        """

        #sanity check for a duplicate call
        if self._body_parsing_started:
            return

        #if header not parsed already
        #if parse_request_body is called, then it means
        #that we're retaining the request header data but
        #reparsing only the body
        if not self._parsing_started:
            self._mark_post_parse_error()
            return

        body_stream = self.request_stream
        data = body_stream.read(1)

        #check if the body is empty
        if not data:
            self._post, self._files = QueryDict(encoding=self._encoding), MultiValueDict()
            return
        body_stream.unget(data)

        if self.content_type == 'multipart/form-data':      
            try:
                #returns POST QueryDict and MultiValueDict for _files
                self._post, self._files = self._parse_file_upload(self.META.get(MetaDict.Info.REQ_HEADERS), body_stream)
            except MultiPartParserError:
                # An error occurred while parsing POST data. Since when
                # formatting the error the request handler might access
                # self.POST, set self._post and self._file to prevent
                # attempts to parse POST data again.
                self._mark_post_parse_error()
                raise
        elif self.content_type == 'application/x-www-form-urlencoded':
            #if the content-type is of form-urlencoded, then all we need to do is to parse the body
            #as a key-value pair. This gives our _post and an empty _files of MultiValueDict
            self._post, self._files = QueryDict(self.body(), encoding=self._encoding), MultiValueDict()
        #for any other CONTENT_TYPE, an empty QueryDict for _post and empty MultiValueDict for _files
        else:
            self._post, self._files = QueryDict(encoding=self._encoding), MultiValueDict()
        
        self.POST = self._post
        self.FILES = self._files                
        return

    def close(self):
        if hasattr(self, '_files'):
            for f in chain.from_iterable(l[1] for l in self._files.lists()):
                f.close()

    # File-like and iterator interface.
    #
    # Expects self._stream to be set to an appropriate source of bytes by
    # a corresponding request subclass (e.g. WSGIRequest).
    # Also when request data has already been read by request.POST or
    # request.body, self._stream points to a BytesIO instance
    # containing that data.

    def read(self, *args, **kwargs):
        self._read_started = True
        try:
            return self._stream.read(*args, **kwargs)
        except IOError as e:
            raise_(UnreadablePostError(*e.args), e)

    def readline(self, *args, **kwargs):
        self._read_started = True
        try:
            return self._stream.readline(*args, **kwargs)
        except IOError as e:
            #raise UnreadablePostError(*e.args) from e
            raise_(UnreadablePostError(*e.args), e)

    def __iter__(self):
        return iter(self.readline, b'')

    def xreadlines(self):
        #warnings.warn(
        #    'HttpRequest.xreadlines() is deprecated in favor of iterating the '
        #    'request.', RemovedInDjango30Warning, stacklevel=2,
        #)
        for xreadline_ in self:
            yield xreadline_
        #yield from self

    #QUESTION: Why is this being returned here?
    #I don't understand - Candidate for removal.
    def readlines(self):
        return list(self)

class QueryDict(MultiValueDict):
    """
    A specialized MultiValueDict which represents a query string.

    A QueryDict can be used to represent GET or POST data. It subclasses
    MultiValueDict since keys in such data can be repeated, for instance
    in the data from a form with a <select multiple> field.

    By default QueryDicts are immutable, though the copy() method
    will always return a mutable copy.

    Both keys and values set on this class are converted from the given encoding
    (DEFAULT_CHARSET by default) to str.
    """

    # These are both reset in __init__, but is specified here at the class
    # level so that unpickling will have valid values
    _mutable = True
    _encoding = None

    def __init__(self, query_string=None, mutable=False, encoding=None):
        super(QueryDict, self).__init__()
        self.encoding = encoding or settings.DEFAULT_CHARSET
        query_string = query_string or ''
        parse_qsl_kwargs = {
            'keep_blank_values': True,
            'fields_limit': settings.DATA_UPLOAD_MAX_NUMBER_FIELDS,
            'encoding': self.encoding,
        }
        
        #TODO: Convert query_string to bytes - why did I put this?
        #QUESTION: Need to call urlparse on the query_string before it's being passed on to limited_parse_qsl?

        if isinstance(query_string, bytes):
            # query_string normally contains URL-encoded data, a subset of ASCII.
            try:
                query_string = query_string.decode(self.encoding)
            except UnicodeDecodeError:
                # ... but some user agents are misbehaving :-(
                query_string = query_string.decode('iso-8859-1')
        for key, value in limited_parse_qsl(query_string, **parse_qsl_kwargs):
            self.appendlist(key, value)
        self._mutable = mutable

    @classmethod
    def fromkeys(cls, iterable, value='', mutable=False, encoding=None):
        """
        Return a new QueryDict with keys (may be repeated) from an iterable and
        values from value.
        """
        q = cls('', mutable=True, encoding=encoding)
        for key in iterable:
            q.appendlist(key, value)
        if not mutable:
            q._mutable = False
        return q

    @property
    def encoding(self):
        if self._encoding is None:
            self._encoding = settings.DEFAULT_CHARSET
        return self._encoding

    @encoding.setter
    def encoding(self, value):
        self._encoding = value

    def _assert_mutable(self):
        if not self._mutable:
            raise AttributeError("This QueryDict instance is immutable")

    def __setitem__(self, key, value):
        self._assert_mutable()
        key = bytes_to_text(key, self.encoding)
        value = bytes_to_text(value, self.encoding)
        super(QueryDict, self).__setitem__(key, value)

    def __delitem__(self, key):
        self._assert_mutable()
        super(QueryDict, self).__delitem__(key)

    def __copy__(self):
        result = self.__class__('', mutable=True, encoding=self.encoding)
        for key, value in self.lists():
            result.setlist(key, value)
        return result

    def __deepcopy__(self, memo):
        result = self.__class__('', mutable=True, encoding=self.encoding)
        memo[id(self)] = result
        for key, value in self.lists():
            result.setlist(copy.deepcopy(key, memo), copy.deepcopy(value, memo))
        return result

    def setlist(self, key, list_):
        self._assert_mutable()
        key = bytes_to_text(key, self.encoding)
        list_ = [bytes_to_text(elt, self.encoding) for elt in list_]
        super(QueryDict, self).setlist(key, list_)

    def setlistdefault(self, key, default_list=None):
        self._assert_mutable()
        return super(QueryDict, self).setlistdefault(key, default_list)

    def appendlist(self, key, value):
        self._assert_mutable()
        key = bytes_to_text(key, self.encoding)
        value = bytes_to_text(value, self.encoding)
        super(QueryDict, self).appendlist(key, value)

    def pop(self, key, *args):
        self._assert_mutable()
        return super(QueryDict, self).pop(key, *args)

    def popitem(self):
        self._assert_mutable()
        return super(QueryDict, self).popitem()

    def clear(self):
        self._assert_mutable()
        super(QueryDict, self).clear()

    def setdefault(self, key, default=None):
        self._assert_mutable()
        key = bytes_to_text(key, self.encoding)
        default = bytes_to_text(default, self.encoding)
        return super(QueryDict, self).setdefault(key, default)

    def copy(self):
        """Return a mutable copy of this object."""
        return self.__deepcopy__({})

    def urlencode(self, safe=None):
        """
        Return an encoded string of all query string arguments.

        `safe` specifies characters which don't require quoting, for example::

            >>> q = QueryDict(mutable=True)
            >>> q['next'] = '/a&b/'
            >>> q.urlencode()
            'next=%2Fa%26b%2F'
            >>> q.urlencode(safe='/')
            'next=/a%26b/'
        """
        output = []
        if safe:
            safe = safe.encode(self.encoding)

            def encode(k, v):
                return '%s=%s' % ((quote(k, safe), quote(v, safe)))
        else:
            def encode(k, v):
                return urlencode({k: v})
        for k, list_ in self.lists():
            output.extend(
                encode(k.encode(self.encoding), str(v).encode(self.encoding))
                for v in list_
            )
        return '&'.join(output)

# It's neither necessary nor appropriate to use
# django.utils.encoding.force_text for parsing URLs and form inputs. Thus,
# this slightly more restricted function, used by QueryDict.
def bytes_to_text(s, encoding):
    """
    Convert bytes objects to strings, using the given encoding. Illegally
    encoded input characters are replaced with Unicode "unknown" codepoint
    (\ufffd).

    Return any non-bytes objects without change.
    """
    if isinstance(s, bytes):
        #return str(s, encoding, 'replace')
        return str(s).encode(encoding=encoding, errors='replace')
    else:
        return s

def split_domain_port(host):
    """
    Return a (domain, port) tuple from a given host.

    Returned domain is lowercased. If the host is invalid, the domain will be
    empty.
    """
    host = host.lower()

    if not host_validation_re.match(host):
        return '', ''

    if host[-1] == ']':
        # It's an IPv6 address without a port.
        return host, ''
    bits = host.rsplit(':', 1)
    domain, port = bits if len(bits) == 2 else (bits[0], '')
    # Remove a trailing dot (if present) from the domain.
    domain = domain[:-1] if domain.endswith('.') else domain
    return domain, port

def parse_request_headers(request_header_stream):
    """
    Parse the request header's individual headers into key, value-list
    pairs.

    Returns the request line and a mutable key-value pair headers dictionary.
    """
    request_line = ''
    request_headers = {}
    start = 0

    end = request_header_stream.find(b'\r\n', 1)
    if end != -1:
        request_line = request_header_stream[start:end]
    else:
        raise InvalidHttpRequest("Invalid request.")
    end+=2
    request_header_stream = request_header_stream[end:]
    start = 0
    
    #iterate through each header line
    end = request_header_stream.find(b'\r\n', 1)
    while end != -1:
        request_header = request_header_stream[start:end]
        end += 2
        request_header_stream = request_header_stream[end:]
        start = 0

        #parse the request header
        end_index = request_header.find(b':')
        if end_index != -1:
            header =  request_header[:end_index]
            header = header.encode('ascii','')
            value = request_header[end_index+1:]
            value = value.strip()
            value = value.encode('ascii','')
            if header in request_headers:
                request_headers[header].append(value)
            else:
                request_headers[header] = list()
                request_headers[header].append(value)
        else:
            raise InvalidHttpRequest("Invalid request header: {}".format(header))
        end = request_header_stream.find(b'\r\n', 1)
    
    #sanity check
    if len(request_headers) == 0:
        raise InvalidHttpRequest("Invalid request.")
    
    #construct an immutable version of MultiValueDict for the request headers
    request_headers = MultiValueDict(request_headers)
    
    return request_line, request_headers

def parse_request_line(request_line=''):
    """
    Parse the request line in an HTTP/HTTP Proxy request and return a dictionary with 8 entries:
    <METHOD> <SCHEME>://<DOMAIN>/<PATH>;<PARAMS>?<QUERY_STRING>#<FRAGMENT> <PROTOCOL_INFO>
    """
    _splits = request_line.split(' ')

    if len(_splits) > 3:
        raise InvalidHttpRequest("Invalid request line.", 400)
    method, uri, protocol_version = _splits

    if not method or not uri or not protocol_version:
        raise InvalidHttpRequest("Invalid request line.", 400)
    
    request_uri_result = urlparse(uri)
    request_line_result = {}
    request_line_result[MetaDict.ReqLine.SCHEME] = request_uri_result[0]
    request_line_result[MetaDict.ReqLine.DOMAIN] = request_uri_result[1]
    request_line_result[MetaDict.ReqLine.PATH] = request_uri_result[2]
    request_line_result[MetaDict.ReqLine.PARAMS] = request_uri_result[3]
    request_line_result[MetaDict.ReqLine.QUERY_STRING] = request_uri_result[4]
    request_line_result[MetaDict.ReqLine.FRAGMENT] = request_uri_result[5]
    request_line_result[MetaDict.ReqLine.METHOD] = method
    request_line_result[MetaDict.ReqLine.PROTO_INFO] = protocol_version

    return request_line_result