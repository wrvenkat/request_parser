"""
Base file upload handler classes, and the built-in concrete subclasses
"""

from io import BytesIO
from request_parser.files.uploadedfile import (
    InMemoryUploadedFile, TemporaryUploadedFile,
)
from request_parser.utils.module_loading import import_string

__all__ = [
    'UploadFileException', 'StopUpload', 'SkipFile', 'FileUploadHandler',
    'TemporaryFileUploadHandler', 'MemoryFileUploadHandler', 'load_handler',
    'StopFutureHandlers'
]


class UploadFileException(Exception):
    """
    Any error having to do with uploading files.
    """
    pass


class StopUpload(UploadFileException):
    """
    This exception is raised when an upload must abort.
    """
    def __init__(self, connection_reset=False):
        """
        If ``connection_reset`` is ``True``, Django knows will halt the upload
        without consuming the rest of the upload. This will cause the browser to
        show a "connection reset" error.
        """
        self.connection_reset = connection_reset

    def __str__(self):
        if self.connection_reset:
            return 'StopUpload: Halt current upload.'
        else:
            return 'StopUpload: Consume request data, then halt.'


class SkipFile(UploadFileException):
    """
    This exception is raised by an upload handler that wants to skip a given file.
    """
    pass


class StopFutureHandlers(UploadFileException):
    """
    Upload handers that have handled a file and do not want future handlers to
    run should raise this exception instead of returning None.
    """
    pass


class FileUploadHandler:
    """
    Base class for streaming upload handlers.
    """
    chunk_size = 64 * 2 ** 10  # : The default chunk size is 64 KB.

    def __init__(self, request=None):
        self.file_name = None
        self.content_type = None
        self.content_length = None
        self.charset = None
        self.content_type_extra = None
        self.request = request

    def handle_raw_input(self, input_data, META, content_length, boundary, settings, encoding=None):
        """
        Handle the raw input from the client.

        Parameters:

            :input_data:
                An object that supports reading via .read().
            :META:
                ``request.META``.
            :content_length:
                The (integer) value of the Content-Length header from the
                client.
            :boundary: The boundary from the Content-Type header. Be sure to
                prepend two '--'.
        """
        pass

    def new_file(self, field_name, file_name, content_type, content_length, charset=None, content_type_extra=None):
        """
        Signal that a new file has been started.

        Warning: As with any data from the client, you should not trust
        content_length (and sometimes won't even get it).
        """
        self.field_name = field_name
        self.file_name = file_name
        self.content_type = content_type
        self.content_length = content_length
        self.charset = charset
        self.content_type_extra = content_type_extra

    def receive_data_chunk(self, raw_data, start):
        """
        Receive data from the streamed upload parser. ``start`` is the position
        in the file of the chunk.
        """
        raise NotImplementedError('subclasses of FileUploadHandler must provide a receive_data_chunk() method')

    def file_complete(self, file_size):
        """
        Signal that a file has completed. File size corresponds to the actual
        size accumulated by all the chunks.

        Subclasses should return a valid ``UploadedFile`` object.
        """
        raise NotImplementedError('subclasses of FileUploadHandler must provide a file_complete() method')

    def upload_complete(self):
        """
        Signal that the upload is complete. Subclasses should perform cleanup
        that is necessary for this handler.
        """
        pass


class TemporaryFileUploadHandler(FileUploadHandler, object):
    """
    Upload handler that streams data into a temporary file.
    """

    #QUESTION: There's no handle_raw_input(). Then how's a file upload handled that's
    #not in-memory?
    #ANSWER: handlr_raw_input() is not what is used to handle streaming into a temp file. That
    #would be receive_data_chunk().

    def handle_raw_input(self, input_data, META, content_length, boundary, settings, encoding=None):
        self.settings = settings

    def new_file(self, *args, **kwargs):
        """
        Create the file object to append to as data is coming in.
        """
        super(TemporaryFileUploadHandler, self).new_file(*args, **kwargs)
        self.file = TemporaryUploadedFile(self.file_name, self.content_type, 0, self.charset, self.settings, self.content_type_extra)

    def receive_data_chunk(self, raw_data, start):
        self.file.write(raw_data)

    def file_complete(self, file_size):
        self.file.seek(0)
        self.file.size = file_size
        return self.file


