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


    def test_httprequest_full_path(self):
        request = HttpRequest()
        request.path = '/;some/?awful/=path/foo:bar/'
        request.path_info = '/prefix' + request.path
        request.META['QUERY_STRING'] = ';some=query&+query=string'
        expected = '/%3Bsome/%3Fawful/%3Dpath/foo:bar/?;some=query&+query=string'
        self.assertEqual(request.get_full_path(), expected)
        self.assertEqual(request.get_full_path_info(), '/prefix' + expected)

    def test_httprequest_full_path_with_query_string_and_fragment(self):
        request = HttpRequest()
        request.path = '/foo#bar'
        request.path_info = '/prefix' + request.path
        request.META['QUERY_STRING'] = 'baz#quux'
        self.assertEqual(request.get_full_path(), '/foo%23bar?baz#quux')
        self.assertEqual(request.get_full_path_info(), '/prefix/foo%23bar?baz#quux')

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

    def test_wsgirequest_path_info(self):
        def wsgi_str(path_info, encoding='utf-8'):
            path_info = path_info.encode(encoding)  # Actual URL sent by the browser (bytestring)
            path_info = path_info.decode('iso-8859-1')  # Value in the WSGI environ dict (native string)
            return path_info
        # Regression for #19468
        request = WSGIRequest({'PATH_INFO': wsgi_str("/سلام/"), 'REQUEST_METHOD': 'get', 'wsgi.input': BytesIO(b'')})
        self.assertEqual(request.path, "/سلام/")

        # The URL may be incorrectly encoded in a non-UTF-8 encoding (#26971)
        request = WSGIRequest({
            'PATH_INFO': wsgi_str("/café/", encoding='iso-8859-1'),
            'REQUEST_METHOD': 'get',
            'wsgi.input': BytesIO(b''),
        })
        # Since it's impossible to decide the (wrong) encoding of the URL, it's
        # left percent-encoded in the path.
        self.assertEqual(request.path, "/caf%E9/")

    def test_limited_stream(self):
        # Read all of a limited stream
        stream = LimitedStream(BytesIO(b'test'), 2)
        self.assertEqual(stream.read(), b'te')
        # Reading again returns nothing.
        self.assertEqual(stream.read(), b'')

        # Read a number of characters greater than the stream has to offer
        stream = LimitedStream(BytesIO(b'test'), 2)
        self.assertEqual(stream.read(5), b'te')
        # Reading again returns nothing.
        self.assertEqual(stream.readline(5), b'')

        # Read sequentially from a stream
        stream = LimitedStream(BytesIO(b'12345678'), 8)
        self.assertEqual(stream.read(5), b'12345')
        self.assertEqual(stream.read(5), b'678')
        # Reading again returns nothing.
        self.assertEqual(stream.readline(5), b'')

        # Read lines from a stream
        stream = LimitedStream(BytesIO(b'1234\n5678\nabcd\nefgh\nijkl'), 24)
        # Read a full line, unconditionally
        self.assertEqual(stream.readline(), b'1234\n')
        # Read a number of characters less than a line
        self.assertEqual(stream.readline(2), b'56')
        # Read the rest of the partial line
        self.assertEqual(stream.readline(), b'78\n')
        # Read a full line, with a character limit greater than the line length
        self.assertEqual(stream.readline(6), b'abcd\n')
        # Read the next line, deliberately terminated at the line end
        self.assertEqual(stream.readline(4), b'efgh')
        # Read the next line... just the line end
        self.assertEqual(stream.readline(), b'\n')
        # Read everything else.
        self.assertEqual(stream.readline(), b'ijkl')

        # Regression for #15018
        # If a stream contains a newline, but the provided length
        # is less than the number of provided characters, the newline
        # doesn't reset the available character count
        stream = LimitedStream(BytesIO(b'1234\nabcdef'), 9)
        self.assertEqual(stream.readline(10), b'1234\n')
        self.assertEqual(stream.readline(3), b'abc')
        # Now expire the available characters
        self.assertEqual(stream.readline(3), b'd')
        # Reading again returns nothing.
        self.assertEqual(stream.readline(2), b'')

        # Same test, but with read, not readline.
        stream = LimitedStream(BytesIO(b'1234\nabcdef'), 9)
        self.assertEqual(stream.read(6), b'1234\na')
        self.assertEqual(stream.read(2), b'bc')
        self.assertEqual(stream.read(2), b'd')
        self.assertEqual(stream.read(2), b'')
        self.assertEqual(stream.read(), b'')

    def test_stream(self):
        payload = FakePayload('name=value')
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': payload},
        )
        self.assertEqual(request.read(), b'name=value')

    def test_read_after_value(self):
        """
        Reading from request is allowed after accessing request contents as
        POST or body.
        """
        payload = FakePayload('name=value')
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': payload,
        })
        self.assertEqual(request.POST, {'name': ['value']})
        self.assertEqual(request.body, b'name=value')
        self.assertEqual(request.read(), b'name=value')

    def test_value_after_read(self):
        """
        Construction of POST or body is not allowed after reading
        from request.
        """
        payload = FakePayload('name=value')
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': payload,
        })
        self.assertEqual(request.read(2), b'na')
        with self.assertRaises(RawPostDataException):
            request.body
        self.assertEqual(request.POST, {})

    def test_non_ascii_POST(self):
        payload = FakePayload(urlencode({'key': 'España'}))
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_LENGTH': len(payload),
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'wsgi.input': payload,
        })
        self.assertEqual(request.POST, {'key': ['España']})

    def test_alternate_charset_POST(self):
        """
        Test a POST with non-utf-8 payload encoding.
        """
        payload = FakePayload(urlencode({'key': 'España'.encode('latin-1')}))
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_LENGTH': len(payload),
            'CONTENT_TYPE': 'application/x-www-form-urlencoded; charset=iso-8859-1',
            'wsgi.input': payload,
        })
        self.assertEqual(request.POST, {'key': ['España']})

    def test_body_after_POST_multipart_form_data(self):
        """
        Reading body after parsing multipart/form-data is not allowed
        """
        # Because multipart is used for large amounts of data i.e. file uploads,
        # we don't want the data held in memory twice, and we don't want to
        # silence the error by setting body = '' either.
        payload = FakePayload("\r\n".join([
            '--boundary',
            'Content-Disposition: form-data; name="name"',
            '',
            'value',
            '--boundary--'
            '']))
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'multipart/form-data; boundary=boundary',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': payload,
        })
        self.assertEqual(request.POST, {'name': ['value']})
        with self.assertRaises(RawPostDataException):
            request.body

    def test_body_after_POST_multipart_related(self):
        """
        Reading body after parsing multipart that isn't form-data is allowed
        """
        # Ticket #9054
        # There are cases in which the multipart data is related instead of
        # being a binary upload, in which case it should still be accessible
        # via body.
        payload_data = b"\r\n".join([
            b'--boundary',
            b'Content-ID: id; name="name"',
            b'',
            b'value',
            b'--boundary--'
            b''])
        payload = FakePayload(payload_data)
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'multipart/related; boundary=boundary',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': payload,
        })
        self.assertEqual(request.POST, {})
        self.assertEqual(request.body, payload_data)

    def test_POST_multipart_with_content_length_zero(self):
        """
        Multipart POST requests with Content-Length >= 0 are valid and need to be handled.
        """
        # According to:
        # https://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.13
        # Every request.POST with Content-Length >= 0 is a valid request,
        # this test ensures that we handle Content-Length == 0.
        payload = FakePayload("\r\n".join([
            '--boundary',
            'Content-Disposition: form-data; name="name"',
            '',
            'value',
            '--boundary--'
            '']))
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'multipart/form-data; boundary=boundary',
            'CONTENT_LENGTH': 0,
            'wsgi.input': payload,
        })
        self.assertEqual(request.POST, {})

    def test_POST_binary_only(self):
        payload = b'\r\n\x01\x00\x00\x00ab\x00\x00\xcd\xcc,@'
        environ = {
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'application/octet-stream',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': BytesIO(payload),
        }
        request = WSGIRequest(environ)
        self.assertEqual(request.POST, {})
        self.assertEqual(request.FILES, {})
        self.assertEqual(request.body, payload)

        # Same test without specifying content-type
        environ.update({'CONTENT_TYPE': '', 'wsgi.input': BytesIO(payload)})
        request = WSGIRequest(environ)
        self.assertEqual(request.POST, {})
        self.assertEqual(request.FILES, {})
        self.assertEqual(request.body, payload)

    def test_read_by_lines(self):
        payload = FakePayload('name=value')
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': payload,
        })
        self.assertEqual(list(request), [b'name=value'])

    def test_POST_after_body_read(self):
        """
        POST should be populated even if body is read first
        """
        payload = FakePayload('name=value')
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': payload,
        })
        request.body  # evaluate
        self.assertEqual(request.POST, {'name': ['value']})

    def test_POST_after_body_read_and_stream_read(self):
        """
        POST should be populated even if body is read first, and then
        the stream is read second.
        """
        payload = FakePayload('name=value')
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': payload,
        })
        request.body  # evaluate
        self.assertEqual(request.read(1), b'n')
        self.assertEqual(request.POST, {'name': ['value']})

    def test_POST_after_body_read_and_stream_read_multipart(self):
        """
        POST should be populated even if body is read first, and then
        the stream is read second. Using multipart/form-data instead of urlencoded.
        """
        payload = FakePayload("\r\n".join([
            '--boundary',
            'Content-Disposition: form-data; name="name"',
            '',
            'value',
            '--boundary--'
            '']))
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'multipart/form-data; boundary=boundary',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': payload,
        })
        request.body  # evaluate
        # Consume enough data to mess up the parsing:
        self.assertEqual(request.read(13), b'--boundary\r\nC')
        self.assertEqual(request.POST, {'name': ['value']})

    def test_POST_immutable_for_mutipart(self):
        """
        MultiPartParser.parse() leaves request.POST immutable.
        """
        payload = FakePayload("\r\n".join([
            '--boundary',
            'Content-Disposition: form-data; name="name"',
            '',
            'value',
            '--boundary--',
        ]))
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'multipart/form-data; boundary=boundary',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': payload,
        })
        self.assertFalse(request.POST._mutable)

    def test_multipart_without_boundary(self):
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'multipart/form-data;',
            'CONTENT_LENGTH': 0,
            'wsgi.input': FakePayload(),
        })
        with self.assertRaisesMessage(MultiPartParserError, 'Invalid boundary in multipart: None'):
            request.POST

    def test_multipart_non_ascii_content_type(self):
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'multipart/form-data; boundary = \xe0',
            'CONTENT_LENGTH': 0,
            'wsgi.input': FakePayload(),
        })
        msg = 'Invalid non-ASCII Content-Type in multipart: multipart/form-data; boundary = à'
        with self.assertRaisesMessage(MultiPartParserError, msg):
            request.POST

    def test_POST_connection_error(self):
        """
        If wsgi.input.read() raises an exception while trying to read() the
        POST, the exception is identifiable (not a generic OSError).
        """
        class ExplodingBytesIO(BytesIO):
            def read(self, len=0):
                raise OSError('kaboom!')

        payload = b'name=value'
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': ExplodingBytesIO(payload),
        })
        with self.assertRaises(UnreadablePostError):
            request.body

    def test_set_encoding_clears_POST(self):
        payload = FakePayload('name=Hello Günter')
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': payload,
        })
        self.assertEqual(request.POST, {'name': ['Hello Günter']})
        request.encoding = 'iso-8859-16'
        self.assertEqual(request.POST, {'name': ['Hello GĂŒnter']})

    def test_set_encoding_clears_GET(self):
        request = WSGIRequest({
            'REQUEST_METHOD': 'GET',
            'wsgi.input': '',
            'QUERY_STRING': 'name=Hello%20G%C3%BCnter',
        })
        self.assertEqual(request.GET, {'name': ['Hello Günter']})
        request.encoding = 'iso-8859-16'
        self.assertEqual(request.GET, {'name': ['Hello G\u0102\u0152nter']})

    def test_FILES_connection_error(self):
        """
        If wsgi.input.read() raises an exception while trying to read() the
        FILES, the exception is identifiable (not a generic OSError).
        """
        class ExplodingBytesIO(BytesIO):
            def read(self, len=0):
                raise OSError('kaboom!')

        payload = b'x'
        request = WSGIRequest({
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'multipart/form-data; boundary=foo_',
            'CONTENT_LENGTH': len(payload),
            'wsgi.input': ExplodingBytesIO(payload),
        })
        with self.assertRaises(UnreadablePostError):
            request.FILES

    def test_get_raw_uri(self):
        factory = RequestFactory(HTTP_HOST='evil.com')
        request = factory.get('////absolute-uri')
        self.assertEqual(request.get_raw_uri(), 'http://evil.com//absolute-uri')

        request = factory.get('/?foo=bar')
        self.assertEqual(request.get_raw_uri(), 'http://evil.com/?foo=bar')

        request = factory.get('/path/with:colons')
        self.assertEqual(request.get_raw_uri(), 'http://evil.com/path/with:colons')

