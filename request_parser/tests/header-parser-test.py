import os, inspect

from request_parser.http.multipartparser import LazyStream
from request_parser.utils.datastructures import MultiValueDict

request_stream = ''
max_header_size = 64

def parse_headers(request_header_stream):
    """
    Parse the request header's individual headers into key, value-list
    pairs and return them.
    """
    request_header = ''
    request_headers = {}
    
    start = 0
    end = request_header_stream.find(b'\r\n', 1)
    if end:
        #TODO: parse the first line of the request
        request_line = request_header_stream[start:end]
    end+=2
    request_header_stream = request_header_stream[end:]
    start = 0
    
    end = request_header_stream.find(b'\r\n', 1)
    while end != -1:
        request_header = request_header_stream[start:end]
        end += 2
        request_header_stream = request_header_stream[end:]
        start = 0

        #parse the request header
        #TODO: Use MultiValueDict
        end_index = request_header.find(b':')
        if end_index:
            header =  request_header[:end_index]
            header = header.encode('ascii','')
            value = request_header[end_index+1:]
            value = value.strip()
            value = value.encode('ascii','')
            if header in request_headers:
                header.append(value)
            else:
                request_headers[header] = list()
                request_headers[header].append(value)
        else:
            #TODO: raise error
            break
        
        end = request_header_stream.find(b'\r\n', 1)        

    return request_headers

def parse_header_bootstrap(request):
    request_stream = LazyStream(request)
    request_header = ''

    #read until we find a '\r\n\r\n' sequence
    request_header_end = -1
    while request_header_end == -1:
        chunk = request_stream.read(max_header_size)
        request_header_end = chunk.find(b'\r\n\r\n')
        if request_header_end != -1:
            request_header += chunk[:request_header_end]
        else:
            request_header += chunk
    request_header+= b'\r\n'
    
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
            headers = parse_header_bootstrap(stream1)            
            print "Done parsing!"
            print headers
        except Exception as e:
            print "Exception is: {}".format(e)

parse_test()