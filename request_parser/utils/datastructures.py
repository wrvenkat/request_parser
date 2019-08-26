import copy
from io import BytesIO

from request_parser.exceptions.exceptions import SuspiciousMultipartForm, InputStreamExhausted

class MultiValueDictKeyError(KeyError):
    pass

class MultiValueDict(dict):
    """
    A subclass of dictionary customized to handle multiple values for the
    same key.

    >>> d = MultiValueDict({'name': ['Adrian', 'Simon'], 'position': ['Developer']})
    >>> d['name']
    'Simon'
    >>> d.getlist(b'name')'
    ['Adrian', 'Simon']
    >>> d.getlist(b'doesnotexist')'
    []
    >>> d.getlist(b'doesnotexist', ['Adrian', 'Simon'])'
    ['Adrian', 'Simon']
    >>> d.get('lastname', 'nonexistent')
    'nonexistent'
    >>> d.setlist(b'lastname', ['Holovaty', 'Willison'])'

    This class exists to solve the irritating problem raised by cgi.parse_qs,
    which returns a list for every key, even though most Web forms submit
    single name-value pairs.
    """
    def __init__(self, key_to_list_mapping=()):
        super(MultiValueDict, self).__init__(key_to_list_mapping)

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, super(MultiValueDict, self).__repr__())

    def __getitem__(self, key):
        """
        Return the last data value for this key, or [] if it's an empty list;
        raise KeyError if not found.
        """
        try:
            list_ = super(MultiValueDict, self).__getitem__(key)
        except KeyError:
            raise MultiValueDictKeyError(key)
        try:
            return list_[-1]
        except IndexError:
            return []

    def __setitem__(self, key, value):
        #set the value as a list i.e [value]
        super(MultiValueDict, self).__setitem__(key, [value])

    def __copy__(self):
        #returns a list of tuples of (key, value_list) of MultiValueDict for 
        #a shallow copy
        return self.__class__([
            (k, v[:])
            for k, v in self.lists()
        ])

    def __deepcopy__(self, memo):
        #create an empty instance of MultiValueDict
        result = self.__class__()
        #in the memo dict, set the id(self)'s value as the new instance
        memo[id(self)] = result
        #for each (key, value) tuple in self,
        for key, value in dict.items(self):
            #populate result dictionary with a key : [value] copy
            #where each of key and value are deep copies
            dict.__setitem__(result, copy.deepcopy(key, memo),
                            copy.deepcopy(value, memo))
        return result

    def __getstate__(self):
        #Fixed dictionary comprehension here
        multi_value_state_dict = dict((k, self._getlist(k)) for k in self)
        return {self.__dict__,{'_data': multi_value_state_dict}}

    def __setstate__(self, obj_dict):
        #retrieve the dictionary associated with '_data' key
        #with a default value being an empty dictionary
        data = obj_dict.pop('_data', {})
        #for each (key, value) tuple in data
        for k, v in list(data.items()):
            #create the list with value v for key k
            self.setlist(k, v)
        #update the attribute dictionary from the returned obj_dict
        #the update automatically iterates through the key, value pair in #obj_dict and populates the attributes; since there's no parameter
        #with '_dict' key, that item is ignored.
        self.__dict__.update(obj_dict)

    def get(self, key, default=None):
        """
        Return the last data value for the passed key. If key doesn't exist
        or value is an empty list, return `default`.
        """
        try:
            val = self[key]
        except KeyError:
            return default
        if val == []:
            return default
        return val

    def _getlist(self, key, default=None, force_list=False):
        """
        Return a list of values for the key.

        Used internally to manipulate values list. If force_list is True,
        return a new copy of values.
        """
        try:
            values = super(MultiValueDict, self).__getitem__(key)
        except KeyError:
            if default is None:
                return []
            return default
        else:
            if force_list:
                #return a copy of values as a list
                values = list(values) if values is not None else None
            return values

    def getlist(self, key, default=None):
        """
        Return the list of values for the key. If key doesn't exist, return a
        default value.
        """
        return self._getlist(key, default, force_list=True)

    def setlist(self, key, potential_list):
        """
        sets a list for a key.
        Converts a single value to a list item.        
        """
        list_ = ''
        if potential_list is None:
            list_ = []
        elif type(potential_list) is list:
            list_ = list(potential_list)
        else:
            list_ = [potential_list]
        super(MultiValueDict, self).__setitem__(key, list_)

    def setdefault(self, key, default=None):
        """
        Set the default value for a key if key is not in the dict
        """
        if key not in self:
            self[key] = default
            # Do not return default here because __setitem__() may store
            # another value -- QueryDict.__setitem__() does. Look it up.
        return self[key]

    def setlistdefault(self, key, default_list=None):
        """
        Set a default list for a key if key not in the dict
        """
        if key not in self:
            if default_list is None:
                default_list = []
            self.setlist(key, default_list)
            # Do not return default_list here because setlist() may store
            # another value -- QueryDict.setlist() does. Look it up.
        return self._getlist(key)

    def appendlist(self, key, value):
        """Append an item to the internal list associated with key."""
        self.setlistdefault(key).append(value)

    def items(self):
        """
        Yield (key, value) pairs, where value is the last item in the list
        associated with the key.
        """
        for key in self:
            yield key, self[key]

    def lists(self):
        """Yield (key, list) pairs."""
        return iter(list(super(MultiValueDict, self).items()))

    def values(self):
        """Yield the last value on every key list."""
        for key in self:
            yield self[key]

    def copy(self):
        """Return a shallow copy of this object."""
        return copy.copy(self)

    def update(self, *args, **kwargs):
        """Extend rather than replace existing key lists."""

        #accepts only 1 value for args
        if len(args) > 1:
            raise TypeError("update expected at most 1 argument, got %d" % len(args))
        #if there's only 1 for args, then it's assumed to be a dictionary
        if args:
            other_dict = args[0]
            #if the dictionary is another MultiValueDict,
            if isinstance(other_dict, MultiValueDict):
                #then for each (key, value_list) tuple,
                for key, value_list in other_dict.lists():
                    #the existing one is extended
                    self.setlistdefault(key).extend(value_list)
            #if its not a MultiValueDict,
            else:
                #then assuming it's some dictionary, it's iterated upon
                try:
                    #for each (key, value) tuple in the other_dict,
                    for key, value in list(other_dict.items()):
                        #the existing one is /appended/ since we don't know
                        #the type of the value, we can only append and not
                        #extend
                        self.setlistdefault(key).append(value)
                #if our assumption of other_dict being another dictionary
                #is wrong
                except TypeError:
                    raise ValueError("MultiValueDict.update() takes either a MultiValueDict or dictionary")
        #now we parse the kwargs, which is a dictionary
        #so, for each (key, value) tuple in the kwargs dictionary
        for key, value in list(kwargs.items()):
            #the value for each key is /appended/ since we don't know if value
            #will be another list
            self.setlistdefault(key).append(value)

    def dict(self):
        """Return current object as a dict with singular values."""
        return {key: self[key] for key in self}

