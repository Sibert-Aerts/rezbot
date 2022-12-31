import re

'''
In this file, a "type" is an object which has a __name__ field and a __call__ method
    of type (str -> T), which may also raise errors for poorly formed input strings.
e.g. `str`, `int` and `float` are "types", but also any function (str -> T) is a "type".
The two classes below can be used to instantiate simple new "types" as well.
'''

#####################################################
#                   Type Functions                  #
#####################################################

from utils.util import parse_bool

# Wrapper around re.compile so that the name shows up as "regex"
def regex(*args, **kwargs):
    return re.compile(*args, **kwargs)

def bool_or_none(val: str):
    if val is None or val == 'None':
        return None
    return(parse_bool(val))

class Hex(int):
    def __new__(cls, val: str):
        if not isinstance(val, str):
            return super().__new__(cls, val)
        if val and val[0] == '#':
            val = val[1:]
        elif val and val[:2] == '0x':
            val = val[2:]
        return super().__new__(cls, val, base=16)

    def __repr__(self):
        return hex(self)

def url(s: str):
    if len(s) > 2 and s[0] == '<' and s[-1] == '>':
        return s[1:-1]
    return s


#####################################################
#                   Type Factories                  #
#####################################################

class Option:
    '''
    An Option object behaves like a "type" for parsing enums from strings, returning enum-like objects.
    By default it is case insensitive, and will normalise all names to lowercase.
    * Set `prefer_upper=True` to instead normalise all names to uppercase.
    * Set `case_sensitive=True` to instead be case sensitive.
    * Set `stringy=True` it will return regular strings instead of enum-like objects. True

    Examples:
        >>> Color = Option('red', 'green', 'blue', name='color')
        >>> Color.red
        red
        >>> Color('red') is Color.red
        True
        >>> 'red' == Color.red
        False
        >>> Color('magenta')
        ValueError: Unknown color: "magenta"


        >>> Color2 = Color + ['cyan', 'magenta', 'yellow']
        >>> Color2('magenta') == Color2.magenta
        True
        >>> Color2.red == Color.red
        False
        
    ----
    With `stringy=True`, it essentially acts as a filter/normaliser for a set of strings.
        >>> Color = Option('red', 'green', 'blue', stringy=True)
        >>> Color('red') == Color.red == 'red'
        True
    '''

    class Str:
        ''' The str-like class representing a specific possible option. '''
        def __init__(self, str): self.str = str
        def __repr__(self): return self.str
        def __str__(self): return self.str

    def __init__(self, *options, name='option', case_sensitive=False, prefer_upper=False, stringy=False):
        self.__name__ = name
        self._case_sens = case_sensitive
        self._stringy = stringy
        self._pref_upp = prefer_upper

        if not case_sensitive:
            options = [opt.upper() if prefer_upper else opt.lower() for opt in options]
        self._options = options
        for option in self._options:
            setattr(self, option, option if stringy else Option.Str(option))
        
    def __call__(self, text):
        if not self._case_sens: text = text.upper() if self._pref_upp else text.lower()
        if hasattr(self, text):
            return getattr(self, text)
        if len(self._options) <= 8:
            raise ValueError(f'Must be one of {"/".join(self._options)}')
        raise ValueError(f'Unknown {self.__name__} "{text}"')

    def __add__(self, other):
        if isinstance(other, list):
            return Option(*self._options, *other, name=self.__name__, case_sensitive=self._case_sens, stringy=self._stringy)
        raise Exception('Option can only be added to list')

    def __iter__(self):
        return self._options.__iter__()


class Multi:
    '''
    A Multi object wraps a "type" to be a comma (or otherwise) separated list of said type.
    The output type is a list but with __repr__ changed to resemble the original input.

    >>> intList = Multi(int)
    >>> intList('10,20,30') == [10, 20, 30]
    True
    >>> intList('10,20,30')
    10,20,30
    '''

    class List(list):
        def __init__(self, sep, *a, **kw):
            super().__init__(self, *a, **kw)
            self.sep = sep
        def __repr__(self): return self.sep.join(str(s) for s in self)

    def __init__(self, type, sep=','):
        self.__name__ = type.__name__ + ' list'
        self.type = type
        self.sep = sep

    def __call__(self, text: str):
        out = Multi.List(self.sep)
        for item in text.split(self.sep):
            try:
                out.append(self.type(item))
            except Exception as e:
                if isinstance(self.type, Option) and len(self.type._options) <= 8:
                    raise ValueError(f'Must be a sequence of items from {"/".join(self.type._options)} separated by "{self.sep}"s.')
                raise ValueError(f'"{item}" must be of type {self.type.__name__} ({e})')
        return out
