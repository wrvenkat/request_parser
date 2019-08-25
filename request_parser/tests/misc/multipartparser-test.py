import os, inspect

from request_parser.http.multipartparser import MultiPartParser
from request_parser.files import uploadhandler, utils
from request_parser.conf.settings import Settings

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
        'Content-Length' : 554,
        'Content-Type' : 'multipart/form-data; boundary=-------------------------9051914041544843365972754266'
    }

    test_dir = "tests/multipart test files/"
    test_file1 = test_dir + "mp-test1.txt"
    test_file1 = utils.get_abs_path(test_file1)
    stream1 = ''

    with open(test_file1, 'rb') as stream1:
        try:
            multipartparser_1 = MultiPartParser(META, stream1, upload_handlers, Settings.default())
            post, files = multipartparser_1.parse()
            print("Done parsing!")
        except Exception as e:
            print("Exception is: {}".format(e))
    
test1()