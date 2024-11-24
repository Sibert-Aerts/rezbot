'''
This file contains the definitions for the base class Pipeoid and deriving classes Source, Pipe and Spout.
These define the basic model and interface for those scripting entities.
'''

from typing import Callable, Any, Generic, TypeVar
from collections import defaultdict
import inspect
from textwrap import dedent

import discord
from discord import Embed

from .signature import Signature
from .state import Context, SpoutState


class Pipeoid:
    '''
    Base class of Pipe, Source and Spout.
    '''
    name: str
    aliases: list[str]
    category: str | None

    signature: Signature
    doc: str = None
    small_doc: str = None

    def __init__(
        self,
        *,
        signature: Signature,
        name: str,
        aliases: list[str]=None,
        category: str=None,
        doc: str=None,
        may_use: Callable[[discord.User], bool]=None
    ):
        self.name = name
        self.aliases = aliases or []
        if name in self.aliases: self.aliases.remove(name)
        self.category = category
        self.signature = signature
        if doc:
            self.doc = dedent(doc).strip()
            self.small_doc = self.doc.split('\n', 1)[0]
        if may_use:
            self.may_use = may_use

    # ======================================= SCRIPTING API =======================================

    def may_use(self, user):
        return True

    # ======================================= REPRESENTATION ======================================

    def __repr__(self):
        '''Returns the internally-facing qualified name, e.g. `Pipe:repeat`'''
        return type(self).__name__ + ':' + self.name

    def __str__(self):
        '''Returns the human-facing qualified name, e.g. `Pipe: repeat`'''
        return type(self).__name__ + ': ' + self.name

    def get_command_doc(self):
        out = self.doc or ''
        if self.signature:
            out += '\nParameters:\n'
            out += '\n'.join(f'• {s.simple_str()}' for s in self.signature.values())
        return out

    def _get_github_url(self, func: 'function'):
        while getattr(func, '__wrapped__', False):
            func = func.__wrapped__
        code = func.__code__
        file_path = code.co_filename.replace('\\', '/')
        line = code.co_firstlineno
        if (i := file_path.find('/src/pipes/')) > 0:
            return f'https://github.com/sibert-aerts/rezbot/blob/master{file_path[i:]}#L{line}'
        return None

    def get_source_code_url(self):
        return None

    def embed(self, bot: discord.Client=None, **kwargs):
        ''' Build an embed to display in Discord. '''
        title = str(self)
        if self.aliases:
            title += ' (' + ', '.join(self.aliases) + ')'

        description = self.doc or ''
        if (source_url := self.get_source_code_url()):
            description += f'\n[(View source)]({source_url})'

        embed = Embed(title=title, description=description, color=0xfdca4b)

        if self.signature:
            sig = '\n'.join(str(self.signature[s]) for s in self.signature)
            embed.add_field(name='Parameters', value=sig, inline=False)

        if bot:
            embed.set_footer(text=bot.user.name, icon_url=bot.user.avatar)

        return embed


class Pipe(Pipeoid):
    '''
    Represents a functional function that can be used in a script.
    '''
    pipe_function: Callable[..., list[str]]
    is_coroutine: bool

    def __init__(self, signature: Signature, function: Callable[..., list[str]], **kwargs):
        super().__init__(signature=signature, **kwargs)

        self.pipe_function = function
        self.is_coroutine = inspect.iscoroutinefunction(function)

    async def apply(self, items: list[str], **args) -> list[str]:
        ''' Apply the pipe to a list of items. '''
        # TODO: Call may_use here?
        if self.is_coroutine:
            return await self.pipe_function(items, **args)
        else:
            return self.pipe_function(items, **args)

    def get_source_code_url(self):
        return self._get_github_url(self.pipe_function)


