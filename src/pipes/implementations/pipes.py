import re
from functools import wraps

from ..signature import Signature
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

pipes.command_pipes = []
_CATEGORY = 'NONE'

def set_category(category: str):
    global _CATEGORY
    _CATEGORY = category

def make_pipe(signature, command=False, may_use=None):
    '''Makes a Pipe out of a function.'''
    def _make_pipe(func):
        global pipes, _CATEGORY
        pipe = Pipe(Signature(signature), func, category=_CATEGORY, may_use=may_use)
        pipes.add(pipe)
        if command:
            pipes.command_pipes.append(pipe)
        return func
    return _make_pipe


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
from . import pipes_maths