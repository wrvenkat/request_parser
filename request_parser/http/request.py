import copy
import re
import warnings
from io import BytesIO
from itertools import chain
from urllib.parse import quote, urlencode
    #urljoin, urlsplit

from request_parser.conf.settings import Settings
from request_parser.exceptions.exceptions import (
    ImproperlyConfigured, RequestDataTooBig,
)
from request_parser.files import uploadhandler
from request_parser.http.multipartparser import MultiPartParser, MultiPartParserError, parse_header, LazyStream
from request_parser.utils.datastructures import ImmutableList, MultiValueDict, ImmutableMultiValueDict
from request_parser.utils.encoding import escape_uri_path, iri_to_uri, uri_to_iri
from request_parser.utils.http import is_same_domain, limited_parse_qsl, _urlparse as urlparse
from .constants import MetaDict

RAISE_ERROR = object()
#validates a given string for a format of the form host:port
host_validation_re = re.compile(rb"^([a-z0-9.-]+|\[[a-f0-9]*:[a-f0-9\.:]+\])(:\d+)?$")

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

class RequestHeaderParseException(Exception):
    """
    You cannot parse request body wihtout first parsing request
    header.
    """
    def __init__(self, message, code=None, params=None):
        super(RequestHeaderParseException, self).__init__(message, code, params)

class NoHostFoundException(Exception):
    """
    Raised when no HOST header is not present in the request.
    """
    pass

