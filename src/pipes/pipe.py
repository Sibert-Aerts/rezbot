from collections import defaultdict
import inspect
from textwrap import dedent
import traceback
import discord
from discord import Embed

from .signature import Signature
from typing import Callable, Any, Generic, TypeVar


class Pipeoid():
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
        name: str=None,
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
            self.doc = dedent(doc).lstrip()
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
            out += '\n'.join(f'• {s}: {self.signature[s]}' for s in self.signature)
        return out

    def embed(self, ctx=None):
        embed = Embed(title=str(self), description=self.doc, color=0xfdca4b)
        if self.signature:
            sig = '\n'.join(f'__{s}:__ {self.signature[s]}' for s in self.signature)
            embed.add_field(name='Parameters', value=sig, inline=False)
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

    def apply(self, items: list[str], **args) -> list[str]:
        ''' Apply the pipe to a list of items. '''
        # TODO: Call may_use here?
        return self.pipe_function(items, **args)


class Source(Pipeoid):
    '''
    Represents something which generates strings in a script.
    '''
    source_function: Callable[..., list[str]]
    # TODO: Get rid of pass_message
    pass_message: bool
    depletable: bool
    plural: str | None = None

    def __init__(self, signature: Signature, function: Callable[..., list[str]], *, plural: str=None, pass_message=False, depletable=False, **kwargs):
        super().__init__(signature=signature, **kwargs)
        self.source_function = function
        self.pass_message = pass_message
        self.depletable = depletable

        if plural:
            self.plural = plural.lower() 
        elif plural is not False and 'n' in signature:
            self.plural = self.name + 's'
        if self.plural and self.plural != self.name:
            self.aliases.insert(0, self.plural)

    def generate(self, message, args: dict[str, Any], n=None):
        ''' Call the Source to produce items using a parsed dict of arguments. '''
        if n:
            # Handle the `n` that may be given using the {n sources} notation
            if isinstance(n, str) and n.lower() == 'all':
                if self.depletable: n = -1
                else: raise ValueError('Requested `all` items but the source is not depletable.')
            if 'n' in args: args['n'] = int(n)
            elif 'N' in args: args['N'] = int(n)
        if self.pass_message:
            return self.source_function(message, **args)
        else:
            return self.source_function(**args)

    def __call__(self, *args, **kwargs):
        traceback.print_stack(limit=3)
        print('Deprecation Warning: Source.__call__')
        return self.generate(*args, **kwargs)

    def embed(self, ctx=None):
        embed = super().embed(ctx=ctx)
        if self.plural and self.plural != self.name:
            embed.title += ' (' + self.plural + ')'
        if self.depletable:
            embed.title += ' `depletable`'
        return embed


class Spout(Pipeoid):
    '''
    Represents something which strictly performs side-effects in a script.
    '''
    spout_function: Callable[..., None]
    
    def __init__(self, signature: Signature, function: Callable[..., list[str]], **kwargs):
        super().__init__(signature=signature, **kwargs)
    
        # self.name = name or function.__name__.rsplit('_', 1)[0].lower()
        self.spout_function = function

    def hook(self, items: list[str], **args):
        # DOES NOT actually call the underlying function yet, but returns the tuple of items so it can be done later...
        return (self.spout_function, args, items)



P = TypeVar("P")

class PipeoidStore(Generic[P]):
    ''' A class for storing/mapping multiple Pipeoid instances. '''
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
        return len(self.by_name)

    def __iter__(self):
        return (i for i in self.by_primary_name)

    def values(self): 
        return self.by_primary_name.values()


class Pipes(PipeoidStore[Pipe]):
    pass

class Sources(PipeoidStore[Source]):
    pass

class Spouts(PipeoidStore[Spout]):
    pass
