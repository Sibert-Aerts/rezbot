from textwrap import dedent
from discord import Embed
from .signature import parse_args


class Pipe:
    def __init__(self, signature, function):
        self.signature = signature
        self.function = function
        # remove _pipe or _source from the name
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
        text, args = parse_args(self.signature, text)
        return self.function([text], **args)

    def command_doc(self):
        out = self.doc
        out += '\nArguments:\n'
        out += '\n'.join(['• ' + s + ': ' + str(self.signature[s]) for s in self.signature])
        return out

    def embed(self):
        embed = Embed(title=self.name, description=self.doc, color=0xfdca4b)
        if self.signature:
            sig = '\n'.join(['__'+s+':__ ' + str(self.signature[s]) for s in self.signature])
            embed.add_field(name='Arguments', value=sig, inline=False)
        return embed


class Source(Pipe):
    def __init__(self, signature, function, pass_message=False):
        self.pass_message = pass_message
        super().__init__(signature, function)

    def __call__(self, message, argstr):
        _, args = parse_args(self.signature, argstr)
        if self.pass_message:
            return self.function(message, **args)
        else:
            return self.function(**args)


class Pipes:
    '''A class for storing multiple Pipe instances.'''
    def __init__(self):
        self.pipes = {}

    def __getitem__(self, name):
        return self.pipes[name]

    def __setitem__(self, name, pipe):
        self.pipes[name] = pipe

    def __contains__(self, name):
        return (name in self.pipes)

    def __len__(self, name):
        return len(self.pipes)

    def __bool__(self):
        return len(self.pipes) > 0

    def __iter__(self):
        return (i for i in self.pipes)