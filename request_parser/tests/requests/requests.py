from io import BytesIO
from itertools import chain
import base64
import unittest
from os.path import join

from request_parser.http.request import HttpRequest, RawPostDataException, UnreadablePostError, split_domain_port
from request_parser.http.multipartparser import MultiPartParserError
from request_parser.files.utils import get_abs_path
from request_parser.http.constants import MetaDict
from request_parser.utils.encoding import iri_to_uri, uri_to_iri
from request_parser.http.request import InvalidHttpRequest, parse_request_headers, QueryDict
from request_parser.http.multipartparser import MultiPartParserError
from request_parser.conf.settings import Settings
from request_parser.exceptions.exceptions import RequestDataTooBig

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
        test_files_dir = "tests/request parse test files"
        cls.test_files_dir = get_abs_path(test_files_dir)

        request_file = "complex-request1.txt"
        cls.request_file = join(cls.test_files_dir, request_file)
    
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

        #close the file/stream
        request_stream.close()
    
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

        #close the file/stream
        request_stream.close()

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

        #close the file/stream
        request_stream.close()
    
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

        #close the file/stream
        request_stream.close()
    
    def test_http_request_encoding_and_bodystream_metadata_reset(self):
        """
        This test covers the encoding set/reset and the body_stream reset
        cases.
        """
        #charset/encoding reset test
        encoded_body_dir = "tests/request parse test files/encoded body"
        encoded_body_dir = get_abs_path(encoded_body_dir)

        iso_88591_1_file = "ISO-8859-1-Barca.txt"
        utf8_file = "UTF8-Barca.txt"
        utf16_BEBOM_file = "UTF16 BEBOM-Barca.txt"

        iso_88591_1_file = join(encoded_body_dir, iso_88591_1_file)
        utf8_file = join(encoded_body_dir, utf8_file)
        utf16_BEBOM_file = join(encoded_body_dir, utf16_BEBOM_file)

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

        #close the file/stream
        request_stream.close()

    def test_http_request_stream_set(self):
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
        self.assertEqual("multipart/form-data", http_request.content_type)
        self.assertIsNone(http_request.content_params)

        #another request file
        another_test_file = "get-request1.txt"
        another_test_file = join(self.test_files_dir, another_test_file)
        another_test_file_stream = open(another_test_file, 'r')
        http_request.stream = another_test_file_stream

        #Confirm new Request Headers
        http_request.parse_request_header()
        http_request.parse_request_body()
        request_headers = http_request.META[MetaDict.Info.REQ_HEADERS]
        self.assertEqual("www.knowhere484.com", http_request.get_host())        
        self.assertListEqual(["en-us"], request_headers.getlist('Accept-Language'))
        self.assertListEqual(["gzip, deflate"], request_headers.getlist('Accept-Encoding'))
        self.assertListEqual(["cookie3=value3, cookie4=value4"], request_headers.getlist('Cookies'))
        self.assertListEqual(["Safari/4.0 (compatible; MSIE5.01; Linux Blah)"], request_headers.getlist('User-Agent'))
        self.assertEqual("application/x-www-form-urlencoded", http_request.content_type)
        self.assertIsNone(http_request.content_params)

        #close the file/stream
        request_stream.close()
        another_test_file_stream.close()

