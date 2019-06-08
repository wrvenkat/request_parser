from request_parser.http.request import HttpRequest
from request_parser.http.constants import MetaDict
from request_parser.files.utils import get_abs_path
import base64

def requestparser():
    curr_dir = "request parse test files"
    curr_dir = get_abs_path(curr_dir)

    put_multipart_request = "complex-request1.txt"
    put_multipart_request = curr_dir+put_multipart_request
    stream = ''

    with open(put_multipart_request, 'r') as stream:
        try:
            http_get_request1 = HttpRequest(stream)
            #http_get_request1.parse_request_header()
            body = http_get_request1.parse()
            print "Method: "+http_get_request1.method
            print "Scheme is: "+http_get_request1.scheme
            print "Path is: "+http_get_request1.path
            print "Protocol info: "+http_get_request1.protocol_info
            print "Host is: "+http_get_request1.get_host()
            print "Port is: "+http_get_request1.get_port()
            print "Encoding is: "+http_get_request1.encoding
            print "Content-Type is: "+http_get_request1.content_type
            print "Request URI is: "+http_get_request1.get_uri()
            print "GET query string dict is: "
            print http_get_request1.GET
            print "Cookies are: "
            print http_get_request1.META[MetaDict.Info.REQ_HEADERS].getlist("Cookies")
            print "Request headers are: "
            print http_get_request1.META['REQUEST_HEADERS']
            print "Request is: "
            print http_get_request1
            files = http_get_request1.FILES
            print_files_details(files)
            #print "Body is: "+body
            
        except Exception as e:
            print "Exception is: {}".format(e)

def print_files_details(files):
    """
    Prints details of files in the MultiValueDict files.
    """
    for name, _files in files.lists():
        for _file in _files:
            print "Filename is: "+name
            print "Uploaded name is: "+_file.name
            print "Uploaded file size: "+str(_file.size)
            print "File content-type: "+_file.content_type
            _file = _file.open()
            chunk = _file.read(100)
            output = base64.b64encode(chunk)
            print "First hundred bytes of file Base64 encoded: "+str(output)
    
requestparser()