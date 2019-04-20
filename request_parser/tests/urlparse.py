from request_parser.utils import http
from request_parser.http.request import InvalidHttpRequest

def urlparsetest():
    test1_url = "/path-to/a-file.html?key1=val1&key2=val2"

    result1 = http._urlparse(test1_url)
    print result1

def request_line_parse(request_line=''):
    """
    Parse the request line in an HTTP/HTTP Proxy request and return a dictionary with 8 entries:
    <METHOD> <SCHEME>://<DOMAIN>/<PATH>;<PARAMS>?<QUERY>#<FRAGMENT> <PROTOCOL_INFO>
    """

    method, uri, protoccol_version = request_line.split(' ',3)

    if method is None or uri is None or protoccol_version is None:
        raise InvalidHttpRequest("Invalid request line.")
    
    request_uri_result = http._urlparse(uri)
    request_line_result = {}
    request_line_result['SCHEME'] = request_uri_result[0]
    request_line_result['DOMAIN'] = request_uri_result[1]
    request_line_result['PATH'] = request_uri_result[2]
    request_line_result['PARAMS'] = request_uri_result[3]
    request_line_result['QUERY'] = request_uri_result[4]
    request_line_result['FRAGMENT'] = request_uri_result[5]
    request_line_result['METHOD'] = method
    request_line_result['PROTOCOL_INFO'] = protoccol_version

    return request_line_result

def request_line_parse_test():
    request_line1 = "GET /path-to/a-file.html?key1=val1&key2=val2 HTTP/1.1"

    result1 = request_line_parse(request_line1)
    print result1

urlparsetest()
request_line_parse_test()