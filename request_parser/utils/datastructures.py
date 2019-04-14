import copy

class MultiValueDictKeyError(KeyError):
    pass

class MultiValueDict(dict):
    """
    A subclass of dictionary customized to handle multiple values for the
    same key.

    >>> d = MultiValueDict({'name': ['Adrian', 'Simon'], 'position': ['Developer']})
    >>> d['name']
    'Simon'
    >>> d.getlist('name')
    ['Adrian', 'Simon']
    >>> d.getlist('doesnotexist')
    []
    >>> d.getlist('doesnotexist', ['Adrian', 'Simon'])
    ['Adrian', 'Simon']
    >>> d.get('lastname', 'nonexistent')
    'nonexistent'
    >>> d.setlist('lastname', ['Holovaty', 'Willison'])

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
        for k, v in data.items():
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
        TODO: Is this even required? Not sure. Let it be as is for now.
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
        return iter(super(MultiValueDict, self).items())

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
                    for key, value in other_dict.items():
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
        for key, value in kwargs.items():
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
        for k, v in data.items():
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
        TODO: Is this even required? Not sure. Let it be as is for now.
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