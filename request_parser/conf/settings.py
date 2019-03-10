
class Settings:
    """Setting used to configure the parser"""


FILE_UPLOAD_TEMP_DIR = '.'

FILE_UPLOAD_MAX_MEMORY_SIZE = 4096

DEFAULT_CHARSET = 'utf-8'

DATA_UPLOAD_MAX_NUMBER_FIELDS = 4096

#max memory size reserved for in-memory file handling
#default is 50 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * ((2 ** 10) * (2 ** 10))

#flag that configures whether request-parser should treat requests
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