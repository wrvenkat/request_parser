import os, inspect

def get_abs_path(dir=''):
    """
    Return absolute path of current directory.
    """
    #for relative path
    curr_filename = inspect.getframeinfo(inspect.currentframe()).filename
    curr_path = os.path.dirname(os.path.abspath(curr_filename))
    curr_path = curr_path+"/"+dir+"/"

    return curr_path