class BuildAbsoluteURITests(SimpleTestCase):
    factory = RequestFactory()

    def test_absolute_url(self):
        request = HttpRequest()
        url = 'https://www.example.com/asdf'
        self.assertEqual(request.build_absolute_uri(location=url), url)

    def test_host_retrieval(self):
        request = HttpRequest()
        request.get_host = lambda: 'www.example.com'
        request.path = ''
        self.assertEqual(
            request.build_absolute_uri(location='/path/with:colons'),
            'http://www.example.com/path/with:colons'
        )

    def test_request_path_begins_with_two_slashes(self):
        # //// creates a request with a path beginning with //
        request = self.factory.get('////absolute-uri')
        tests = (
            # location isn't provided
            (None, 'http://testserver//absolute-uri'),
            # An absolute URL
            ('http://example.com/?foo=bar', 'http://example.com/?foo=bar'),
            # A schema-relative URL
            ('//example.com/?foo=bar', 'http://example.com/?foo=bar'),
            # Relative URLs
            ('/foo/bar/', 'http://testserver/foo/bar/'),
            ('/foo/./bar/', 'http://testserver/foo/bar/'),
            ('/foo/../bar/', 'http://testserver/bar/'),
            ('///foo/bar/', 'http://testserver/foo/bar/'),
        )
        for location, expected_url in tests:
            with self.subTest(location=location):
                self.assertEqual(request.build_absolute_uri(location=location), expected_url)


unittest.main()