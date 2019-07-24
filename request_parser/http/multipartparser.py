"""
Multi-part parsing for file uploads.

Exposes one class, ``MultiPartParser``, which feeds chunks of uploaded data to
file upload handlers for processing.
"""
import base64
import binascii
import cgi

from six import reraise as raise_from
from future.backports.urllib.parse import unquote

from request_parser.conf.settings import Settings
from request_parser.exceptions.exceptions import (
    RequestDataTooBig, TooManyFieldsSent, InputStreamExhausted
)
from request_parser.files.uploadhandler import (
    SkipFile, StopFutureHandlers, StopUpload,
)
from request_parser.utils.datastructures import MultiValueDict
from request_parser.utils.encoding import force_text
from request_parser.utils.text import unescape_entities
from request_parser.utils.datastructures import LazyStream, ChunkIter

__all__ = ('MultiPartParser', 'MultiPartParserError', 'InputStreamExhausted')

class MultiPartParserError(Exception):
    pass

RAW = "raw"
FILE = "file"
FIELD = "field"

class MultiPartParser:
    """
    A rfc2388 multipart/form-data parser.

    ``MultiValueDict.parse()`` reads the input stream in ``chunk_size`` chunks
    and returns a tuple of ``(MultiValueDict(POST), MultiValueDict(FILES))``.
    """
    def __init__(self, META, input_data, upload_handlers, settings, encoding=None):
        """
        Initialize the MultiPartParser object.

        :META:
            The standard ``META`` dictionary in Django request objects.
        :input_data:
            The raw post data, as a file-like object.
        :upload_handlers:
            A list of UploadHandler instances that perform operations on the
            uploaded data.
        :encoding:
            The encoding with which to treat the incoming data.
        """
        self.settings = settings

        # Content-Type should contain multipart and the boundary information.
        content_type = META.get('Content-Type', '')
        if not content_type.startswith('multipart/'):
            raise MultiPartParserError('Invalid Content-Type: %s' % content_type)

        # Parse the header to get the boundary to split the parts.
        content_types, opts = parse_header(content_type.encode('ascii'))
        boundary = opts.get('boundary')
        if not boundary or not cgi.valid_boundary(boundary):
            raise MultiPartParserError('Invalid boundary in multipart: %s' % boundary.decode())

        # Content-Length should contain the length of the body we are about
        # to receive.
        try:
            content_length = int(META.get('Content-Length', 0))
        except (ValueError, TypeError):
            content_length = 0

        if content_length < 0:
            # This means we shouldn't continue...raise an error.
            raise MultiPartParserError("Invalid content length: %r" % content_length)

        if isinstance(boundary, str):
            boundary = boundary.encode('ascii')
        self._boundary = boundary
        self._input_data = input_data

        # For compatibility with low-level network APIs (with 32-bit integers),
        # the chunk size should be < 2^31, but still divisible by 4.
        possible_sizes = [x.chunk_size for x in upload_handlers if x.chunk_size]
        self._chunk_size = min([2 ** 31 - 4] + possible_sizes)

        self._meta = META
        self._encoding = encoding or self.settings.DEFAULT_CHARSET
        self._content_length = content_length
        self._upload_handlers = upload_handlers

    def parse(self):
        """
        Parse the POST data and break it into a FILES MultiValueDict and a POST
        MultiValueDict.

        Return a tuple containing the POST and FILES dictionary, respectively.
        """
        from request_parser.http.request import QueryDict

        encoding = self._encoding
        handlers = self._upload_handlers

        # HTTP spec says that Content-Length >= 0 is valid
        # handling content-length == 0 before continuing
        if self._content_length == 0:
            return QueryDict(self.settings, encoding=self._encoding), MultiValueDict()

        # See if any of the handlers take care of the parsing.
        # This allows overriding everything if need be.
        for handler in handlers:
            result = handler.handle_raw_input(
                self._input_data,
                self._meta,
                self._content_length,
                self._boundary,
                self.settings,
                encoding,
            )
            # Check to see if it was handled
            if result is not None:
                #If we're returning as soon as the result is not None, then
                #it means there can be only one handler that is allowed to parse
                #body and files - technically there can be more than one but the
                #first one is picked
                return result[0], result[1]

        # Create the data structures to be used later.
        self._post = QueryDict(self.settings, mutable=True)
        self._files = MultiValueDict()

        # Instantiate the stream:
        stream = LazyStream(ChunkIter(self._input_data, self._chunk_size))

        # Whether or not to signal a file-completion at the beginning of the loop.
        old_field_name = None
        counters = [0] * len(handlers)

        # Number of bytes that have been read.
        num_bytes_read = 0
        # To count the number of keys in the request.
        num_post_keys = 0
        # To limit the amount of data read from the request.
        read_size = None

        try:
            for item_type, meta_data, field_stream in Parser(stream, self._boundary):
                if old_field_name:
                    # We run this at the beginning of the next loop
                    # since we cannot be sure a file is complete until
                    # we hit the next boundary/part of the multipart content.
                    self.handle_file_complete(old_field_name, counters)
                    old_field_name = None

                try:
                    disposition = meta_data['content-disposition'][1]
                    field_name = disposition['name'].strip()
                except (KeyError, IndexError, AttributeError):
                    continue

                transfer_encoding = meta_data.get('content-transfer-encoding')
                if transfer_encoding is not None:
                    transfer_encoding = transfer_encoding[0].strip()
                    transfer_encoding = force_text(transfer_encoding, encoding, errors='replace')
                field_name = force_text(field_name, encoding, errors='replace')

                if item_type == FIELD:
                    # Avoid storing more than DATA_UPLOAD_MAX_NUMBER_FIELDS.
                    num_post_keys += 1
                    if (self.settings.DATA_UPLOAD_MAX_NUMBER_FIELDS is not None and
                            self.settings.DATA_UPLOAD_MAX_NUMBER_FIELDS < num_post_keys):
                        raise TooManyFieldsSent(
                            'The number of GET/POST parameters exceeded '
                            'settings.DATA_UPLOAD_MAX_NUMBER_FIELDS.'
                        )

                    # Avoid reading more than DATA_UPLOAD_MAX_MEMORY_SIZE.
                    if self.settings.DATA_UPLOAD_MAX_MEMORY_SIZE is not None:
                        read_size = self.settings.DATA_UPLOAD_MAX_MEMORY_SIZE - num_bytes_read

                    # This is a post field, we can just set it in the post
                    if transfer_encoding == 'base64':
                        #read only for the remaining size
                        raw_data = field_stream.read(size=read_size)
                        num_bytes_read += len(raw_data)
                        try:
                            #decode the data read
                            data = base64.b64decode(raw_data)
                        except binascii.Error:
                            data = raw_data
                    else:
                        data = field_stream.read(size=read_size)
                        num_bytes_read += len(data)

                    # Add two here to make the check consistent with the
                    # x-www-form-urlencoded check that includes '&='.
                    #QUESTION: We can't implement buffered reading if we
                    #have only read part of a stream. Can we?
                    num_bytes_read += len(field_name) + 2
                    if (self.settings.DATA_UPLOAD_MAX_MEMORY_SIZE is not None and
                            num_bytes_read > self.settings.DATA_UPLOAD_MAX_MEMORY_SIZE):
                        raise RequestDataTooBig('Request body exceeded settings.DATA_UPLOAD_MAX_MEMORY_SIZE.')
                    
                    #force_text(data, encoding, errors='replace')
                    if transfer_encoding is None:
                        transfer_encoding = ''
                    content_type, content_type_extra = meta_data.get('content-type', ('', {}))
                    content_type = content_type.strip()
                    #print "data: "+data+"\r\ntype: "+content_type+"\r\nt.encoding: "+transfer_encoding
                    #self._post.appendlist(field_name, force_text(data, encoding, errors='replace'))
                    self._post.appendlist(field_name, {
                                                        'data' : force_text(data, encoding, errors='replace'),
                                                        'content-type' : force_text(content_type, encoding, errors='replace'),
                                                        'transfer-encoding' : transfer_encoding,
                                                        'content-type-extra': content_type_extra
                                                      }
                    )
                elif item_type == FILE:
                    # This is a file, use the handler...
                    file_name = disposition.get('filename')
                    if file_name:
                        file_name = force_text(file_name, encoding, errors='replace')
                        file_name = self.IE_sanitize(unescape_entities(file_name))
                    if not file_name:
                        continue

                    content_type, content_type_extra = meta_data.get('content-type', ('', {}))
                    content_type = content_type.strip()
                    charset = content_type_extra.get('charset')

                    try:
                        content_length = int(meta_data.get('content-length')[0])
                    except (IndexError, TypeError, ValueError):
                        content_length = None

                    counters = [0] * len(handlers)
                    try:
                        for handler in handlers:
                            try:
                                handler.new_file(
                                    field_name, file_name, content_type,
                                    content_length, charset, content_type_extra,
                                    transfer_encoding
                                )
                            #if a handler is handling a new file, it raises StopFutureHandlers
                            #to prevent others from handling it
                            except StopFutureHandlers:
                                break

                        for chunk in field_stream:
                            if transfer_encoding == 'base64':
                                # We only special-case base64 transfer encoding
                                # We should always decode base64 chunks by multiple of 4,
                                # ignoring whitespace.

                                stripped_chunk = b"".join(chunk.split())

                                remaining = len(stripped_chunk) % 4
                                while remaining != 0:
                                    over_chunk = field_stream.read(4 - remaining)
                                    stripped_chunk += b"".join(over_chunk.split())
                                    remaining = len(stripped_chunk) % 4

                                try:
                                    chunk = base64.b64decode(stripped_chunk)
                                except Exception as exc:
                                    # Since this is only a chunk, any error is an unfixable error.                                
                                    raise_from(MultiPartParserError("Could not decode base64 data."), exc)

                            for i, handler in enumerate(handlers):
                                chunk_length = len(chunk)
                                #stream data into the temp file
                                chunk = handler.receive_data_chunk(chunk, counters[i])
                                counters[i] += chunk_length

                                #None means no errors, which means we break
                                if chunk is None:
                                    # Don't continue if the chunk received by
                                    # the handler is None.
                                    break

                    #QUESTION: When does this occur?            
                    except SkipFile:
                        self._close_files()
                        # Just use up the rest of this file...
                        exhaust(field_stream)
                    else:
                        # Handle file upload completions on next iteration.
                        old_field_name = field_name
                else:
                    # If this is neither a FIELD or a FILE, just exhaust the stream.
                    exhaust(stream)
        #QUESTION: When does this occur?
        #ANSWER: This is used when one of the file handler on line 257 signals to
        #stop any more further file handline. This means any further file upload
        #request needs to be abruptly stopped.
        #See django's tests/file_uploads/uploadhandler.py for more details.
        #TODO: Repurpose this so that we can stop file upload parsing whenver needed.
        except StopUpload as e:
            self._close_files()
            if not e.connection_reset:
                exhaust(self._input_data)
        else:
            # Make sure that the request data is all fed
            exhaust(self._input_data)

        # Signal that the upload has completed.
        # any() shortcircuits if a handler's upload_complete() returns a value.

        #Perform any clean up after file upload is complete
        any(handler.upload_complete() for handler in handlers)
        self._post._mutable = False
        return self._post, self._files

    def handle_file_complete(self, old_field_name, counters):
        """
        Handle all the signaling that takes place when a file is complete.
        """
        for i, handler in enumerate(self._upload_handlers):
            file_obj = handler.file_complete(counters[i])
            if file_obj:
                # If it returns a file object, then set the files dict.
                self._files.appendlist(force_text(old_field_name, self._encoding, errors='replace'), file_obj)
                break

    #What the hell is this for?
    def IE_sanitize(self, filename):
        """Cleanup filename from Internet Explorer full paths."""
        return filename and filename[filename.rfind("\\") + 1:].strip()

    def _close_files(self):
        # Free up all file handles.
        # FIXME: this currently assumes that upload handlers store the file as 'file'
        # We should document that... (Maybe add handler.free_file to complement new_file)
        for handler in self._upload_handlers:
            if hasattr(handler, 'file'):
                handler.file.close()

