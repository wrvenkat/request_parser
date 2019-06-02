import unittest
from platform import system
from os import rmdir

from request_parser.conf.settings import Settings, InvalidDirectory
from request_parser.files.utils import get_abs_path

class SettingsTests(unittest.TestCase):
    def test_invalid_arg_init(self):
        settings = Settings("Test")
        self.assertFalse(hasattr(settings, "FILE_UPLOAD_TEMP_DIR"))

    def test_file_upload_directory(self):
        settings = Settings.default()
        self.assertIn("files/file_uploads", settings.FILE_UPLOAD_TEMP_DIR)

        #if it's Linux or Mac
        if system() == 'Linux' or system() == 'Darwin':
            with self.assertRaises(InvalidDirectory) as invalidDir_Exception:
                settings = Settings({Settings.Key.FILE_UPLOAD_DIR : "/etc/"})
            self.assertEquals("No write permissions to directory: /etc", invalidDir_Exception.exception.args[0])
        
        if system() == 'Windows':
            settings = Settings({Settings.Key.FILE_UPLOAD_DIR : "C:/Program Files"})
    
    def test_default_settings(self):
        default_setting = Settings.default()

        self.assertTrue(hasattr(default_setting, "FILE_UPLOAD_TEMP_DIR"))
        self.assertTrue(hasattr(default_setting, "MAX_HEADER_SIZE"))
        self.assertTrue(hasattr(default_setting, "FILE_UPLOAD_MAX_MEMORY_SIZE"))
        self.assertTrue(hasattr(default_setting, "DATA_UPLOAD_MAX_MEMORY_SIZE"))
        self.assertTrue(hasattr(default_setting, "DATA_UPLOAD_MAX_NUMBER_FIELDS"))
        self.assertTrue(hasattr(default_setting, "DEFAULT_CHARSET"))

        #confirm the values
        self.assertIn('files/file_uploads', default_setting.FILE_UPLOAD_TEMP_DIR)
        self.assertEqual(16, default_setting.MAX_HEADER_SIZE)
        self.assertEqual(80 * ((2 ** 10) * (2 ** 10)), default_setting.FILE_UPLOAD_MAX_MEMORY_SIZE)
        self.assertEqual(100 * ((2 ** 10) * (2 ** 10)), default_setting.DATA_UPLOAD_MAX_MEMORY_SIZE)
        self.assertEqual(4096, default_setting.DATA_UPLOAD_MAX_NUMBER_FIELDS)
        self.assertEqual('ISO-8859-1', default_setting.DEFAULT_CHARSET)
    
    def test_custom_setting(self):
        test_file_dir = "tests/settings/test_file_dir"
        config = {
            Settings.Key.FILE_UPLOAD_DIR : test_file_dir,
            Settings.Key.FILE_UPLOAD_MAX_MEMORY : 10 * ((2 ** 10) * (2 ** 10))
        }

        custom_setting = Settings(config)

        self.assertTrue(hasattr(custom_setting, "FILE_UPLOAD_TEMP_DIR"))
        self.assertTrue(hasattr(custom_setting, "MAX_HEADER_SIZE"))
        self.assertTrue(hasattr(custom_setting, "FILE_UPLOAD_MAX_MEMORY_SIZE"))
        self.assertTrue(hasattr(custom_setting, "DATA_UPLOAD_MAX_MEMORY_SIZE"))
        self.assertTrue(hasattr(custom_setting, "DATA_UPLOAD_MAX_NUMBER_FIELDS"))
        self.assertTrue(hasattr(custom_setting, "DEFAULT_CHARSET"))

        #confirm the values
        self.assertIn('test_file_dir', custom_setting.FILE_UPLOAD_TEMP_DIR)
        self.assertEqual(16, custom_setting.MAX_HEADER_SIZE)
        self.assertEqual(10 * ((2 ** 10) * (2 ** 10)), custom_setting.FILE_UPLOAD_MAX_MEMORY_SIZE)
        self.assertEqual(100 * ((2 ** 10) * (2 ** 10)), custom_setting.DATA_UPLOAD_MAX_MEMORY_SIZE)
        self.assertEqual(4096, custom_setting.DATA_UPLOAD_MAX_NUMBER_FIELDS)
        self.assertEqual('ISO-8859-1', custom_setting.DEFAULT_CHARSET)

        test_file_dir = get_abs_path(test_file_dir)
        rmdir(test_file_dir)

unittest.main()