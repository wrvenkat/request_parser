import unittest
from request_parser.conf.settings import Settings

class SettingsTests(unittest.TestCase):
    def test_invalid_arg_init(self):
        settings = Settings("Test")
        self.assertFalse(hasattr(settings, "FILE_UPLOAD_TEMP_DIR"))

    def test_default_settings(self):
        default_setting = Settings.default()

        self.assertTrue(hasattr(default_setting, "FILE_UPLOAD_TEMP_DIR"))
        self.assertTrue(hasattr(default_setting, "MAX_HEADER_SIZE"))
        self.assertTrue(hasattr(default_setting, "FILE_UPLOAD_MAX_MEMORY_SIZE"))
        self.assertTrue(hasattr(default_setting, "DATA_UPLOAD_MAX_MEMORY_SIZE"))
        self.assertTrue(hasattr(default_setting, "DATA_UPLOAD_MAX_NUMBER_FIELDS"))
        self.assertTrue(hasattr(default_setting, "DEFAULT_CHARSET"))

        #confirm the values
        self.assertEqual('file_uploads', default_setting.FILE_UPLOAD_TEMP_DIR)
        self.assertEqual(16, default_setting.MAX_HEADER_SIZE)
        self.assertEqual(80 * ((2 ** 10) * (2 ** 10)), default_setting.FILE_UPLOAD_MAX_MEMORY_SIZE)
        self.assertEqual(100 * ((2 ** 10) * (2 ** 10)), default_setting.DATA_UPLOAD_MAX_MEMORY_SIZE)
        self.assertEqual(4096, default_setting.DATA_UPLOAD_MAX_NUMBER_FIELDS)
        self.assertEqual('ISO-8859-1', default_setting.DEFAULT_CHARSET)
    
    def test_custom_setting(self):
        config = {
            Settings.Key.FILE_UPLOAD_DIR : "test_file_dir",
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
        self.assertEqual('test_file_dir', custom_setting.FILE_UPLOAD_TEMP_DIR)
        self.assertEqual(16, custom_setting.MAX_HEADER_SIZE)
        self.assertEqual(10 * ((2 ** 10) * (2 ** 10)), custom_setting.FILE_UPLOAD_MAX_MEMORY_SIZE)
        self.assertEqual(100 * ((2 ** 10) * (2 ** 10)), custom_setting.DATA_UPLOAD_MAX_MEMORY_SIZE)
        self.assertEqual(4096, custom_setting.DATA_UPLOAD_MAX_NUMBER_FIELDS)
        self.assertEqual('ISO-8859-1', custom_setting.DEFAULT_CHARSET)

unittest.main()