class InterBoundaryIter:
    """
    A Producer that will iterate over boundaries.
    Returns a LazyStream for any inter-boundary data that is encapsulated by
    BoundaryIter.
    """
    def __init__(self, stream, boundary):
        self._stream = stream
        self._boundary = boundary

    def __iter__(self):
        return self

    #def __next__(self): <- Python 3
    def next(self): #<- Python 2.x
        #note that while the class is supposed to be handling the iteration over
        #each boundary, it's deferring it to BoundaryIter which skips over boundaries
        #as the POST body stream is parsed
        try:
            #create a new-stream from the bytes-set returned by BoundaryIter
            return LazyStream(BoundaryIter(self._stream, self._boundary))
        except InputStreamExhausted:
            raise StopIteration()

class BoundaryIter:
    """
    A Producer that is sensitive to boundaries.

    Will happily yield bytes until a boundary is found. Will yield the bytes
    before the boundary, throw away the boundary bytes themselves, and push the
    post-boundary bytes back on the stream.

    The future calls to next() after locating the boundary will raise a
    StopIteration exception.
    """

    def __init__(self, stream, boundary):
        self._stream = stream
        self._boundary = boundary
        self._done = False
        # rollback an additional six bytes because the format is like
        # this: CRLF<boundary>[--CRLF]
        self._rollback = len(boundary) + 6

        # Try to use mx fast string search if available. Otherwise
        # use Python find. Wrap the latter for consistency.
        unused_char = self._stream.read(1)
        #peek if stream is empty
        if not unused_char:
            raise InputStreamExhausted()
        #if not empty, put the read character back in the stream
        self._stream.unget(unused_char)

    def __iter__(self):
        return self

    #def __next__(self):
    def next(self):
        if self._done:
            raise StopIteration()

        stream = self._stream
        rollback = self._rollback

        bytes_read = 0
        chunks = []
        for bytes in stream:
            bytes_read += len(bytes)
            chunks.append(bytes)

            if bytes_read > rollback:
                break
            if not bytes:
                break
        else:
            self._done = True

        if not chunks:
            raise StopIteration()

        #convert the byte array into one contiguous set of bytes (or string)
        chunk = b''.join(chunks)
        boundary = self._find_boundary(chunk)

        if boundary:
            #get the indices of current inter-boundary data - end
            #get the beginning of the next inter-boundary data - next
            end, next = boundary
            #put back everything starting from next till end of POST back in the stream
            stream.unget(chunk[next:])
            #done with current inter-boundary data
            self._done = True
            #return everything from beginning to end
            return chunk[:end]
        #If no boundary is found
        else:
            # make sure we don't treat a partial boundary (and
            # its separators) as data

            #if there's no data from beginning to end - 6
            if not chunk[:-rollback]:  # and len(chunk) >= (len(self._boundary) + 6):
                # There's nothing left, we should just return and mark as done.
                self._done = True
                return chunk
            #if there is data, then put it back and return
            else:
                stream.unget(chunk[-rollback:])
                return chunk[:-rollback]

    def _find_boundary(self, data):
        """
        Find a multipart boundary in data.

        Should no boundary exist in the data, return None. Otherwise, return
        a tuple containing the indices of the following:
         * the end of current encapsulation
         * the start of the next encapsulation
        """
        index = data.find(self._boundary)
        if index < 0:
            return None
        else:
            end = index
            next = index + len(self._boundary)
            # backup over CRLF
            last = max(0, end - 1)
            if data[last:last + 1] == b'\n':
                end -= 1
            last = max(0, end - 1)
            if data[last:last + 1] == b'\r':
                end -= 1
            return end, next