class MemoryFileUploadHandler(FileUploadHandler, object):
    """
    File upload handler to stream uploads into memory (used for small files).
    """

    def handle_raw_input(self, input_data, META, content_length, boundary, settings, encoding=None):
        """
        Use the content_length to signal whether or not this handler should be
        used.
        """
        # Check the content-length header to see if we should
        # If the post is too large, we cannot use the Memory handler.
        self.activated = content_length <= settings.FILE_UPLOAD_MAX_MEMORY_SIZE

    def new_file(self, *args, **kwargs):
        super(MemoryFileUploadHandler, self).new_file(*args, **kwargs)
        if self.activated:
            self.file = BytesIO()
            raise StopFutureHandlers()

    def receive_data_chunk(self, raw_data, start):
        """Add the data to the BytesIO file."""
        if self.activated:
            self.file.write(raw_data)
        else:
            return raw_data

    def file_complete(self, file_size):
        """Return a file object if this handler is activated."""
        if not self.activated:
            return

        self.file.seek(0)
        return InMemoryUploadedFile(
            file=self.file,
            field_name=self.field_name,
            name=self.file_name,
            content_type=self.content_type,
            size=file_size,
            charset=self.charset,
            content_type_extra=self.content_type_extra
        )


class ConvenientFileUploadHandler(FileUploadHandler, object):
    """
    A wrapper class that conveniently switches to TemporaryFileUploadHandler from MemoryFileUploadHandler
    when the size of content read exceeds settings.FILE_UPLOAD_MAX_MEMORY_SIZE.

    It's easier to compose the functionality of TemporaryFileUploadHandler and MoemoryFileUploadHandler
    by /using/ either of them instead of inheriting them.

    It's also easier to implement the functionalities this way while maintaining API compatibility.
    """

    def __init__(self, request=None):
        self._request = request
        self._handler = MemoryFileUploadHandler(request)
        self._received_data_size = 0
        self._switched_to_temp_file = False
    
    def handle_raw_input(self, input_data, META, content_length, boundary, settings, encoding=None):
        #We grab the settings object and call the handler's handle_raw_input to activate it.
        self._settings = settings
        
        #we pass the content_length arg to 0 so that the MemoryFileUploadHandler can be activated
        self._handler.handle_raw_input(input_data, META, 0, boundary, settings, encoding)
    
    def new_file(self, *args, **kwargs):
        self._handler.new_file(*args, **kwargs)
    
    def receive_data_chunk(self, raw_data, start):
        current_data_size = len(raw_data)
        
        #check if switching to temp file is required
        if not self._switched_to_temp_file and\
        self._received_data_size + current_data_size > self._settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
            #signal close of file_upload to current handler and
            #get a InMemoryUploadedFile object
            current_content_file = self.file_complete(self._received_data_size)
            content = current_content_file.read()

            #create a new temporary file now that the max size for in-memory
            #handling has exceeded
            temp_upload_handler = TemporaryFileUploadHandler(self._request)

            #activate it
            temp_upload_handler.handle_raw_input(None, None, 0, None, self._settings)

            #create a new file
            temp_upload_handler.new_file(self._handler.field_name, self._handler.file_name, self._handler.content_type, 0, self._handler.charset, self._handler.content_type_extra)

            #stream all of the read data into the temp file
            temp_upload_handler.receive_data_chunk(content, 0)

            #reset the current file handler
            self._handler = temp_upload_handler

            #flag that we've switched to temp file
            self._switched_to_temp_file = True
        
        #stream the raw into the current handle
        self._handler.receive_data_chunk(raw_data, start)

        self._received_data_size += current_data_size
    
    def file_complete(self, file_size):
        return self._handler.file_complete(file_size)

    def upload_complete(self):
        self._handler.upload_complete()


def load_handler(path, *args, **kwargs):
    """
    Given a path to a handler, return an instance of that handler.

    E.g.::
        >>> from django.http import HttpRequest
        >>> request = HttpRequest()
        >>> load_handler('django.core.files.uploadhandler.TemporaryFileUploadHandler', request)
        <TemporaryFileUploadHandler object at 0x...>
    """
    return import_string(path)(*args, **kwargs)
