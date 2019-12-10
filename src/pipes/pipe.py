from textwrap import dedent
from discord import Embed

from .signature import parse_args


class Pipe:
    def __init__(self, signature, function, category):
        self.signature = signature
        # Make sure each Sig knows its own name (this shouldn't happen here but there's no better place)
        for s in signature: signature[s].name = s
        self.function = function
        self.category = category
        # remove _pipe or _source or _spout from the function's name
        self.name = function.__name__.rsplit('_', 1)[0].lower()
        self.doc = function.__doc__
        self.small_doc = None
        if self.doc is not None:
            self.doc = dedent(self.doc).lstrip()
            self.small_doc = self.doc.split('\n')[0]

    def __call__(self, values, argstr):
        _, args = parse_args(self.signature, argstr)
        return self.function(values, **args)

    def as_command(self, text):
        text, args = parse_args(self.signature, text, greedy=False)
        return self.function([text], **args)

    def command_doc(self):
        out = self.doc if self.doc else ''
        if self.signature:
            out += '\nArguments:\n'
            out += '\n'.join(['• ' + s + ': ' + str(self.signature[s]) for s in self.signature])
        return out

    def embed(self):
        embed = Embed(title=(self.__class__.__name__ + ': ' + self.name), description=self.doc, color=0xfdca4b)
        if self.signature:
            sig = '\n'.join(['__'+s+':__ ' + str(self.signature[s]) for s in self.signature])
            embed.add_field(name='Arguments', value=sig, inline=False)
        return embed


class Source(Pipe):
    def __init__(self, signature, function, category, pass_message=False, plural=None):
        self.pass_message = pass_message
        super().__init__(signature, function, category)
        self.plural = plural.lower() if plural or self.name + 's'

    def __call__(self, message, argstr, n=None):
        _, args = parse_args(self.signature, argstr)
        if n:
            if 'n' in args: args['n'] = int(n)
            elif 'N' in args: args['N'] = int(n)
        if self.pass_message:
            return self.function(message, **args)
        else:
            return self.function(**args)
            
    def as_command(self):
        '''This method is not needed and only defined to hide the inherited as_command method to prevent'''
        raise NotImplementedError()


class Spout(Pipe):
    def __init__(self, signature, function, category):
        super().__init__(signature, function, category)
        
    def __call__(self, values, argstr):
        # DOES NOT actually call the underlying function, instead parses the arguments
        # and returns a tuple of items that allows the underlying function to be called at a later time
        _, args = parse_args(self.signature, argstr)
        return (self.function, args, values)

    async def as_command(self, bot, message, text):
        text, args = parse_args(self.signature, text, greedy=False)
        await self.function(bot, message, [text], **args)


class Pipes:
    '''A class for storing multiple Pipe instances.'''
    def __init__(self):
        self.pipes = {}
        self.categories = {}

    def __getitem__(self, name):
        return self.pipes[name]

    def add(self, pipe):
        self.pipes[pipe.name] = pipe
        if pipe.category not in self.categories:
            self.categories[pipe.category] = []
        self.categories[pipe.category].append(pipe)

    def __contains__(self, name):
        return (name in self.pipes)

    def __len__(self, name):
        return len(self.pipes)

    def __bool__(self):
        return len(self.pipes) > 0

    def __iter__(self):
        return (i for i in self.pipes)

class Sources(Pipes):
    '''Pipes except sources can be addressed as either singular or plural'''
    def __init__(self):
        super().__init__()
        self.plurals = {}

    def __getitem__(self, name):
        if name in self.pipes:
            return self.pipes[name]
        return self.plurals[name]

    def add(self, source):
        super().add(source)
        self.plurals[source.plural] = source

    def __contains__(self, name):
        return (name in self.pipes) or (name in self.plurals)