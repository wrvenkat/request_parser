import os, inspect

from request_parser.http.multipartparser import LazyStream
from request_parser.utils.datastructures import ImmutableMultiValueDict, ImmutableList
import request_parser.conf.settings as settings
from request_parser.http.request import InvalidHttpRequest

request_stream = ''
max_header_size = 64

def parse_headers(request_header_stream):
    """
    Parse the request header's individual headers into key, value-list
    pairs and return them.
    """
    request_line = ''
    request_headers = {}
    start = 0

    end = request_header_stream.find(b'\r\n', 1)
    if end != -1:
        request_line = request_header_stream[start:end]
    else:
        raise InvalidHttpRequest("Invalid request.")
    end+=2
    request_header_stream = request_header_stream[end:]
    start = 0
    
    #iterate through each header line
    end = request_header_stream.find(b'\r\n', 1)
    while end != -1:
        request_header = request_header_stream[start:end]
        end += 2
        request_header_stream = request_header_stream[end:]
        start = 0

        #parse the request header
        end_index = request_header.find(b':')
        if end_index != -1:
            header =  request_header[:end_index]
            header = header.encode('ascii','')
            value = request_header[end_index+1:]
            value = value.strip()
            value = value.encode('ascii','')
            if header in request_headers:
                request_headers[header].append(value)
            else:
                request_headers[header] = list()
                request_headers[header].append(value)
        else:
            raise InvalidHttpRequest("Invalid request header: {}".format(header))
        end = request_header_stream.find(b'\r\n', 1)
    
    #sanity check
    if len(request_headers) == 0:
        raise InvalidHttpRequest("Invalid request.")
    
    #construct an immutable version of MultiValueDict for the request headers
    request_headers = ImmutableMultiValueDict(request_headers)
    
    return request_line, request_headers

def parse_header_bootstrap(request):
    request_stream = LazyStream(request)
    request_header = ''

    #read until we find a '\r\n\r\n' sequence
    request_header_end = -1
    while request_header_end == -1:
        chunk = request_stream.read(settings.MAX_HEADER_SIZE)
        request_header_end = chunk.find(b'\r\n\r\n')
        if request_header_end != -1:
            request_header += chunk[:request_header_end]
        else:
            request_header += chunk
    request_header+= b'\r\n'
    
    #sanity check
    if request_header_end == -1:
        raise InvalidHttpRequest("Invalid HTTP request header.")

    #accommodate for '\r\n\r\n'
    request_header_end += 4
    #put back anything starting from the request body
    #back onto the stream
    request_stream.unget(chunk[request_header_end:])

    #parse the request header
    return parse_headers(request_header)

def parse_test():
    #for relative path
    curr_filename = inspect.getframeinfo(inspect.currentframe()).filename
    curr_path = os.path.dirname(os.path.abspath(curr_filename))
    
    test_dir = "headers test files/"
    test_file1 = test_dir + "headers-test1.txt"
    test_file1 = curr_path+"/"+test_file1
    stream1 = ''    

    with open(test_file1, 'r') as stream1:
        try:
            request_line, headers = parse_header_bootstrap(stream1)
            print "Request_line is : {}".format(request_line)
            print headers

            #This should raise an error
            #headers['Content-Type'] = list()
            #This should also raise an error
            print headers.getlist('Cookies')
            headers.setlist('Cookies', ['new-cookie1=new-value1', 'new-cookie2=vew-value2'])
        except Exception as e:
            print "Exception is: {}".format(e)

parse_test()