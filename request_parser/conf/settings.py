
class Settings:
    """Setting used to configure the parser"""

#Directory where file upload files will be stored
FILE_UPLOAD_TEMP_DIR = '.'

#Default max size of uploaded file is 80MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 80 * ((2 ** 10) * (2 ** 10))

DEFAULT_CHARSET = 'utf-8'

DATA_UPLOAD_MAX_NUMBER_FIELDS = 4096

#max memory size reserved for in-memory file handling
#default is 100 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * ((2 ** 10) * (2 ** 10))

#Flag that configures whether request-parser should treat requests
#as if they're meant for a web-proxy
WEB_PROXY = False

#holds the different upload handlers
#the ones listed below are the default ones which Django/request-parser
#requires to work properly while others can be added
FILE_UPLOAD_HANDLERS = [
    #hold uploaded files in-memory
    'request_parser.files.uploadhandler.MemoryFileUploadHandler',
    #hold uploaded files in a temp file
    'request_parser.files.uploadhandler.TemporaryFileUploadHandler',
 ]