class HttpRequest(object,):
    """A basic HTTP request."""

    def __init__(self, request_stream=None, settings=None):
        self._stream = request_stream
        #create a LazyStream out of the _stream
        if self._stream is None:
            self._stream = BytesIO()
        self._stream = LazyStream(self._stream)

        #take care of settings to use default settings
        if settings:
            self.settings = settings
        else:
            self.settings = Settings.default()        

        #Parsing status flags
        self._request_header_parsed = False
        self._request_body_parsed = False

        # POST dictionary in a multipart/form-data is of the form
        # POST['key'] = { 'data'              : data,
        #                 'content-type'      : type,
        #                 'transfer-encoding' : val,
        #                 'content-type-extra': {}
        #               }
        self.POST = QueryDict(self.settings, mutable=True)
        self.FILES = MultiValueDict()

        self._re_init()

    def _re_init(self):
        """
        Helper method to init/reinit an object.
        """
        
        self.GET = QueryDict(self.settings, mutable=True)
        self.META = {}

        #represents a set of properties of an HTTP request
        #that are essential for quick info gathering
        #and those that should be easily changed
        self.method = None
        self.scheme = None
        self.host = None
        self.port = None
        self.path = None        
        self.protocol_info = None
        self.content_type = None
        self.content_params = None

    def __repr__(self):
        if self.method is None or not self.get_full_path():
            return '<%s>' % self.__class__.__name__
        return '<%s: %s %r>' % (self.__class__.__name__, self.method, self.get_full_path())
    
    def get_path(self):
        if self.path:
            return self.path
        else:
            return b''

    def get_method(self):
        return self.method

    def get_scheme(self):
        return self.scheme
    
    def set_scheme(self, scheme):
        if scheme is not None and len(scheme) > 0:
            self.scheme = scheme

    def get_host(self):
        return self.host
    
    def get_port(self):
        return self.port

    def get_full_path(self, force_append_slash=False, raw=False):
        if raw:
            _path = self._get_full_path(self.get_path(), force_append_slash)#.decode('utf-8')
            return uri_to_iri(_path)            
        else:
            return self._get_full_path(self.get_path(), force_append_slash)

    def _get_full_path(self, path, force_append_slash):
        """
        Returns the path of a request.
        """
        # RFC 3986 requires query string arguments to be in the ASCII range.
        # Rather than crash if this doesn't happen, we encode defensively.
        #return '%s%s%s' % (
            #add a '/' if force_append_slash is true and the path doesn't end with '/'
            #also, since anything in self.path is assumed to be safe and final, we don't perform any further encoding
        part1 = escape_uri_path(path, encode_percent=False)
        part2 = b'/' if force_append_slash and not path.endswith(b'/') else b''
        x = iri_to_uri(self.META.get(MetaDict.ReqLine.QUERY_STRING, b''))
        part3 = b''.join([b'?', x.encode('ascii')]) if self.META.get(MetaDict.ReqLine.QUERY_STRING, b'') else b''
        #)
        part1_1 = b''
        if isinstance(part1, str):
            part1_1 = part1.encode('ascii')
        else:
            part1_1 = part1
        y = b''.join([part1_1, part2, part3])
        return y

    def get_uri(self, raw=False):
        """
        Return a safe, absolute URI if raw is false from meta data available in this request. Return the raw URI otherwise
        """
        scheme=self.scheme
        host=self.host
        path = self.get_full_path(raw=raw)
        orig = '{scheme}://{host}{path}'.format(
            scheme=self.scheme,
            host=self.host,
            path = self.get_full_path(raw=True) if raw else self.get_full_path()
        )
        new = b''.join([scheme,b'://',host, path])
        if raw:
            return new.decode('utf-8')
        else:
            return new

    def get_protocol_info(self):
        return self.protocol_info

    def _current_scheme_host(self):
        return '{}://{}'.format(self.scheme, self.host)

    def is_secure(self):
        return self.scheme == 'https'

    def is_ajax(self):
        if 'XMLHttpRequest' in self.META[MetaDict.Info.REQ_HEADERS]:
            return True
        return False

    def is_plain_text(self):
        """
        Returns true if Content-Type is text/plain
        """
        #TODO: Make it so that the content-type can be changed in the
        #META dict
        #req_headers = self.META[MetaDict.Info.REQ_HEADERS]
        #content_type = req_headers.get('Content-Type')
        return self.content_type == 'text/plain'

    @property
    def encoding(self):
        return self.settings.DEFAULT_CHARSET

    @encoding.setter
    def encoding(self, val):
        """
        Set the encoding used for GET/POST accesses. If the GET or POST
        dictionary has already been created, remove and recreate it on the
        next access (so that it is decoded correctly).
        """
        #DONE: Need to check when the GET/POST dictonary is redone?
        #ANSWER: They're redone whenever parse_request_header and parse_request_body
        #are called
        self.settings.DEFAULT_CHARSET = val
        if hasattr(self, 'GET'):
            del self.GET
        if hasattr(self, '_post'):
            del self._post
        if hasattr(self, '_body'):
            del self._body
    
    @property
    def stream(self):
        if hasattr(self, '_stream') and not self._stream:
            return self._stream
        return None

    @stream.setter
    def stream(self, val):
        """
        Set the main request stream. This includes the stream for both header and body.

        Setting a new stream resets the parse META data for request header and parse
        status flags and deleting any META data. This is because, by setting a new stream, 
        the intent is to restart parsing (at least reparse the header).

        This reset doesn't reset POST, FILES and _body. However, calling parse_request_body() is
        possible.
        """
        self._stream = val
        #create a LazyStream out of the _stream
        if self._stream is None:
            self._stream = BytesIO()
        self._stream = LazyStream(self._stream)

        #reset the header META data
        self._reset_header_meta_data()
        #reset parse status flags
        self._request_header_parsed = False
        self._request_body_parsed = False
    
    @property
    def body_stream(self):
        if hasattr(self, '_stream') and not self._stream:
            return self._stream
        return None

    @body_stream.setter
    def body_stream(self, val):
        """
        Set the request stream. This is specific for body.

        Setting a new stream for body signals the intent to call parse_request_body()
        with the current META data/request headers. So, only the body parsing flags 
        and META data are reset.
        """
        self._stream = val
        #create a LazyStream out of the _stream
        if self._stream is None:
            self._stream = BytesIO()
        self._stream = LazyStream(self._stream)

        #reset the POST, FILEs and _body
        if hasattr(self, 'POST'):
            del self.POST
        if hasattr(self, 'FILES'):
            del self.FILES
        if hasattr(self, '_body'):
            del self._body
        
        #re-init POST and FILES
        self.POST = QueryDict(self.settings, mutable=True)
        self.FILES = MultiValueDict()

        #reset the body parsing flag
        self._request_body_parsed = False

    def _reset_header_meta_data(self):
        """
        Remove the listed below META data for a parser instance.
        Note that the POST, FILES and _body are exempt because they're context
        dependant.

        Called by stream.setter to reset parser status.
        """
        if hasattr(self, 'GET'):
            del self.GET
        if hasattr(self, 'META'):
            del self.META
            
        if hasattr(self, 'method'):
            del self.method
        if hasattr(self, 'scheme'):
            del self.scheme
        if hasattr(self, 'host'):
            del self.host
        if hasattr(self, 'port'):
            del self.port
        if hasattr(self, 'path'):
            del self.path
        if hasattr(self, 'protocol_info'):
            del self.protocol_info
        if hasattr(self, 'content_type'):
            del self.content_type
        if hasattr(self, 'content_params'):
            del self.content_params
        
        #re-init the object
        self._re_init()

    def set_path(self, path, encode_safely=True):
        """
        Set a path where path is a UNICODE string.
        Before setting to self.path, it is safely encoded.
        encode_safely - Flag that percent encodes the path if there are UTF-8 characters.
        """        
        if encode_safely:
            #we want the converted IRI string to be safely encoded but not
            #the % in it
            path = escape_uri_path(iri_to_uri(path), encode_percent=False)
        self.path = path

    def _initialize_handlers(self):
        """
        Set the _upload_handlers to an array of upload handlers loaded from
        settings.FILE_UPLOAD_HANDLERS
        """
        self._upload_handlers = [uploadhandler.load_handler(handler, self)
                                 for handler in self.settings.FILE_UPLOAD_HANDLERS]

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
        parser = MultiPartParser(META, post_data, self.upload_handlers, self.settings ,self.encoding)        
        return parser.parse()
    
    def body(self):
        """
        Return body as a raw byte stream.
        """        
        #In future, the content-type check should/could be replaced with
        #a call to check any content-type who's processing is not handled and requires
        #returning it raw
        if self._request_body_parsed and (self.content_type == 'application/x-www-form-urlencoded' or self.content_type == 'multipart/form-data'):
            raise RawPostDataException("You cannot access raw body after reading from request's data stream.")
    
        elif self._request_header_parsed and not hasattr(self, '_body'):
            # Limit the maximum request data size that will be handled in-memory.
            
            #QUESTION: How/where is this used - is the self.read() used based on this?
            #ANSWER: Please see settings.py for what DATA_UPLOAD_MAX_MEMORY_SIZE is for.

            #default chunk_size is 64KB
            chunk_size = 64 * (2 ** 10)
            read_size = 0
            chunk = b''
            _body = b''
            try:                
                chunk = self.read(chunk_size)
                read_size += len(chunk)
                while read_size <= self.settings.DATA_UPLOAD_MAX_MEMORY_SIZE and\
                        chunk:
                    _body += chunk
                    chunk = self.read(chunk_size)
                    read_size += len(chunk)
            except IOError as e:
                raise UnreadablePostError(*e.args) from e
            
            if read_size > self.settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
                raise RequestDataTooBig('Request body exceeded settings.DATA_UPLOAD_MAX_MEMORY_SIZE.')
            self._body = _body
            
        elif not self._request_header_parsed:
            self.parse_request_header()
            return self.body()
        return self._body

    def parse_request_header(self):
        """
        Parse the request headers and populate the META dictionary.
        """
        #if parsing has already started, then simply return
        if self._request_header_parsed:
            return

        #create a LazyStream out of the _stream
        #if self._stream is None:
            #self._stream = BytesIO()
        #request_header_stream = LazyStream(self._stream)
        request_header_stream = self._stream
        request_header = b''
        unget_bytes = b''

        #read until we find a '\r\n\r\n' sequence
        request_header_end = -1
        while request_header_end == -1:
            chunk = request_header_stream.read(self.settings.MAX_HEADER_SIZE)            
            self._request_header_parsed = True
            if not chunk:
                break
            
            request_header += chunk
            request_header_end = request_header.find(b'\r\n\r\n')
            if request_header_end != -1:
                #account for len('\r\n\r\n')                
                unget_bytes = request_header[request_header_end+4:]
                request_header = request_header[:request_header_end]

        #sanity check
        if request_header_end == -1:
            raise InvalidHttpRequest("Invalid HTTP request.", 400, '')
        
        #put back anything starting from the request body
        #back onto the stream
        request_header_stream.unget(unget_bytes)
        request_header+= b'\r\n'

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
            if b'Host' in request_headers:
                host = request_headers[b'Host']
                del request_headers[b'Host']
            else:
                raise NoHostFoundException("No HOST header found in the HTTP request")
        
        #scheme
        if meta_dict[MetaDict.ReqLine.SCHEME]:
            self.scheme = meta_dict[MetaDict.ReqLine.SCHEME].lower()
        else:
            self.scheme = b'UNKNOWN'

        #populate the server host and port
        host, port = split_domain_port(host)
        self.host = host
        if not port:
            if meta_dict[MetaDict.ReqLine.SCHEME].lower() == b'https':
                port = 443
            elif meta_dict[MetaDict.ReqLine.SCHEME].lower() == b'http':
                port = 80
            else:
                #invalid port no.
                port = b'65536'
        self.port = port

        self.method = meta_dict[MetaDict.ReqLine.METHOD]
        self.path = meta_dict[MetaDict.ReqLine.PATH]
        self.protocol_info = meta_dict[MetaDict.ReqLine.PROTO_INFO]
        #correctly set the encoding and the content-type
        self.content_type, header_dict = parse_header(request_headers.get(b'Content-Type'))
        #sanity check for when Content-Type is not present
        if header_dict is not None:        
            for key, value in list(header_dict.items()):
                if b'charset' == key.lower():
                    self.encoding = value
                    break

        self.META[MetaDict.Info.QUERY_STRING] = meta_dict[MetaDict.ReqLine.QUERY_STRING]
        self.GET = QueryDict(self.settings, self.META[MetaDict.ReqLine.QUERY_STRING]) if self.META[MetaDict.ReqLine.QUERY_STRING] else QueryDict(self.settings, mutable=True)
        #Add a immutable version of request_headers dictionary into META dictionary
        self.META[MetaDict.Info.REQ_HEADERS] = ImmutableMultiValueDict(request_headers)

    def _mark_post_parse_error(self):
        self._post = QueryDict(self.settings)
        self._files = MultiValueDict()

    def parse_request_body(self):
        """
        Parse request body according to the content-type if there's a body.        
        """

        #sanity check for a duplicate call
        if self._request_body_parsed:
            return
        
        #initialize the upload_hanldlers
        self._initialize_handlers()

        #if header not parsed already
        #if parse_request_body is called, then it means
        #that we're retaining the request header data but
        #reparsing only the body
        if not self._request_header_parsed:
            self._mark_post_parse_error()
            raise RequestHeaderParseException("Request header not parsed.Parse request header first.")

        #body_stream = self.request_stream
        body_stream = self._stream
        data = body_stream.read(1)

        #check if the body is empty
        if not data:
            self._post, self._files = QueryDict(self.settings, encoding=self.encoding), MultiValueDict()
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
            self._post, self._files = QueryDict(self.settings, self.body(), encoding=self.encoding), MultiValueDict()
        #for any other CONTENT_TYPE, an empty QueryDict for _post and empty MultiValueDict for _files
        else:
            self._post, self._files = QueryDict(self.settings, encoding=self.encoding), MultiValueDict()
        
        #restart content-type check
        if self.content_type == 'text/plain' or self.content_type == 'text/html'\
            or self.content_type == 'application/json':
            self._body = self.body().decode(self.encoding)
        else:
            self._body = self.body().decode(self.encoding)
        
        self._request_body_parsed = True
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
        try:
            return self._stream.read(*args, **kwargs)
        except IOError as e:
            raise UnreadablePostError(*e.args) from e

    def readline(self, *args, **kwargs):
        try:
            return self._stream.readline(*args, **kwargs)
        except IOError as e:
            #raise UnreadablePostError(*e.args) from e
            raise UnreadablePostError(*e.args) from e

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

    def __init__(self, settings, query_string=None, mutable=False, encoding=None):
        super(QueryDict, self).__init__()
        self.settings = settings
        self.encoding = self.settings.DEFAULT_CHARSET
        query_string = query_string or ''
        parse_qsl_kwargs = {
            'keep_blank_values': True,
            'fields_limit': self.settings.DATA_UPLOAD_MAX_NUMBER_FIELDS,
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
    def fromkeys(cls, iterable, value=b'', mutable=False, encoding=None):
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
            self._encoding = self.settings.DEFAULT_CHARSET
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
    (\\ufffd).

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
        return b'', b''

    if host[-1] == b']':
        # It's an IPv6 address without a port.
        return host, b''
    bits = host.rsplit(b':', 1)
    domain, port = bits if len(bits) == 2 else (bits[0], b'')
    # Remove a trailing dot (if present) from the domain.
    domain = domain[:-1] if domain.endswith(b'.') else domain
    return domain, port

def parse_request_headers(request_header_stream):
    """
    Parse the request header's individual headers into key, value-list
    pairs.

    Returns the request line and a mutable key-value pair headers dictionary.
    """
    request_line = b''
    request_headers = {}
    start = 0

    end = request_header_stream.find(b'\r\n', 1)
    if end != -1:
        request_line = request_header_stream[start:end]
    else:
        raise InvalidHttpRequest("Invalid request. Request line terminated incorrectly.", 400)
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
            #header = header.encode('ascii','')
            value = request_header[end_index+1:]
            value = value.strip()
            #value = value.encode('ascii','')
            if header in request_headers:
                request_headers[header].append(value)
            else:
                request_headers[header] = list()
                request_headers[header].append(value)
        else:
            raise InvalidHttpRequest("Invalid request header: {}".format(request_header), 400)
        end = request_header_stream.find(b'\r\n', 1)
    
    #sanity check
    if len(request_headers) == 0:
        raise InvalidHttpRequest("Invalid request. No request headers.", 400)
    
    #construct an immutable version of MultiValueDict for the request headers
    request_headers = MultiValueDict(request_headers)
    
    return request_line, request_headers

def parse_request_line(request_line=b''):
    """
    Parse the request line in an HTTP/HTTP Proxy request and return a dictionary with 8 entries:
    <METHOD> <SCHEME>://<DOMAIN>/<PATH>;<PARAMS>?<QUERY_STRING>#<FRAGMENT> <PROTOCOL_INFO>
    """
    _splits = request_line.split(b' ')

    if len(_splits) != 3:
        raise InvalidHttpRequest("Invalid request line.", 400)
    method, uri, protocol_version = _splits

#    if not method or not uri or not protocol_version:
#        raise InvalidHttpRequest("Invalid request line.", 400)
    
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