import asyncio
from collections import defaultdict
from functools import wraps

from discord.ext.commands import Bot

from ..signature import Signature
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

sources.command_sources = []
_CATEGORY = 'NONE'

def set_category(category: str):
    global _CATEGORY
    _CATEGORY = category

def make_source(signature, *, command=False, **kwargs):
    '''
    Makes a source out of a function.

    Keyword arguments:
    * command: If True, source becomes usable as a standalone bot command (default: False)
    * pass_message: If True, function receives the discord Message as its first argument (default: False)
    * plural: The source's name pluralised, to use as an alias (default: name + 's')
    * depletable: If True, it is allowed to request "ALL" of a source. (e.g. "{all words}" instead of just "{10 words}"),
    in this case `n` will be passed as -1 (default: False)
    '''
    def _make_source(func):
        global sources, _CATEGORY
        source = Source(Signature(signature), func, category=_CATEGORY, **kwargs)
        sources.add(source)
        if command:
            sources.command_sources.append(source)
        return func
    return _make_source

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