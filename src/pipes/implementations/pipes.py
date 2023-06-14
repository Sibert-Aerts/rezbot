import re
from functools import wraps
from typing import Callable, TypeVar

from ..signature import Signature, Par, with_signature, get_signature
from ..pipe import Pipe, Pipes

#######################################################
#                      Decorators                     #
#######################################################

def one_to_one(func):
    '''
    Decorate a function to accept an array of first arguments:
    i.e.
    f: (X, ...) -> Y        becomes     f': (List[X], ...) -> List[Y]
    e.g.
    pow(3, 2) == 9          becomes     pow'([3, 4, 5], 2) == [9, 16, 25]
    '''
    @wraps(func)
    def _one_to_one(input, *args, **kwargs):
        return [func(item, *args, **kwargs) for item in input]
    return _one_to_one

def one_to_many(func):
    '''
    Same as one_to_one except it flattens outputs:
    i.e.
    (X, ...) -> List[Y]     becomes     (List[X], ...) -> List[Y]
    '''
    @wraps(func)
    def _one_to_many(input, *args, **kwargs):
        return [out for item in input for out in func(item, *args, **kwargs)]
    return _one_to_many

def many_to_one(func):
    ''' Doesn't do anything, just a label. '''
    return func

_word_splitter = re.compile(r'([\w\'-]+)') # groups together words made out of letters or ' or -

def word_to_word(func):
    '''
    Decorator allowing a pipe to treat input on a word-by-word basis, with symbols etc. removed.
    '''
    @wraps(func)
    def _word_to_word(line, *args, **kwargs):
        split = re.split(_word_splitter, line)
        for i in range(1, len(split), 2):
            split[i] = func(split[i], *args, **kwargs)
        return ''.join(split)
    return one_to_one(_word_to_word)

pipes = Pipes()
'The canonical object storing/indexing all `Pipe` instances.'

_PIPE_CATEGORY = 'NONE'

def set_category(category: str):
    global _PIPE_CATEGORY
    _PIPE_CATEGORY = category

def pipe_from_func(signature: dict[str, Par]=None, /, *, command=False, **kwargs):
    '''Makes a Pipe out of a function.'''
    func = None
    if callable(signature):
        (func, signature) = (signature, None)

    def _pipe_from_func(func: Callable):
        global pipes, _PIPE_CATEGORY
        # Name is the function name with the _pipe bit cropped off
        name = func.__name__.rsplit('_', 1)[0].lower()
        doc = func.__doc__
        # Signature may be set using @with_signature, given directly, or not given at all
        sig = get_signature(func, Signature(signature or {}))    
        pipe = Pipe(sig, func, name=name, doc=doc, category=_PIPE_CATEGORY, **kwargs)
        pipes.add(pipe, command)
        return func

    if func: return _pipe_from_func(func)
    return _pipe_from_func

T = TypeVar('T')

def pipe_from_class(cls: type[T]) -> type[T]:
    '''
    Makes a Pipe out of a class by reading its definition, and either the class' or the method's docstring.
    ```py
    # Fields:
    name: str
    aliases: list[str]=None
    command: bool=False

    # Methods:
    @with_signature(...)
    @staticmethod
    def pipe_function(items: list[str], ...) -> list[str]: ...

    @staticmethod
    def may_use(user: discord.User) -> bool: ...
    ```
    '''
    def get(key, default=None):
        return getattr(cls, key, default)
    
    pipe = Pipe(
        get_signature(cls.pipe_function),
        cls.pipe_function,
        name=cls.name,
        doc=cls.__doc__ or cls.pipe_function.__doc__,
        category=_PIPE_CATEGORY,
        aliases=get('aliases'),
        may_use=get('may_use'),
    )
    pipes.add(pipe, get('command', False))
    return cls


#####################################################
#                       Pipes                       #
#####################################################

from . import pipes_flow
from . import pipes_string
from . import pipes_meta
from . import pipes_letter
from . import pipes_datamuse
from . import pipes_language
from . import pipes_openai
from . import pipes_encoding
from . import pipes_conversion
from . import pipes_maths
