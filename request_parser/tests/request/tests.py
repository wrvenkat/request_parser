from io import BytesIO
from itertools import chain
import unittest

from future.backports.urllib.parse import urlencode

from request_parser.http.request import HttpRequest, RawPostDataException, UnreadablePostError
from request_parser.http.multipartparser import MultiPartParserError
from request_parser.http.request import split_domain_port
from request_parser.tests import testutils

class RequestsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_files_dir = "request parse test files"
        test_files_dir = testutils.get_abs_path(test_files_dir)

        request_file = "complex-request1.txt"
        cls.request_file = test_files_dir + request_file
        request_stream = open(cls.request_file, 'r')

        cls.http_request = HttpRequest(request_stream)

    def test_httprequest(self):
        """
        Empty request/init test.
        """
        request = HttpRequest(None)
        self.assertEqual(list(request.GET), [])
        self.assertEqual(list(request.POST), [])
        self.assertEqual(list(request.META), [])

        # .GET and .POST should be QueryDicts
        self.assertEqual(request.GET.urlencode(), '')
        self.assertEqual(request.POST.urlencode(), '')

        # and FILES should be MultiValueDict
        self.assertEqual(request.FILES.getlist('foo'), [])

        self.assertIsNone(request.request_stream)
        self.assertIsNone(request.method)
        self.assertIsNone(request.scheme)
        self.assertIsNone(request.host)
        self.assertIsNone(request.port)
        self.assertIsNone(request.path)
        self.assertIsNone(request.path_info)
        self.assertIsNone(request.protocol_info)
        self.assertIsNone(request.content_type)
        self.assertIsNone(request.content_params)

unittest.main()