class ImmutableList(tuple):
    """
    A tuple-like object that raises useful errors when it is asked to mutate.

    Example::

        >>> a = ImmutableList(range(5), warning="You cannot mutate this.")
        >>> a[3] = '4'
        Traceback (most recent call last):
            ...
        AttributeError: You cannot mutate this.
    """

    #See https://stackoverflow.com/questions/5940180/python-default-keyword-arguments-after-variable-length-positional-arguments
    def __new__(cls, *args, **kwargs):
        warning = kwargs.pop('warning', 'ImmutableList object is immutable.')
        self = tuple.__new__(cls, *args, **kwargs)
        self.warning = warning
        return self

    def complain(self, *wargs, **kwargs):
        if isinstance(self.warning, Exception):
            raise self.warning
        else:
            raise AttributeError(self.warning)

    # All list mutation functions complain.
    __delitem__ = complain
    __delslice__ = complain
    __iadd__ = complain
    __imul__ = complain
    __setitem__ = complain
    __setslice__ = complain
    append = complain
    extend = complain
    insert = complain
    pop = complain
    remove = complain
    sort = complain
    reverse = complain

class ImmutableMultiValueDict(MultiValueDict):
    """
    A subclass of MultivalueDict which is also immutable by default.
    NOTE: The values themselves however are not immutable.
    """

    _mutable = False

    def __init__(self, key_to_list_mapping=()):
        super(ImmutableMultiValueDict, self).__init__(key_to_list_mapping)

    def _assert_mutable(self):
        if not self._mutable:
            raise AttributeError("This ImmutableMultiValueDict instance is immutable.")

    def __setitem__(self, key, value):
        #set the value as a list i.e [value]
        self._assert_mutable()
        super(ImmutableMultiValueDict, self).__setitem__(key, [value])

    def __delitem__(self, key):
        self._assert_mutable()
        super(ImmutableMultiValueDict, self).__delitem__(key)

    def __setstate__(self, obj_dict):
        #retrieve the dictionary associated with '_data' key
        #with a default value being an empty dictionary
        data = obj_dict.pop('_data', {})
        #for each (key, value) tuple in data
        for k, v in list(data.items()):
            #create the list with value v for key k
            super(ImmutableMultiValueDict, self).setlist(k, v)
        #update the attribute dictionary from the returned obj_dict
        #the update automatically iterates through the key, value pair in #obj_dict and populates the attributes; since there's no parameter
        #with '_dict' key, that item is ignored.
        self.__dict__.update(obj_dict)

    def setlist(self, key, potential_list):
        """
        sets a list for a key.
        Converts a single value to a list item.
        """
        self._assert_mutable()
        super(ImmutableMultiValueDict, self).setlist(key, potential_list)

    def setdefault(self, key, default=None):
        """
        Set the default value for a key if key is not in the dict
        """
        self._assert_mutable()
        super(ImmutableMultiValueDict, self).setdefault(key, default)

    def setlistdefault(self, key, default_list=None):
        """
        Set a default list for a key if key not in the dict
        """
        self._assert_mutable()
        super(ImmutableMultiValueDict, self).setlistdefault(key, default_list)

    def appendlist(self, key, value):
        """Append an item to the internal list associated with key."""
        self._assert_mutable()
        super(ImmutableMultiValueDict, self).appendlist(key, value)

    def update(self, *args, **kwargs):
        """Extend rather than replace existing key lists."""
        self._assert_mutable()
        super(ImmutableMultiValueDict, self).update(args, kwargs)

