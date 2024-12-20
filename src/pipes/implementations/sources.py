import asyncio
from functools import wraps
from typing import TypeVar

# NOTE: Unused imports are so other addons can import them from here
from pipes.core.signature import Signature, Par, get_signature, with_signature
from pipes.core.state import Context
from pipes.core.pipe import Source, Sources


#######################################################
#                     Decorations                     #
#######################################################

def multi_source(func):
    '''
    Decorates a function to take an argument 'n' that simply asynchronously calls the function multiple times.

    f: (*args) -> y      becomes     f': (*args, n=1) -> [y]
    e.g.
    rand()   -> 0.1      becomes     rand'(n=3) -> [0.5, 0.2, 0.3]
    '''
    @wraps(func)
    async def _multi_source(*args, n, **kwargs):
        return await asyncio.gather(*(func(*args, **kwargs) for i in range(n)))
    return _multi_source

def get_which(get_what):
    '''
    Takes a function
        get_what(items: Iterator[X], what: T) -> results: list[Y]
    where `items` and `results` have equal length (i.e. one result per item)
    and extends it to
        get_which(items: Iterator[X], which: Iterator[T]) -> results: list[Y]
    and results has length (#items × #which) ordered so that it's first the attributes of item 1, then the attributes of item 2, etc.
    '''
    def _get_which(item, which):
        w = ( get_what(item, what) for what in which )
        return [x for y in zip(*w) for x in y]
    return _get_which

NATIVE_SOURCES = Sources()
'The canonical object storing/indexing all `Source` instances.'

_CATEGORY = 'NONE'

def set_category(category: str):
    global _CATEGORY
    _CATEGORY = category

def source_from_func(signature: dict[str, Par]=None, /, *, command=False, **kwargs):
    '''
    Makes a source out of a function.
    * command: If True, source becomes usable as a standalone bot command (default: False)

    Source-specific keyword arguments:
    * plural: The source's name pluralised, to use as an alias (default: name + 's')
    * depletable: If True, it is allowed to request "ALL" of a source. (e.g. "{all words}" instead of just "{10 words}"),
    in this case `n` will be passed as -1 (default: False)
    '''
    func = None
    if callable(signature):
        (func, signature) = (signature, None)

    def _source_from_func(func):
        global NATIVE_SOURCES, _CATEGORY
        # Name is the function name with the _source bit cropped off
        name = func.__name__.rsplit('_', 1)[0].lower()
        doc = func.__doc__
        # Signature may be set using @with_signature, given directly, or not given at all
        sig = get_signature(func, Signature(signature or {}))
        source = Source(sig, func, name=name, doc=doc, category=_CATEGORY, **kwargs)
        NATIVE_SOURCES.add(source, command)
        return func

    if func: return _source_from_func(func)
    return _source_from_func

T = TypeVar('T')

def source_from_class(cls: type[T]) -> type[T]:
    '''
    Makes a Source out of a class by reading its definition, and either the class' or the method's docstring.
    ```py
    # Fields:
    name: str
    plural: str=None
    aliases: list[str]=None
    depletable: bool=False
    command: bool=False

    # Methods:
    @with_signature(...)
    @staticmethod
    async def source_function(ctx: Context, items: list[str], ...) -> list[str]: ...

    @staticmethod
    def may_use(user: discord.User) -> bool: ...
    ```
    '''
    def get(key, default=None):
        return getattr(cls, key, default)

    source = Source(
        get_signature(cls.source_function),
        cls.source_function,
        name=cls.name,
        plural=get('plural'),
        doc=cls.__doc__ or cls.source_function.__doc__,
        category=_CATEGORY,
        aliases=get('aliases'),
        depletable=get('depletable', False),
        may_use=get('may_use'),
    )
    NATIVE_SOURCES.add(source, get('command', False))
    return cls


#####################################################
#                      Sources                      #
#####################################################

from . import sources_discord
from . import sources_bot
from . import sources_file
from . import sources_quotes
from . import sources_etc
from . import sources_wikipedia
