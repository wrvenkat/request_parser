from request_parser.http.multipartparser import MultiPartParser
from request_parser.files import uploadhandler

def test1():    
    settings_upload_handlers = [
        #hold uploaded files in-memory
        'request_parser.files.uploadhandler.MemoryFileUploadHandler',
        #hold uploaded files in a temp file
        'request_parser.files.uploadhandler.TemporaryFileUploadHandler',
    ]

    #Set the _upload_handlers to an array of upload handlers loaded from
    #settings.FILE_UPLOAD_HANDLERS
    upload_handlers = [uploadhandler.load_handler(handler)
                                 for handler in settings_upload_handlers]

    META = {
        'CONTENT_LENGTH' : 554,
        'CONTENT_TYPE' : 'multipart/form-data; boundary=-------------------------9051914041544843365972754266'
    }

    test_dir = "multipart test files/"
    test_file1 = test_dir + "mp-test1.txt"
    stream1 = ''

    with open(test_file1, 'r') as stream1:
        try:
            multipartparser_1 = MultiPartParser(META, stream1, upload_handlers)
            multipartparser_1.parse()
        except Exception as e:
            print "Exception is: {}".format(e)
    
test1()