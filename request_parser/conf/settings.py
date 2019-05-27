
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
        'request_parser.files.uploadhandler.MemoryFileUploadHandler',
        #hold uploaded files in a temp file
        'request_parser.files.uploadhandler.TemporaryFileUploadHandler',
    ]

    def __init__(self, settings_dict=None):
        if not settings_dict or type(settings_dict) != dict:
            return

        default_settings = Settings.default()

        #FILE_UPLOAD_DIR
        if Settings.Key.FILE_UPLOAD_DIR in settings_dict:
                self.FILE_UPLOAD_TEMP_DIR = settings_dict[Settings.Key.FILE_UPLOAD_DIR]
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
            self.DATA_UPLOAD_MAX_FIELDS = settings_dict[Settings.Key.DATA_UPLOAD_MAX_FIELDS]
        else:
            self.DATA_UPLOAD_MAX_FIELDS =  default_settings.DATA_UPLOAD_MAX_FIELDS

        #DEFAULT_CHARSET
        if Settings.Key.DEFAULT_CHARSET in settings_dict:
            self.DEFAULT_CHARSET = settings_dict[Settings.Key.DEFAULT_CHARSET]
        else:
            self.DEFAULT_CHARSET = default_settings.DEFAULT_CHARSET
    
    @classmethod
    def default(cls):
        settings = Settings()

        #Directory where file upload files will be stored
        settings.FILE_UPLOAD_TEMP_DIR = 'file_uploads'

        #max header size of a header
        settings.MAX_HEADER_SIZE = 16

        #Default max size of uploaded file is 80MB
        settings.FILE_UPLOAD_MAX_MEMORY_SIZE = 80 * ((2 ** 10) * (2 ** 10))

        #max memory size reserved for in-memory file handling
        #default is 100 MB
        settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * ((2 ** 10) * (2 ** 10))

        settings.DATA_UPLOAD_MAX_FIELDS = 4096

        #Default charset per HTTP 1.1 - https://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.7.1
        settings.DEFAULT_CHARSET = 'ISO-8859-1'
        
        return settings
