from os.path import normpath, isdir, join, isabs
from os import errno, mkdir, remove
from request_parser.files.utils import get_abs_path

class InvalidDirectory(Exception):
    """
    Raised when get_abs_path fails to get a proper directory
    from the provided string.
    """
    
    def __init__(self, message, code=None, params=None):
        super(InvalidDirectory, self).__init__(message, code, params)

class Settings:
    """Setting used to configure the parser"""

    class Key:
        """
        Key to settings name mapping.
        """
        FILE_UPLOAD_DIR = "FILE_UPLOAD_TEMP_DIR"
        MAX_HEADER_SIZE = "MAX_HEADER_SIZE"
        FILE_UPLOAD_MAX_MEMORY = "FILE_UPLOAD_MAX_MEMORY"
        DATA_UPLOAD_MAX_MEMORY = "DATA_UPLOAD_MAX_MEMORY"
        DATA_UPLOAD_MAX_FIELDS = "DATA_UPLOAD_MAX_FIELDS"
        DEFAULT_CHARSET = "DEFAULT_CHARSET"

    #holds the different upload handlers
    #the ones listed below are the default ones which Django/request-parser
    #requires to work properly while others can be added
    FILE_UPLOAD_HANDLERS = [
        #hold uploaded files in-memory
        #'request_parser.files.uploadhandler.MemoryFileUploadHandler',
        #hold uploaded files in a temp file
        #'request_parser.files.uploadhandler.TemporaryFileUploadHandler',

        #File upload handler that's convenient to handle file uploads that are
        #large and small
        'request_parser.files.uploadhandler.ConvenientFileUploadHandler',
    ]

    def __init__(self, settings_dict=None, check_presence=False):
        if not settings_dict or type(settings_dict) != dict:
            return

        default_settings = Settings.default(check_presence=check_presence)

        #FILE_UPLOAD_DIR
        if Settings.Key.FILE_UPLOAD_DIR in settings_dict:
                self.FILE_UPLOAD_TEMP_DIR = settings_dict[Settings.Key.FILE_UPLOAD_DIR]
                self.FILE_UPLOAD_TEMP_DIR = self._check_upload_dir(check_presence=True)
        else:
            self.FILE_UPLOAD_TEMP_DIR = default_settings.FILE_UPLOAD_TEMP_DIR

        #MAX_HEADER_SIZE
        if Settings.Key.MAX_HEADER_SIZE in settings_dict:
            self.MAX_HEADER_SIZE = settings_dict[Settings.Key.MAX_HEADER_SIZE]
        else:
            self.MAX_HEADER_SIZE = default_settings.MAX_HEADER_SIZE

        #FILE_UPLOAD_MAX_MEMORY_SIZE
        if Settings.Key.FILE_UPLOAD_MAX_MEMORY in settings_dict:
            self.FILE_UPLOAD_MAX_MEMORY_SIZE = settings_dict[Settings.Key.FILE_UPLOAD_MAX_MEMORY]
        else:
            self.FILE_UPLOAD_MAX_MEMORY_SIZE = default_settings.FILE_UPLOAD_MAX_MEMORY_SIZE

        #DATA_UPLOAD_MAX_MEMORY_SIZE
        if Settings.Key.DATA_UPLOAD_MAX_MEMORY in settings_dict:
            self.DATA_UPLOAD_MAX_MEMORY_SIZE = settings_dict[Settings.Key.DATA_UPLOAD_MAX_MEMORY]
        else:
            self.DATA_UPLOAD_MAX_MEMORY_SIZE = default_settings.DATA_UPLOAD_MAX_MEMORY_SIZE

        #DATA_UPLOAD_MAX_FIELDS
        if Settings.Key.DATA_UPLOAD_MAX_FIELDS in settings_dict:
            self.DATA_UPLOAD_MAX_NUMBER_FIELDS = settings_dict[Settings.Key.DATA_UPLOAD_MAX_FIELDS]
        else:
            self.DATA_UPLOAD_MAX_NUMBER_FIELDS =  default_settings.DATA_UPLOAD_MAX_NUMBER_FIELDS

        #DEFAULT_CHARSET
        if Settings.Key.DEFAULT_CHARSET in settings_dict:
            self.DEFAULT_CHARSET = settings_dict[Settings.Key.DEFAULT_CHARSET]
        else:
            self.DEFAULT_CHARSET = default_settings.DEFAULT_CHARSET
    
    @classmethod
    def default(cls, check_presence=False):
        settings = Settings()

        #Directory where file upload files will be stored
        #default directory is relative to the module.
        settings.FILE_UPLOAD_TEMP_DIR = join('files','file_uploads')

        #max header size of a header
        settings.MAX_HEADER_SIZE = 16

        # Maximum size, in bytes, of a request before it will be streamed to the
        # file system instead of into memory.
        #default value is 30 MB
        settings.FILE_UPLOAD_MAX_MEMORY_SIZE = 30 * ((2 ** 10) * (2 ** 10))
        
        # Maximum size in bytes of request data (excluding file uploads) that will be
        # read before a SuspiciousOperation (RequestDataTooBig) is raised.
        #default is 5 MB
        settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * ((2 ** 10) * (2 ** 10))

        # Maximum number of GET/POST parameters that will be read before a
        # SuspiciousOperation (TooManyFieldsSent) is raised.
        settings.DATA_UPLOAD_MAX_NUMBER_FIELDS = 4096

        #Default charset per HTTP 1.1 - https://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.7.1
        settings.DEFAULT_CHARSET = 'ISO-8859-1'
        
        settings.FILE_UPLOAD_TEMP_DIR = settings._check_upload_dir(check_presence=check_presence)

        return settings

    def _check_upload_dir(self, check_presence=False):
        """
        Method that canonicalizes the FILE_UPLOAD_DIR if required and checks for permission issues.
        """
        file_upload_dir = self.FILE_UPLOAD_TEMP_DIR
        file_upload_dir = normpath(file_upload_dir)

        #if the provided directory path is not present(already) or
        #if it's an absolute path
        if not isabs(file_upload_dir) or not isdir(file_upload_dir):
            #try to get a directory path with
            #FILE_UPLOAD_TEMP_DIR in the path
            file_upload_dir = get_abs_path(file_upload_dir)
        
        if check_presence:
            #check permission for creating directory and writing files
            try:
                #check if directory exists if not create
                if not isdir(file_upload_dir):
                    mkdir(file_upload_dir)
                            
                test_file_path = join(file_upload_dir, "acdr423x.tmp")        
                test_file = open(test_file_path, "w+")
                test_file.write("Permissions Check!")
                test_file.close()
                remove(test_file_path)                
            except IOError as ioError:
                if ioError.errno == errno.EACCES:
                    raise InvalidDirectory("No write permissions to directory: {}".format(file_upload_dir))
                else:
                    raise InvalidDirectory("Error: Invalid directory: {}".format(file_upload_dir))
        
        return file_upload_dir