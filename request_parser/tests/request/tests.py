from io import BytesIO
from itertools import chain
import unittest

from future.backports.urllib.parse import urlencode, quote

from request_parser.http.request import HttpRequest, RawPostDataException, UnreadablePostError, split_domain_port
from request_parser.http.multipartparser import MultiPartParserError
from request_parser.tests import testutils
from request_parser.http.constants import MetaDict

from request_parser.utils.encoding import iri_to_uri, uri_to_iri

class HttpRequestBasicTests(unittest.TestCase):

    def test_empty_request_stream(self):
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

        self.assertIsNone(request.method)
        self.assertIsNone(request.scheme)
        self.assertIsNone(request.host)
        self.assertIsNone(request.port)
        self.assertIsNone(request.path)
        self.assertIsNone(request.protocol_info)
        self.assertIsNone(request.content_type)
        self.assertIsNone(request.content_params)

    def test_httprequest_full_path(self):
        request = HttpRequest()
        request.path = '/;some/?awful/=path/foo:bar/'
        request.path_info = '/prefix' + request.path
        request.META['QUERY_STRING'] = ';some=query&+query=string'
        expected = '/%3Bsome/%3Fawful/%3Dpath/foo:bar/?;some=query&+query=string'
        self.assertEqual(request.get_full_path(), expected)        

    def test_httprequest_full_path_with_query_string_and_fragment(self):
        request = HttpRequest()
        request.path = '/foo#bar'
        request.path_info = '/prefix' + request.path
        request.META['QUERY_STRING'] = 'baz#quux'
        self.assertEqual(request.get_full_path(), '/foo%23bar?baz#quux')

    def test_httprequest_repr(self):
        request = HttpRequest()
        request.path = '/somepath/'
        request.method = 'GET'
        request.GET = {'get-key': 'get-value'}
        request.POST = {'post-key': 'post-value'}
        request.COOKIES = {'post-key': 'post-value'}
        request.META = {'post-key': 'post-value'}
        self.assertEqual(repr(request), "<HttpRequest: GET '/somepath/'>")

    def test_httprequest_repr_invalid_method_and_path(self):
        request = HttpRequest()
        self.assertEqual(repr(request), "<HttpRequest>")
        request = HttpRequest()
        request.method = "GET"
        self.assertEqual(repr(request), "<HttpRequest>")
        request = HttpRequest()
        request.path = ""
        self.assertEqual(repr(request), "<HttpRequest>")

