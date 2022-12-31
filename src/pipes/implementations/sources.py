import asyncio
from collections import defaultdict
from functools import wraps

from discord.ext.commands import Bot

from ..signature import Signature, Par, get_signature, with_signature
from ..pipe import Source, Sources
from resource.variables import VariableStore


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
        get_what(items:List[X], what:T) -> results:List[Y]
    where `items` and `results` have equal length (i.e. one result per item)
    and extends it to
        get_which(items:List[X], which:List[T]) -> results:List[Y]
    and results has length (#items × #which) ordered so that it's first the attributes of item 1, then the attributes of item 2, etc.
    '''
    def _get_which(item, which):
        w = [ get_what(item, what) for what in which ]
        return [x for y in zip(*w) for x in y]
    return _get_which

sources = Sources()
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
    * pass_message: If True, function receives the discord Message as its first argument (default: False)
    * plural: The source's name pluralised, to use as an alias (default: name + 's')
    * depletable: If True, it is allowed to request "ALL" of a source. (e.g. "{all words}" instead of just "{10 words}"),
    in this case `n` will be passed as -1 (default: False)
    '''
    func = None
    if callable(signature):
        (func, signature) = (signature, None)

    def _source_from_func(func):
        global sources, _CATEGORY
        # Name is the function name with the _source bit cropped off
        name = func.__name__.rsplit('_', 1)[0].lower()
        doc = func.__doc__
        # Signature may be set using @with_signature, given directly, or not given at all
        sig = get_signature(func, Signature(signature or {}))
        source = Source(sig, func, name=name, doc=doc, category=_CATEGORY, **kwargs)
        sources.add(source, command)
        return func

    if func: return _source_from_func(func)
    return _source_from_func

# TODO: Copy @pipe_from_class to make @source_from_class

def source_from_class(cls: type):
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
    @staticmethod
    @with_signature(...)
    async def source_function(items: list[str], ...) -> list[str]: ...
            
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
        pass_message=True,
        aliases=get('aliases'),
        depletable=get('depletable', False),
        may_use=get('may_use'),
    )
    sources.add(source, get('command', False))


# Add fields here to make them easily accessible (readable and writable) both inside and outside of this file.
class SourceResources:
    bot: Bot = None
    previous_pipeline_output = defaultdict(list)
    variables = VariableStore('variables.json')


#####################################################
#                      Sources                      #
#####################################################

from . import sources_discord
from . import sources_bot
from . import sources_file
from . import sources_quotes
from . import sources_etc
from . import sources_wikipedia
