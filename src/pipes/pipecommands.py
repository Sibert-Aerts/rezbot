from functools import wraps
import pickle

import discord
from discord.ext import commands

from .pipes import *
from mycommands import MyCommands
import utils.texttools as texttools
import utils.util as util

infoText = '''
Pipes are a weird text-manipulation toy that came to me in a dream and that I forgot about in another dream.
The concept is that pieces of input text are transformed by a series of methods called "pipes"
in order to produce fun and unpredictable output text, like a game of telephone.

You can execute a pipeline by typing something of the form:
    `>>> [source] > [pipe] > [pipe] > ...`

[source] can just be text, e.g. `Quentin Tarantino`.
It can also be a special source that finds/produces text, written as `{sourceName [args]}`, e.g. `{random}`.

The list of possible sources can be seen by typing `>sources`

Each [pipe] is an item of the form `pipeName [args]`.
    e.g. `print`, `repeat n=3`, `translate from=en to=fr`

The list of possible pipes can be seen by typing `>pipes`

For both pipes and sources, [args] is a list of arguments: `[arg] [arg] [arg] ...`
Each [arg] can be of the form `argName=valueNoSpaces` or `argName="value with spaces"`.

Several example pipelines that you can try out:
    `>>> Quentin Tarantino > repeat 4 -> letterize p=0.5 -> min_dist`
    `>>> {prev} > case A > convert fullwidth`
    `>>> {that} > case Aa`


PS: `->` is short for `> print >`
'''

customPipes = {}
try:
    customPipes = pickle.load(open('custompipes.p', 'rb'))
    print(len(customPipes), 'custom pipes loaded.')
except:
    print('Could not load custompipes.p!')
    pass

###############################################################
#              An extra command module for pipes              #
###############################################################

class PipesCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command()
    async def languages(self, name=''):
        '''Print the list of languages applicable for the translate command/pipe.'''
        #TODO: put this in the language pipe's doc.
        await self.say(' '.join(texttools.translateLanguages))

    @commands.command()
    async def pipes_help(self):
        '''Print general info on how to use my wacky system of pipes.'''
        await self.say(infoText)

    @commands.command()
    async def pipes(self, name=''):
        '''Print a list of all pipes and their descriptions, or details on a specific pipe.'''
        infos = []

        # TODO: if name in customPipes:

        # Info on a specific pipe
        if name != '' and name in pipes:
            pipe = pipes[name]
            info = name
            if pipe.__doc__ is not None:
                info += ':\n\t' + pipe.__doc__
            if pipe.signature:
                info += '\n\tArguments:'
                info += '\n\t • ' + '\n\t • '.join(pipe.signature)
            infos.append(info)

        # Info on all pipes
        else:
            infos.append('Here\'s a list of pipes, use >pipes [pipe name] to see more info on a specific one.\n')
            colW = len(max(pipes, key=len)) + 2
            for name in pipes:
                pipe = pipes[name]
                info = name + ' ' * (colW-len(name))
                if pipe.__doc__ is not None:
                    info += pipe.__doc__
                infos.append(info)
        
        text = texttools.block_format('\n'.join(infos))
        await self.say(text)

    @commands.command()
    async def sources(self, name=''):
        '''Print a list of all sources and their descriptions, or details on a specific pipe.'''
        infos = []

        # Info on a specific source
        if name != '' and sources.get(name) is not None:
            source = sources[name]
            info = name
            if source.__doc__ is not None:
                info += ':\n\t' + source.__doc__
            if source.signature:
                info += '\n\tArguments:'
                info += '\n\t • ' + '\n\t • '.join(source.signature)
            infos.append(info)

        # Info on all sources
        else:
            infos.append('Here\'s a list of sources, use >sources [source name] to see more info on a specific one.\n')
            colW = len(max(sources, key=len)) + 2
            for name in sources:
                source = sources[name]
                info = name + ' ' * (colW-len(name))
                if source.__doc__ is not None:
                    info += source.__doc__
                infos.append(info)
        
        text = texttools.block_format('\n'.join(infos))
        await self.say(text)

    # Custom pipes down here

    @commands.command(pass_context=True)
    async def define(self, ctx, name=''):
        '''Define a custom pipe. First argument is the name, everything after that is the code.'''
        name = name.lower()
        if name in pipes or name in customPipes:
            await self.say('A pipe by that name already exists, try >redefine instead.')
            return
        code = re.split('\s+', ctx.message.content, 2)[2]
        customPipes[name] = {'desc': None, 'code': code}
        await self.say('Defined a new pipe called `{}` as `{}`'.format(name, customPipes[name]['code']))
        pickle.dump(customPipes, open('custompipes.p', 'wb'))


    @commands.command(pass_context=True)
    async def redefine(self, ctx, name=''):
        '''Redefine a custom pipe. First argument is the name, everything after that is the code.'''
        name = name.lower()
        if name not in customPipes:
            await self.say('A custom pipe by that name was not found!')
            return
        code = re.split('\s+', ctx.message.content, 2)[2]
        customPipes[name]['code'] = code
        await self.say('Redefined `{}` as `{}`'.format(name, customPipes[name]['code']))
        pickle.dump(customPipes, open('custompipes.p', 'wb'))


    @commands.command(pass_context=True)
    async def describe(self, ctx, name=''):
        '''Describe a custom pipe. First argument is the name, everything after that is the description.'''
        name = name.lower()
        if name not in customPipes:
            await self.say('A custom pipe by that name was not found!')
            return
        desc = re.split('\s+', ctx.message.content, 2)[2]
        customPipes[name]['desc'] = desc
        await self.say('Described `{}` as `{}`'.format(name, customPipes[name]['desc']))
        pickle.dump(customPipes, open('custompipes.p', 'wb'))


    @commands.command()
    async def custom_pipes(self, name=''):
        '''Print a list of all custom pipes and their descriptions, or details on a specific custom pipe.'''
        infos = []

        # Info on a specific pipe
        if name != '' and name in customPipes:
            pipe = customPipes[name]
            info = name + ':'
            if pipe['desc'] is not None:
                info += '\n\t' + pipe['desc']
            info += '\nCode:'
            info += '\n\t' + pipe['code']
            # if pipe.signature:
            #     info += '\n\tArguments:'
            #     info += '\n\t • ' + '\n\t • '.join(pipe.signature)
            infos.append(info)

        # Info on all pipes
        else:
            infos.append('Here\'s a list of all custom pipes, use >custom_pipes [name] to see more info on a specific one.\n')
            colW = len(max(customPipes, key=len)) + 2
            for name in customPipes:
                pipe = customPipes[name]
                info = name + ' ' * (colW-len(name))
                if pipe['desc'] is not None:
                    info += pipe['desc']
                infos.append(info)
        
        text = texttools.block_format('\n'.join(infos))
        await self.say(text)

###############################################################
#                  Turn pipes into commands!                  #
###############################################################

def pipe_to_func(pipe):
    async def func(self, ctx):
        text = util.get_args(ctx)
        text = pipe(text)
        await self.say(text)
    func.__name__ = pipe.__name__.split('_pipe', 1)[0]
    func.__doc__ = pipe.__doc__
    if pipe.signature:
        func.__doc__ += '\nArguments:\n' + '\n'.join(' • ' + s for s in pipe.signature)
    return func

# Turn those pipes into discord.py bot commands!
for pipe in command_pipes:
    func = pipe_to_func(pipe)
    # manually call the function decorator to make func into a command
    command = commands.command(pass_context=True)(func)
    setattr(PipesCommands, func.__name__, command)

###############################################################
#                 Turn sources into commands!                 #
###############################################################

def source_to_func(source):
    async def func(self, ctx):
        args = util.get_args(ctx)
        text = source(ctx.message, args)
        await self.say('\n'.join(text))
    func.__name__ = source.__name__.split('_source', 1)[0]
    func.__doc__ = source.__doc__
    if source.signature:
        func.__doc__ += '\nArguments:\n' + '\n'.join(' • ' + s for s in source.signature)
    return func

# Turn those sources into discord.py bot commands!
for source in command_sources:
    func = source_to_func(source)
    # manually call the function decorator to make func into a command
    command = commands.command(pass_context=True)(func)
    setattr(PipesCommands, func.__name__, command)


# Load the bot cog
def setup(bot):
    bot.add_cog(PipesCommands(bot))