class Source(Pipeoid):
    '''
    Represents something which generates strings in a script.
    '''
    source_function: Callable[..., list[str]]
    depletable: bool
    plural: str | None = None

    def __init__(self, signature: Signature, function: Callable[..., list[str]], *, plural: str=None, depletable=False, **kwargs):
        super().__init__(signature=signature, **kwargs)
        self.source_function = function
        self.depletable = depletable

        if plural:
            self.plural = plural.lower()
        elif plural is not False and 'n' in signature:
            self.plural = self.name + 's'
        if self.plural and self.plural != self.name:
            self.aliases.insert(0, self.plural)

    def generate(self, context: Context, args: dict[str, Any], n=None):
        ''' Call the Source to produce items using a parsed dict of arguments. '''
        if n is not None:
            # Handle the `n` that may be given using the {n sources} notation
            if isinstance(n, str) and n.lower() == 'all':
                if self.depletable: n = -1
                else: raise ValueError('Requested `all` items but the source is not depletable.')
            if 'n' in args: args['n'] = int(n)
            elif 'N' in args: args['N'] = int(n)
        return self.source_function(context, **args)

    def get_source_code_url(self):
        return self._get_github_url(self.source_function)

    def embed(self, **kwargs):
        embed = super().embed(**kwargs)
        if self.depletable:
            embed.title += ' `depletable`'
        return embed


class Spout(Pipeoid):
    '''
    Represents something which strictly performs side-effects in a script.
    '''
    class Mode:
        simple = object()
        '''Spout which straightforwardly receives one set of values and args in its callback.'''
        aggregated = object()
        '''Spout which acts based on the complete SpoutState in its callback.'''

    spout_function: Callable[..., None]
    mode: Mode = Mode.simple

    def __init__(self, signature: Signature, function: Callable[..., None], mode: Mode=None, **kwargs):
        super().__init__(signature=signature, **kwargs)
        self.spout_function = function
        self.mode = mode or self.mode

    def get_source_code_url(self):
        return self._get_github_url(self.spout_function)

    def hook(self, spout_state: SpoutState, items: list[str], **args):
        if self.mode == Spout.Mode.simple:
            # Classic system: Spouts that are simply independent function calls at the end of execution
            spout_state.add_simple_callback(self, items, args)

        elif self.mode == Spout.Mode.aggregated:
            # New system: Spouts can work on the aggregated data from multiple calls
            spout_state.add_aggregated_callback(self, items, args)

        else:
            raise Exception(f'Spout {self.name} has invalid mode.')

    async def do_simple_callback(self, bot: discord.Client, context: Context, values: list[str], **args):
        '''Instantly performs a simple spout callback.'''
        if self.mode == Spout.Mode.simple:
            await self.spout_function(context, values, **args)
        elif self.mode == Spout.Mode.aggregated:
            await self.spout_function(context, [(values, args)])


P = TypeVar('P', bound=Pipeoid)

class PipeoidStore(Generic[P]):
    ''' A class for storing/mapping multiple Pipeoid instances. '''
    _name_singular = 'Pipeoid'
    _name_plural = 'Pipeoids'

    by_name: dict[str, P]
    by_primary_name: dict[str, P]
    categories: defaultdict[str, list[P]]
    commands: list[P]

    def __init__(self):
        self.by_name = {}
        self.by_primary_name = {}
        self.categories = defaultdict(list)
        self.commands = []

    def add(self, pipeoid: P, command=False) -> None:
        # Primary name
        if pipeoid.name in self.by_name:
            raise Exception(f'Overlapping name: {type(pipeoid).__name__}:{pipeoid.name}')
        self.by_primary_name[pipeoid.name] = pipeoid
        self.by_name[pipeoid.name] = pipeoid

        # Aliases
        for name in pipeoid.aliases:
            if name in self.by_name:
                raise Exception(f'Overlapping name: {type(pipeoid).__name__}:{name}')
            self.by_name[name] = pipeoid

        # Category
        if pipeoid.category:
            self.categories[pipeoid.category].append(pipeoid)

        if command:
            self.commands.append(pipeoid)

    def __getitem__(self, name: str) -> P:
        return self.by_name[name]

    def __contains__(self, name: str) -> bool:
        return (name in self.by_name)

    def __len__(self):
        return len(self.by_primary_name)

    def __iter__(self):
        return self.by_primary_name.__iter__()

    def values(self):
        return self.by_primary_name.values()


class Pipes(PipeoidStore[Pipe]):
    _name_singular = 'Pipe'
    _name_plural = 'Pipes'

class Sources(PipeoidStore[Source]):
    _name_singular = 'Source'
    _name_plural = 'Sources'

class Spouts(PipeoidStore[Spout]):
    _name_singular = 'Spout'
    _name_plural = 'Spouts'