def exhaust(stream_or_iterable):
    """Exhaust an iterator or stream."""
    try:
        iterator = iter(stream_or_iterable)
    except TypeError:
        iterator = ChunkIter(stream_or_iterable, 16384)

    for __ in iterator:
        pass

def parse_boundary_stream(stream, max_header_size):
    """
    Parse one and exactly one stream that's encpasulated within a boundary.
    """
    # Stream at beginning of header, look for end of header
    # and parse it if found. The header must fit within one
    # chunk.
    chunk = stream.read(max_header_size)

    # 'find' returns the top of these four bytes, so we'll
    # need to munch them later to prevent them from polluting
    # the payload.
    header_end = chunk.find(b'\r\n\r\n')

    def _parse_header(line):
        main_value_pair, params = parse_header(line)
        try:
            name, value = main_value_pair.split(':', 1)
        except ValueError:
            raise ValueError("Invalid header: %r" % line)
        return name, (value, params)

    if header_end == -1:
        # we find no header, so we just mark this fact and pass on
        # the stream verbatim
        stream.unget(chunk)
        return (RAW, {}, stream)

    header = chunk[:header_end]

    # here we place any excess chunk back onto the stream, as
    # well as throwing away the CRLFCRLF bytes from above.
    stream.unget(chunk[header_end + 4:])

    TYPE = RAW
    outdict = {}

    # Eliminate blank lines
    for line in header.split(b'\r\n'):
        # This terminology ("main value" and "dictionary of
        # parameters") is from the Python docs.
        try:
            name, (value, params) = _parse_header(line)
        except ValueError:
            continue

        if name == 'content-disposition':
            TYPE = FIELD
            if params.get('filename'):
                TYPE = FILE

        outdict[name] = value, params

    #if the stream if raw, then put it back
    #into the stream for it to be read byt the main parser
    if TYPE == RAW:
        stream.unget(chunk)

    return (TYPE, outdict, stream)