class RequestTests(unittest.TestCase):
    """
    Test the request parsing - Invalid requests, query string. Post data - key value pairs,
    multipart/form-data, other content-types.
    """
    @classmethod
    def setUpClass(cls):
        cls.maxDiff = None

        test_files_dir = "tests/request parse test files"
        test_files_dir = get_abs_path(test_files_dir)
        
        #GET request
        get_request_with_query_file = "get-request-with-query-string.txt"
        cls.get_request_with_query = join(test_files_dir, get_request_with_query_file)

        #POST request
        post_request_with_query_file = "post-request-with-query.txt"
        cls.post_request_with_query_file = join(test_files_dir, post_request_with_query_file)

        #PUT request with multipart-form-data
        put_request_multipart_file = "complex-request1.txt"
        cls.put_request_multipart_file = join(test_files_dir, put_request_multipart_file)

    def test_request_query_string(self):
        #get file stream
        get_request_with_query_stream = open(self.get_request_with_query,'r')

        get_request_with_query = HttpRequest(get_request_with_query_stream)
        get_request_with_query.parse_request_header()
        get_request_with_query.parse_request_body()
        # Use of dict() had to be changed to QueryDict() as the test seem to be failing on Jython
        # where full repr(obj) seems to be used to perform equality of 2 dicts but for print calls
        # only the proper doct() level repr() call is used.
        # By using QueryDict(), we can maintain Jython compatibility
        request_GET = QueryDict(Settings.default(), mutable=True)
        request_GET['source'] = 'hp'
        request_GET['ei'] = 'H8jpXI_lN4OiswXa-oOwAw'
        request_GET['q'] = 'asdfadsf'
        request_GET['oq'] = 'asdfadsf'
        request_GET['gs_l'] = 'psy-ab.12..0j0i10l3j0j0i10l5.1255.1577..2445...0.0..1.153.972.2j6......0....1..gws-wiz.....0..0i131.DPwpRijoAMc'
        self.assertDictEqual(request_GET, get_request_with_query.GET)
        self.assertDictEqual(QueryDict(Settings.default(), mutable=True), get_request_with_query.POST)

        #close get request
        get_request_with_query_stream.close()

        #get file stream
        post_request_with_query_stream = open(self.post_request_with_query_file,'r')

        post_request_with_query = HttpRequest(post_request_with_query_stream)
        post_request_with_query.parse_request_header()
        post_request_with_query.parse_request_body()
        request_POST = QueryDict(Settings.default(), mutable=True)
        request_POST['source'] = 'hp'
        request_POST['ei'] = 'H8jpXI_lN4OiswXa-oOwAw'
        request_POST['q'] = 'asdfadsf'
        request_POST['oq'] = 'asdfadsf'
        request_POST['gs_l'] = 'psy-ab.12..0j0i10l3j0j0i10l5.1255.1577..2445...0.0..1.153.972.2j6......0....1..gws-wiz.....0..0i131.DPwpRijoAMc'
        self.assertDictEqual(request_POST, post_request_with_query.POST)
        self.assertDictEqual(QueryDict(Settings.default(), mutable=True), post_request_with_query.GET)

        #close request file
        post_request_with_query_stream.close()

    def test_request_multipart_request(self):
        """
        Test a complex request with multipart-form-data body.
        """
        multipart_request_stream = open(self.put_request_multipart_file, 'r')

        #get a request handle
        multipart_request = HttpRequest(multipart_request_stream)
        multipart_request.parse_request_header()
        multipart_request.parse_request_body()
        
        #request data that should be present
        _POST = QueryDict(Settings.default(), mutable=True)
        _POST['id'] = '123e4567-e89b-12d3-a456-426655440000'
        _POST['address'] = '{\r\n  \"street\": \"3, Garden St\",\r\n  \"city\": \"Hillsbery, UT\"\r\n}'
        _GET = QueryDict(Settings.default(), mutable=True)

        #test
        self.assertDictEqual(_POST, multipart_request.POST)
        self.assertDictEqual(_GET, multipart_request.GET)
        self.assertIn('profileImage', multipart_request.FILES)
        _file = multipart_request.FILES.get('profileImage')
        #we create a string equivalent to base64 encoding the first 100 bytes from the raw file.
        first_100_bytes_b64 = '/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcvJik0KSEiMEExNDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDg=='
        #we assert that it is equal to the same that can be obtained by reading the file
        self.assertEquals(first_100_bytes_b64, base64.b64encode(_file.read(100)))

        #close it out
        multipart_request_stream.close()

    def test_request_data_too_big(self):
        """
        Tests both request.py's and multipartparser.py's RequestDataTooBig.
        """

        #text/plain test
        multipart_request_stream = open(self.put_request_multipart_file, 'r')

        #get a request handle
        multipart_request = HttpRequest(
                                multipart_request_stream,
                                #setting DATA_UPLOAD MAX to be 64 bytes
                                Settings({Settings.Key.DATA_UPLOAD_MAX_MEMORY : 64})
                            )
        multipart_request.parse_request_header()
        multipart_request.content_type = "text/plain"
        with self.assertRaises(RequestDataTooBig) as rqdTooBig_Exception:
            multipart_request.parse_request_body()
        self.assertEquals("Request body exceeded settings.DATA_UPLOAD_MAX_MEMORY_SIZE.", rqdTooBig_Exception.exception.args[0])
        multipart_request_stream.close()

        #x-www-form-urlencoded test
        multipart_request_stream = open(self.put_request_multipart_file, 'r')

        #get a request handle
        multipart_request = HttpRequest(
                                multipart_request_stream,
                                #setting DATA_UPLOAD MAX to be 64 bytes
                                Settings({Settings.Key.DATA_UPLOAD_MAX_MEMORY : 64})
                            )
        multipart_request.parse_request_header()
        multipart_request.content_type = "application/x-www-form-urlencoded"
        with self.assertRaises(RequestDataTooBig) as rqdTooBig_Exception:
            multipart_request.parse_request_body()
        self.assertEquals("Request body exceeded settings.DATA_UPLOAD_MAX_MEMORY_SIZE.", rqdTooBig_Exception.exception.args[0])
        multipart_request_stream.close()
        

    def test_invalid_request_header(self):
        #Incorrectly terminated request
        invalid_request_1 = "GET asasd\r\nHost: www.knowhere123.com\r\n"
        invalid_request_1 = BytesIO(invalid_request_1)
        invalid_http_request = HttpRequest(invalid_request_1)
        with self.assertRaises(InvalidHttpRequest) as iHR_Exception:
            invalid_http_request.parse_request_header()        
        self.assertEquals("Invalid HTTP request.", iHR_Exception.exception.args[0])
        self.assertEquals(400, iHR_Exception.exception.args[1])

        #reuest without any headers
        invalid_request_2 = "GET dadsadsasd HTTP/1.1\r\n\r\n\r\n"
        invalid_request_2 = BytesIO(invalid_request_2)
        invalid_http_request = HttpRequest(invalid_request_2)
        with self.assertRaises(InvalidHttpRequest) as iHR_Exception:
            invalid_http_request.parse_request_header()
        self.assertEquals("Invalid request. No request headers.", iHR_Exception.exception.args[0])
        self.assertEquals(400, iHR_Exception.exception.args[1])

        #invalid request line_0
        invalid_request = "GET asasd HTTP/1.1"
        with self.assertRaises(InvalidHttpRequest) as iHR_Exception:
            parse_request_headers(invalid_request)
        self.assertEqual("Invalid request. Request line terminated incorrectly.", iHR_Exception.exception.args[0])
        self.assertEquals(400, iHR_Exception.exception.args[1])

        #incorrect request line_1
        invalid_request_3 = "GET asasd\r\nHost: www.knowhere123.com\r\n\r\n"
        invalid_request_3 = BytesIO(invalid_request_3)
        invalid_http_request = HttpRequest(invalid_request_3)
        with self.assertRaises(InvalidHttpRequest) as iHR_Exception:
            invalid_http_request.parse_request_header()
        self.assertEquals("Invalid request line.", iHR_Exception.exception.args[0])
        self.assertEquals(400, iHR_Exception.exception.args[1])

        #incorrect request line_2
        invalid_request_4 = "GET asasd asdas HTTP/1.1\r\nHost: www.knowhere123.com\r\n\r\n"
        invalid_request_4 = BytesIO(invalid_request_4)
        invalid_http_request = HttpRequest(invalid_request_4)
        with self.assertRaises(InvalidHttpRequest) as iHR_Exception:
            invalid_http_request.parse_request_header()
        self.assertEquals("Invalid request line.", iHR_Exception.exception.args[0])
        self.assertEquals(400, iHR_Exception.exception.args[1])

        #incorrect request header
        invalid_request_4 = "GET asasd HTTP/1.1\r\nHost www.knowhere123.com\r\n\r\n"
        invalid_request_4 = BytesIO(invalid_request_4)
        invalid_http_request = HttpRequest(invalid_request_4)
        with self.assertRaises(InvalidHttpRequest) as iHR_Exception:
            invalid_http_request.parse_request_header()        
        self.assertIn("Invalid request header", iHR_Exception.exception.args[0])
        self.assertEquals(400, iHR_Exception.exception.args[1])        

    def test_post_process_body_read(self):
        """
        Read body for a non text/plain request after parse_request_body().
        """
        http_request_stream = open(self.put_request_multipart_file, 'r')
        http_request = HttpRequest(http_request_stream)
        http_request.parse_request_header()
        http_request.parse_request_body()
        with self.assertRaises(RawPostDataException) as rPDE_Exception:
            body = http_request.body()
        self.assertEquals("You cannot access raw body after reading from request's data stream.", rPDE_Exception.exception.args[0])

    def test_invalid_request_body(self):
        """
        Test request body.
        """
        http_request_stream = open(self.put_request_multipart_file, 'r')
        http_request = HttpRequest(http_request_stream)
        http_request.parse_request_header()

        #Change Content-Type
        request_headers = http_request.META['REQUEST_HEADERS']
        request_headers._mutable = True
        request_headers.setlist('Content-Type','application/x-www-form-urlencoded')
        with self.assertRaises(MultiPartParserError) as mPPE_Exception:
            http_request.parse_request_body()
        self.assertEquals('Invalid Content-Type: application/x-www-form-urlencoded', mPPE_Exception.exception.args[0])
        
        #close the file
        http_request_stream.close()

        #get a POST request and pass it a multipart body
        http_request_stream = open(self.post_request_with_query_file, 'r')
        http_request = HttpRequest(http_request_stream)
        http_request.parse_request_header()

        #change request body
        multipart_body = "---------------------------9051914041544843365972754266\r\n"
        multipart_body += "Content-Disposition: form-data; name=\"file1\"; filename=\"a.txt\"\r\n"
        multipart_body+= "Content-Type: text/plain\r\n\r\nContent of a.txt:\r\n"
        multipart_body+= " abcdefghijklmnopqrstuvwxyz1234567890aabbccddeeffgghhiijjkkllmmnnooppqqrrssttuuvvwwxxyyzz11223344556677889900~!@#$%^&*()_+\r\n"
        multipart_body+= "---------------------------9051914041544843365972754266--\r\n\r\n"
        multipart_body = BytesIO(multipart_body)
        http_request.body_stream = multipart_body
        http_request.parse_request_body()
        self.assertIn(' name', http_request.POST)
        self.assertEquals('"file1"', http_request.POST[' name'])

        #close the file
        http_request_stream.close()

unittest.main()