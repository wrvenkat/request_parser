from request_parser.http.request import HttpRequest
from request_parser.http.constants import MetaDict
import testutils

def requestparser():
    curr_dir = "request parse test files"
    curr_dir = testutils.get_abs_path(curr_dir)

    put_multipart_request = "complex-request1.txt"
    put_multipart_request = curr_dir+put_multipart_request
    stream = ''

    with open(put_multipart_request, 'r') as stream:
        try:
            http_get_request1 = HttpRequest(stream)
            http_get_request1.parse()
            print "Method: "+http_get_request1.method
            print "Scheme is: "+http_get_request1.scheme
            print "Path is: "+http_get_request1.path
            print "Protocol info: "+http_get_request1.protocol_info
            print "Host is: "+http_get_request1.get_host()
            print "Port is: "+http_get_request1.get_port()
            print "Encoding is: "+http_get_request1._encoding
            print "Content-Type is: "+http_get_request1.content_type
            print "Request URI is: "+http_get_request1.get_raw_uri()
            print "GET query string dict is: "
            print http_get_request1.GET
            print "Cookies are: "
            print http_get_request1.META[MetaDict.Info.REQ_HEADERS].getlist("Cookies")
            print "Request headers are: "
            print http_get_request1.META['REQUEST_HEADERS']
            print "Request is: "
            print http_get_request1
            
        except Exception as e:
            print "Exception is: {}".format(e)

requestparser()