class RequestHeaderTests(unittest.TestCase):
    """
    HttpRequest META data check.
    """
    @classmethod
    def setUpClass(cls):
        test_files_dir = "request parse test files"
        test_files_dir = testutils.get_abs_path(test_files_dir)

        request_file = "complex-request1.txt"
        cls.request_file = test_files_dir + request_file
    
    def test_http_headers_post_header_parse(self):
        """
        Test the META dict value for the request headers.
        """
        request_stream = open(self.request_file, 'r')
        http_request = HttpRequest(request_stream)

        #Confirm Request Headers
        http_request.parse_request_header()
        request_headers = http_request.META[MetaDict.Info.REQ_HEADERS]
        self.assertEqual("www.knowhere123.com", http_request.get_host())
        self.assertListEqual(["image/gif, image/jpeg, */*"], request_headers.getlist('Accept'))
        self.assertListEqual(["en-us"], request_headers.getlist('Accept-Language'))
        self.assertListEqual(["gzip, deflate"], request_headers.getlist('Accept-Encoding'))
        self.assertListEqual(["cookie1=value1, cookie2=value2", "cookie3=value3, cookie4=value4"], request_headers.getlist('Cookies'))
        self.assertListEqual(["Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)"], request_headers.getlist('User-Agent'))
        self.assertListEqual(["830543"], request_headers.getlist('Content-Length'))
        self.assertListEqual(["image/gif, image/jpeg, */*"], request_headers.getlist('Accept'))
        self.assertListEqual(["830543"], request_headers.getlist('Content-Length'))
        self.assertEqual("multipart/form-data", http_request.content_type)
        self.assertIsNone(http_request.content_params)
    
    def test_http_request_line(self):
        """
        Test the request line.
        """
        request_stream = open(self.request_file, 'r')
        http_request = HttpRequest(request_stream)
        http_request.parse_request_header()

        #Request line meta data check
        self.assertEqual("PUT", http_request.get_method())
        self.assertEqual("UNKNOWN", http_request.get_scheme())
        self.assertEqual("/caf%C3%A9/upload", http_request.get_path())
        self.assertEqual("HTTP/1.1", http_request.get_protocol_info())
        self.assertEqual("65536", http_request.get_port())

    def test_http_request_url_reconstruct(self):
        """
        Test reconstructing the original request path with meta data.
        """
        request_stream = open(self.request_file, 'r')
        http_request = HttpRequest(request_stream)
        http_request.parse_request_header()

        #URL encoded UTF-8        
        self.assertEqual("UNKNOWN://www.knowhere123.com/caf%C3%A9/upload", http_request.get_uri())
        #get RAW URI
        #café here is UTF-8 encoded, so when get_uri(raw=True) returns,
        #the representation of the returned value should be same as the UTF-8
        #representation of café
        self.assertEqual("UNKNOWN://www.knowhere123.com/café/upload", http_request.get_uri(raw=True))
        self.assertFalse(http_request.is_ajax())
        self.assertFalse(http_request.is_secure())
    
    def test_http_request_path_metadata_reset(self):
        """
        Test (re)set of meta data post request header processing.
        """
        request_stream = open(self.request_file, 'r')
        http_request = HttpRequest(request_stream)
        http_request.parse_request_header()

        #URI/path string (excluding querys tring) set/reset test
        self.assertEqual("UNKNOWN://www.knowhere123.com/caf%C3%A9/upload", http_request.get_uri())
        new_international_path = "/سلام/this%/is$*()$!@/a/new/path/Name/Müeller"
        http_request.set_path(new_international_path)
        self.assertEqual("UNKNOWN://www.knowhere123.com/%D8%B3%D9%84%D8%A7%D9%85/this%/is$*()$!@/a/new/path/Name/M%C3%BCeller", http_request.get_uri())
        self.assertEqual("UNKNOWN://www.knowhere123.com/سلام/this%/is$*()$!@/a/new/path/Name/Müeller", http_request.get_uri(raw=True))
        #print http_request.get_uri()
    
    def test_http_request_encoding_and_bodystream_metadata_reset(self):
        """
        This test covers the encoding set/reset and the body_stream reset
        cases.
        """
        #charset/encoding reset test
        encoded_body_dir = "request parse test files/encoded body"
        encoded_body_dir = testutils.get_abs_path(encoded_body_dir)

        iso_88591_1_file = "ISO-8859-1-Barca.txt"
        utf8_file = "UTF8-Barca.txt"
        utf16_BEBOM_file = "UTF16 BEBOM-Barca.txt"

        iso_88591_1_file = encoded_body_dir + iso_88591_1_file
        utf8_file = encoded_body_dir + utf8_file
        utf16_BEBOM_file = encoded_body_dir + utf16_BEBOM_file

        iso_88591_1_encoding = "ISO-8859-1"
        utf8_encoding = "UTF-8"
        utf16_BEBOM_encoding = "UTF-16"

        #an http_request
        request_stream = open(self.request_file, 'r')
        http_request = HttpRequest(request_stream)
        http_request.parse_request_header()

        #ISO-88591-1
        #reset content-type and encoding
        iso_88591_1_body = open(iso_88591_1_file, 'r')
        http_request.content_type = "text/plain"
        http_request.encoding = iso_88591_1_encoding.lower()
        #set the request_body stream
        http_request.body_stream = iso_88591_1_body
        http_request.parse_request_body()

        #check if the request body was properly decoded as ISO-8859-1
        _body_file = open(iso_88591_1_file, 'r')
        _body_bytes = _body_file.read()
        _body_bytes = _body_bytes.decode(iso_88591_1_encoding.lower())
        http_body = http_request.body()
        #the body should be in the encoding specified in the request
        self.assertEqual(_body_bytes, http_body)

        #UTF-16
        #reset content-type and encoding
        utf16_BEBOM_body = open(utf16_BEBOM_file, 'r')
        http_request.content_type = "text/plain"
        http_request.encoding = utf16_BEBOM_encoding.lower()
        #set the request_body stream
        http_request.body_stream = utf16_BEBOM_body
        http_request.parse_request_body()

        #check if the request body was properly decoded as ISO-8859-1
        _body_file = open(utf16_BEBOM_file, 'r')
        _body_bytes = _body_file.read()
        _body_bytes = _body_bytes.decode(utf16_BEBOM_encoding.lower())
        http_body = http_request.body()
        #the body should be in the encoding specified in the request
        self.assertEqual(_body_bytes, http_body)

        #UTF-8
        #reset content-type and encoding
        utf8_body = open(utf8_file, 'r')
        http_request.content_type = "text/plain"
        http_request.encoding = utf8_encoding.lower()
        #set the request_body stream
        http_request.body_stream = utf8_body
        http_request.parse_request_body()

        #check if the request body was properly decoded as ISO-8859-1
        _body_file = open(utf8_file, 'r')
        _body_bytes = _body_file.read()
        _body_bytes = _body_bytes.decode(utf8_encoding.lower())
        http_body = http_request.body()
        #the body should be in the encoding specified in the request
        self.assertEqual(_body_bytes, http_body)

unittest.main()