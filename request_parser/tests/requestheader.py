from request_parser.http.request import HttpRequest
from request_parser.http.constants import MetaDict
from request_parser.files.utils import get_abs_path

def requestparser():
    curr_dir = "request parse test files"
    curr_dir = get_abs_path(curr_dir)

    get_request1 = "get-request1.txt"
    get_request1 = curr_dir+get_request1
    stream1 = ''

    with open(get_request1, 'r') as stream1:
        try:
            http_get_request1 = HttpRequest(stream1)
            http_get_request1.parse_request_header()
            print "Method: "+http_get_request1.method
            print "Scheme is: "+http_get_request1.scheme
            print "Path is: "+http_get_request1.path
            print "Protocol info: "+http_get_request1.protocol_info
            print "Host is: "+http_get_request1.get_host()
            print "Port is: "+http_get_request1.get_port()
            print "Encoding is: "+http_get_request1.encoding
            print "Content-Type is: "+http_get_request1.content_type
            print "Request URI is: "+http_get_request1.get_uri(raw=True)
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