from collections import defaultdict
import inspect
from textwrap import dedent
import discord
from discord import Embed

from .signature import Signature
from typing import Callable, Any, Generic, TypeVar


class Pipe:
    '''
    Represents a functional function that can be used in a script.    
    '''
    def __init__(
        self,
        signature: Signature,
        function: Callable[..., list[str]],
        *,
        name: str=None,
        aliases: list[str]=None,
        category: str=None,
        may_use: Callable[[discord.User], bool]=None,
    ):
        self.signature = signature
        self.function = function
        self.category = category
        self._may_use = may_use
        self.is_coroutine = inspect.iscoroutinefunction(function)
        # remove _pipe or _source or _spout from the function's name
        self.name = name or function.__name__.rsplit('_', 1)[0].lower()
        self.aliases = aliases or []
        self.doc = function.__doc__
        self.small_doc = None
        if self.doc:
            # doc is the full docstring
            self.doc = dedent(self.doc).lstrip()
            # small_doc is only the first line of the docstring
            self.small_doc = self.doc.split('\n', 1)[0]

    # ====================================== SCRIPT USAGE API =====================================

    def __call__(self, items: list[str], **args) -> list[str]:
        raise DeprecationWarning("PIPE.__CALL__")

    def apply(self, items: list[str], **args) -> list[str]:
        ''' Apply the pipe to a list of items. '''
        return self.function(items, **args)

    def may_use(self, user):
        if self._may_use:
            return self._may_use(user)
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


class Source(Pipe):
    '''
    Represents something which generates strings in a script.
    '''
    def __init__(self, sig: Signature, fun, *, category: str=None, pass_message=False, plural: str=None, depletable=False):
        super().__init__(sig, fun, category=category)
        self.pass_message = pass_message
        self.depletable = depletable

        self.plural = None
        if plural:
            self.plural = plural.lower() 
        elif plural is not False and 'n' in sig:
            self.plural = self.name + 's'

        if self.plural and self.plural != self.name:
            self.aliases.insert(0, self.plural)

    def __call__(self, message, args: dict[str, Any], n=None):
        ''' Call the Source to produce items using a parsed dict of arguments. '''
        if n:
            # Handle the `n` that may be given using the {n sources} notation
            if isinstance(n, str) and n.lower() == 'all':
                if self.depletable: n = -1
                else: raise ValueError('Requested `all` items but the source is not depletable.')
            if 'n' in args: args['n'] = int(n)
            elif 'N' in args: args['N'] = int(n)
        if self.pass_message:
            return self.function(message, **args)
        else:
            return self.function(**args)

    def embed(self, ctx=None):
        embed = super().embed(ctx=ctx)
        if self.plural and self.plural != self.name:
            embed.title += ' (' + self.plural + ')'
        if self.depletable:
            embed.title += ' `depletable`'
        return embed


class Spout(Pipe):
    '''
    Represents something which strictly performs side-effects in a script.
    '''        
    def __call__(self, items: list[str], **args) -> tuple[Callable[..., None], dict[str, Any], list[str]] :
        # DOES NOT actually call the underlying function yet, but returns the tuple of items so it can be done later...
        return (self.function, args, items)



P = TypeVar("P", Pipe, Source, Spout)

class AbstractPipeoidStore(Generic[P]):
    ''' A class for storing/mapping multiple Pipeoid instances. '''
    by_name: dict[str, P] = {}
    by_primary_name: dict[str, P] = {}
    categories: defaultdict[str, list[P]] = defaultdict(list)

    def add(self, pipeoid: P) -> None:
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


class Pipes(AbstractPipeoidStore[Pipe]):
    pass

class Sources(AbstractPipeoidStore[Source]):
    pass

class Spouts(AbstractPipeoidStore[Spout]):
    pass
