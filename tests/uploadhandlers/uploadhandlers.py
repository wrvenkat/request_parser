import unittest
from os.path import join, splitext

import request_parser.http.request
from request_parser.files import uploadhandler
from request_parser.files.uploadhandler import StopFutureHandlers
from request_parser.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from request_parser.files.utils import get_abs_path
from request_parser.conf.settings import Settings, InvalidDirectory

class UploadHandlerTest(unittest.TestCase):
    """
    Test used to check how the files module reacts to change in Settings object.
    """
    
    @classmethod
    def setUpClass(cls):
        cls.FILE_UPLOAD_HANDLERS = [
            #hold uploaded files in-memory
            'request_parser.files.uploadhandler.MemoryFileUploadHandler',
            #hold uploaded files in a temp file
            'request_parser.files.uploadhandler.TemporaryFileUploadHandler',
            #convenient upload handler
            'request_parser.files.uploadhandler.ConvenientFileUploadHandler'
        ]
        cls.upload_handlers = [uploadhandler.load_handler(handler) for  handler in cls.FILE_UPLOAD_HANDLERS]

        #get a request handle
        test_files_dir = "tests/multipart test files/"
        test_files_dir = get_abs_path(test_files_dir)

        #PUT request with multipart-form-data
        test_file = "kitten.jpg"
        cls.test_file_path = join(test_files_dir, test_file)

        #chunk size is 64KB
        cls.chunk_size = 64 * (2 ** 10)

        #file is 572562 bytes long
        cls.test_file_size = 572.562 * 1000

    def test_in_memory_upload_activate(self):
        """
        Test MemoryFileUploadHandler and InMemoryUploadedFile
        """
        #get a file object
        test_file = open(self.test_file_path, "r")

        #set max in memory to 1MB
        max_in_memory_size = 1 * (2 ** 10) * (2 ** 10)
        custom_settings = Settings({Settings.Key.FILE_UPLOAD_MAX_MEMORY : max_in_memory_size})

        #get the in-memory upload handler
        in_memory_upload_handler = self.upload_handlers[0]

        #call the handle_raw method to activate
        in_memory_upload_handler.handle_raw_input(
                                                    test_file,
                                                    None, 
                                                    self.test_file_size,
                                                    None,
                                                    custom_settings,
                                                    None
                                                )
        
        #create a new file for inmemory handler
        try:
            in_memory_upload_handler.new_file(None, test_file.name, None, 0)
        except StopFutureHandlers:
            pass

        total_chunk_length = 0
        chunk = test_file.read(self.chunk_size)
        while chunk:
            in_memory_upload_handler.receive_data_chunk(chunk, total_chunk_length)
            total_chunk_length += len(chunk)
            chunk = test_file.read(self.chunk_size)
        test_file.close()
        
        in_memory_file = in_memory_upload_handler.file_complete(total_chunk_length)
        x = in_memory_file.read()

        self.assertTrue(isinstance(in_memory_file, InMemoryUploadedFile))
        self.assertEquals("kitten.jpg", in_memory_file.name)

    def test_in_memory_upload_inactive(self):
        """
        Test MemoryFileUploadHandler when it's inactive.
        """
        #get a file object
        test_file = open(self.test_file_path, "r")

        #set max in memory to 500KB
        max_in_memory_size = 500 * (2 ** 10)
        custom_settings = Settings({Settings.Key.FILE_UPLOAD_MAX_MEMORY : max_in_memory_size})

        #get the in-memory upload handler
        in_memory_upload_handler = self.upload_handlers[0]

        #call the handle_raw method to activate
        in_memory_upload_handler.handle_raw_input(
                                                    test_file,
                                                    None, 
                                                    self.test_file_size,
                                                    None,
                                                    custom_settings,
                                                    None
                                                )
        
        #create a new file for inmemory handler
        try:
            in_memory_upload_handler.new_file(None, test_file.name, None, 0)
        except StopFutureHandlers:
            pass

        total_chunk_length = 0
        chunk = test_file.read(self.chunk_size)
        while chunk:
            in_memory_upload_handler.receive_data_chunk(chunk, total_chunk_length)
            total_chunk_length += len(chunk)
            chunk = test_file.read(self.chunk_size)
        test_file.close()
        
        in_memory_file = in_memory_upload_handler.file_complete(total_chunk_length)

        self.assertIsNone(in_memory_file)
    
    def test_temp_file_upload(self):
        """
        Test TemporartFileUploadHandler and TemporaryUploadedFile
        """
        
        #get a file object
        test_file = open(self.test_file_path, "r")

        #get the temporary upload handler
        temp_file_upload_handler = self.upload_handlers[1]

        #call the handle_raw method to activate
        temp_file_upload_handler.handle_raw_input(
                                                    test_file,
                                                    None, 
                                                    self.test_file_size,
                                                    None,
                                                    Settings.default(check_presence=True),
                                                    None
                                                )
        
        #create a new file for inmemory handler
        try:
            temp_file_upload_handler.new_file(None, test_file.name, None, 0)
        except StopFutureHandlers:
            pass

        total_chunk_length = 0
        chunk = test_file.read(self.chunk_size)
        while chunk:
            temp_file_upload_handler.receive_data_chunk(chunk, total_chunk_length)
            total_chunk_length += len(chunk)
            chunk = test_file.read(self.chunk_size)
        test_file.close()
        
        temp_upload_file = temp_file_upload_handler.file_complete(total_chunk_length)

        self.assertTrue(isinstance(temp_upload_file, TemporaryUploadedFile))
        file_name, file_extension = splitext(temp_upload_file.name)
        self.assertEquals(".jpg", file_extension)
    
    def test_convenient_file_upload_in_memory(self):
        """
        Test TemporartFileUploadHandler and TemporaryUploadedFile
        """
        
        #get a file object
        test_file = open(self.test_file_path, "r")

         #set max in memory to 1MB
        max_in_memory_size = 1 * (2 ** 10) * (2 ** 10)
        custom_settings = Settings({Settings.Key.FILE_UPLOAD_MAX_MEMORY : max_in_memory_size})

        #get the convenient upload handler
        convenient_upload_handler = self.upload_handlers[2]

        #call the handle_raw method to activate
        convenient_upload_handler.handle_raw_input(
                                                    test_file,
                                                    None, 
                                                    self.test_file_size,
                                                    None,
                                                    custom_settings,
                                                    None
                                                )
        
        #create a new file for inmemory handler
        try:
            convenient_upload_handler.new_file(None, test_file.name, None, 0, None)
        except StopFutureHandlers:
            pass

        total_chunk_length = 0
        chunk = test_file.read(self.chunk_size)
        while chunk:
            convenient_upload_handler.receive_data_chunk(chunk, total_chunk_length)
            total_chunk_length += len(chunk)
            chunk = test_file.read(self.chunk_size)
        test_file.close()
        
        in_memory_file = convenient_upload_handler.file_complete(total_chunk_length)        

        self.assertTrue(isinstance(in_memory_file, InMemoryUploadedFile))
        self.assertEquals("kitten.jpg", in_memory_file.name)

    def test_convenient_file_upload_to_disk(self):
        """
        Test TemporartFileUploadHandler and TemporaryUploadedFile
        """
        
        #get a file object
        test_file = open(self.test_file_path, "r")

        #set max in memory to 500KB
        max_in_memory_size = 500 * (2 ** 10)
        custom_settings = Settings({Settings.Key.FILE_UPLOAD_MAX_MEMORY : max_in_memory_size}, check_presence=True)

        #get the convenient upload handler
        #reload it!
        self.upload_handlers[2] = uploadhandler.load_handler(self.FILE_UPLOAD_HANDLERS[2])
        convenient_upload_handler = self.upload_handlers[2]

        #call the handle_raw method to activate
        convenient_upload_handler.handle_raw_input(
                                                    test_file,
                                                    None, 
                                                    self.test_file_size,
                                                    None,
                                                    custom_settings,
                                                    None
                                                )
        
        #create a new file for inmemory handler
        try:
            convenient_upload_handler.new_file(None, test_file.name, None, 0, None)
        except StopFutureHandlers:
            pass

        total_chunk_length = 0
        chunk = test_file.read(self.chunk_size)
        while chunk:
            convenient_upload_handler.receive_data_chunk(chunk, total_chunk_length)
            total_chunk_length += len(chunk)
            chunk = test_file.read(self.chunk_size)
        test_file.close()
        
        on_disk_file = convenient_upload_handler.file_complete(total_chunk_length)        

        self.assertTrue(isinstance(on_disk_file, TemporaryUploadedFile))
        file_name, file_extension = splitext(on_disk_file.name)
        self.assertEquals(".jpg", file_extension)    

unittest.main()