class LazyStream:
    """
    The LazyStream wrapper allows one to get and "unget" bytes from a stream.

    Given a producer object (an iterator that yields bytestrings), the
    LazyStream object will support iteration, reading, and keeping a "look-back"
    variable in case you need to "unget" some bytes.
    """
    def __init__(self, producer, length=None):
        """
        Every LazyStream must have a producer when instantiated.

        A producer is an iterable that returns a string each time it
        is called.
        """
        self._producer = producer
        self._empty = False
        self._leftover = b''
        self.length = length
        self.position = 0
        self._remaining = length
        self._unget_history = []

    def tell(self):
        return self.position

    def read(self, size=None):
        def parts():
            remaining = self._remaining if size is None else size
            # do the whole thing in one shot if no limit was provided.
            if remaining is None:
                yield b''.join(self)
                return

            # otherwise do some bookkeeping to return exactly enough
            # of the stream and stashing any extra content we get from
            # the producer
            while remaining != 0:
                assert remaining > 0, 'remaining bytes to read should never go negative'

                try:
                    chunk = next(self)
                except StopIteration:
                    return
                else:
                    emitting = chunk[:remaining]
                    self.unget(chunk[remaining:])
                    remaining -= len(emitting)
                    yield emitting

        out = b''.join(parts())
        return out

    #def __next__(self):
    def __next__(self):
        """
        Used when the exact number of bytes to read is unimportant.

        Return whatever chunk is conveniently returned from the iterator.
        Useful to avoid unnecessary bookkeeping if performance is an issue.
        """
        if self._leftover:
            output = self._leftover
            self._leftover = b''
        else:
            output = next(self._producer)
            self._unget_history = []
        self.position += len(output)
        return output

    def close(self):
        """
        Used to invalidate/disable this lazy stream.

        Replace the producer with an empty list. Any leftover bytes that have
        already been read will still be reported upon read() and/or next().
        """
        self._producer = []

    def __iter__(self):
        return self

    def unget(self, bytes):
        """
        Place bytes back onto the front of the lazy stream.

        Future calls to read() will return those bytes first. The
        stream position and thus tell() will be rewound.
        """
        if not bytes:
            return
        self._update_unget_history(len(bytes))
        self.position -= len(bytes)
        self._leftover = bytes + self._leftover

    def _update_unget_history(self, num_bytes):
        """
        Update the unget history as a sanity check to see if we've pushed
        back the same number of bytes in one chunk. If we keep ungetting the
        same number of bytes many times (here, 50), we're mostly likely in an
        infinite loop of some sort. This is usually caused by a
        maliciously-malformed MIME request.
        """
        self._unget_history = [num_bytes] + self._unget_history[:49]
        number_equal = len([
            current_number for current_number in self._unget_history
            if current_number == num_bytes
        ])

        if number_equal > 40:
            raise SuspiciousMultipartForm(
                "The multipart parser got stuck, which shouldn't happen with"
                " normal uploaded files. Check for malicious upload activity;"
                " if there is none, report this to the Django developers."
            )

class ChunkIter:
    """
    An iterable that will yield chunks of data. Given a file-like object as the
    constructor, yield chunks of read operations from that object.
    """
    def __init__(self, flo, chunk_size=64 * 1024):
        self.flo = flo
        self.chunk_size = chunk_size

    #def __next__(self):
    def __next__(self):
        try:
            data = self.flo.read(self.chunk_size)
        except InputStreamExhausted:
            raise StopIteration()
        if data:
            return data
        else:
            raise StopIteration()

    def __iter__(self):
        return self
