import inspect
from textwrap import dedent
import discord
from discord import Embed

from .signature import Signature
from typing import Callable, Any


class Pipe:
    '''
    Represents a functional function that can be used in a script.
    
    '''
    def __init__(
        self,
        signature: Signature,
        function: Callable[..., list[str]],
        category: str=None,
        may_use: Callable[[discord.User], bool]=None,
    ):
        self.signature = signature
        self.function = function
        self.category = category
        self._may_use = may_use
        self.is_coroutine = inspect.iscoroutinefunction(function)
        # remove _pipe or _source or _spout from the function's name
        self.name = function.__name__.rsplit('_', 1)[0].lower()
        self.doc = function.__doc__
        self.small_doc = None
        if self.doc:
            # doc is the full docstring
            self.doc = dedent(self.doc).lstrip()
            # small_doc is only the first line of the docstring
            self.small_doc = self.doc.split('\n', 1)[0]

    def __call__(self, items: list[str], **args) -> list[str]:
        raise DeprecationWarning("PIPE.__CALL__")

    def apply(self, items: list[str], **args) -> list[str]:
        ''' Apply the pipe to a list of items. '''
        return self.function(items, **args)

    def may_use(self, user):
        if self._may_use:
            return self._may_use(user)
        return True

    def command_doc(self):
        out = self.doc or ''
        if self.signature:
            out += '\nParameters:\n'
            out += '\n'.join(['• ' + s + ': ' + str(self.signature[s]) for s in self.signature])
        return out

    def embed(self, ctx=None):
        embed = Embed(title=(self.__class__.__name__ + ': ' + self.name), description=self.doc, color=0xfdca4b)
        if self.signature:
            sig = '\n'.join(['__'+s+':__ ' + str(self.signature[s]) for s in self.signature])
            embed.add_field(name='Parameters', value=sig, inline=False)
        return embed


class Source(Pipe):
    def __init__(self, signature, function, category, *, pass_message=False, plural=None, depletable=False):
        super().__init__(signature, function, category)
        self.pass_message = pass_message
        self.depletable = depletable
        self.plural = plural.lower() if plural else (self.name + 's') if 'n' in signature else self.name

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

    def embed(self):
        embed = super().embed()
        if self.plural != self.name:
            embed.title += ' (' + self.plural + ')'
        if self.depletable:
            embed.title += ' `depletable`'
        return embed


class Spout(Pipe):
    def __init__(self, signature, function, category):
        super().__init__(signature, function, category)
        
    def __call__(self, items: list[str], **args) -> tuple[Callable[..., None], dict[str, Any], list[str]] :
        # DOES NOT actually call the underlying function yet, but returns the tuple of items so it can be done later...
        return (self.function, args, items)


class Pipes:
    ''' A class for storing multiple Pipe instances. '''
    pipes: dict[str, Pipe]
    categories: dict[str, list[Pipe]]

    def __init__(self):
        self.pipes = {}
        self.categories = {}

    def __getitem__(self, name: str) -> Pipe:
        return self.pipes[name]

    def add(self, pipe: Pipe) -> None:
        self.pipes[pipe.name] = pipe
        if pipe.category:
            if pipe.category not in self.categories:
                self.categories[pipe.category] = []
            self.categories[pipe.category].append(pipe)

    def __contains__(self, name: str) -> bool:
        return (name in self.pipes)

    def __len__(self):
        return len(self.pipes)

    def __bool__(self):
        return len(self.pipes) > 0

    def __iter__(self):
        return (i for i in self.pipes)

    def values(self):
        return self.pipes.values()

class Sources(Pipes):
    ''' Pipes except sources can be addressed as either singular or plural. '''
    pipes: dict[str, Source]
    plurals: dict[str, Source]
    categories: dict[str, list[Source]]

    def __init__(self):
        super().__init__()
        self.plurals = {}

    def __getitem__(self, name: str) -> Source:
        if name in self.pipes:
            return self.pipes[name]
        return self.plurals[name]

    def add(self, source: Source) -> None:
        super().add(source)
        self.plurals[source.plural] = source

    def __contains__(self, name: str) -> bool:
        return (name in self.pipes) or (name in self.plurals)