class Parser:
    """
    Parser class that parses inter-boudary data to return,
    item_type, meta_data, field_stream.
    """
    def __init__(self, stream, boundary):
        self._stream = stream
        #the actual boundary in the HTTP header is '--' shorter than the
        #separating boundary in the POST body
        self._separator = b'--' + boundary

    def __iter__(self):
        boundarystream = InterBoundaryIter(self._stream, self._separator)
        #for each sub-stream within boundaries, yield the parsed content
        #note that many sub-streams (usually) form a boundaryStream
        #And a boundaryStream is the stream of bytes between boundaries
        for sub_stream in boundarystream:
            # Iterate over each part
            #to return item_type, meta_data, field_stream
            yield parse_boundary_stream(sub_stream, 1024)

def parse_header(line):
    """
    Parse the header into a key-value.

    Input (line): bytes
    Output: str for key/name, bytes for values which will be decoded later.
    """
    plist = _parse_header_params(b';' + line)
    key = plist.pop(0).lower().decode('ascii')
    pdict = {}
    for p in plist:
        i = p.find(b'=')
        if i >= 0:
            has_encoding = False
            name = p[:i].strip().lower().decode('ascii')
            if name.endswith('*'):
                # Lang/encoding embedded in the value (like "filename*=UTF-8''file.ext")
                # http://tools.ietf.org/html/rfc2231#section-4
                name = name[:-1]
                if p.count(b"'") == 2:
                    has_encoding = True
            value = p[i + 1:].strip()
            if has_encoding:
                encoding, lang, value = value.split(b"'")                
                #will come back to bite us. Investigate -> DONE
                value = unquote(value.decode(), encoding=encoding.decode())
            if len(value) >= 2 and value[:1] == value[-1:] == b'"':
                value = value[1:-1]
                value = value.replace(b'\\\\', b'\\').replace(b'\\"', b'"')
            pdict[name] = value
    return key, pdict

def _parse_header_params(s):
    plist = []
    while s[:1] == b';':
        s = s[1:]
        end = s.find(b';')
        #if there's a " bounded by the recently found ; then we
        #look for the next ; starting at the index where the ; was
        #found + 1 (end + 1)
        #we do this until we either reach the end of the string or
        #we find a string bound by ; without a "

        #what this means is we need to keep finding a ;
        #that doesn't have " within its boundary
        #once such a sequence is found, it hopefully
        #is of the form 'boundary=------12312312312312'
        while end > 0 and s.count(b'"', 0, end) % 2:
            end = s.find(b';', end + 1)
        if end < 0:
            end = len(s)
        f = s[:end]
        plist.append(f.strip())
        s = s[end:]
    return plist
