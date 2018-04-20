from functools import wraps
import pickle

import discord
from discord.ext import commands

from .pipes import *
from .macros import Macro, pipe_macros, source_macros
from .processor import Pipeline
from mycommands import MyCommands
import utils.texttools as texttools
import utils.util as util

infoText = '''
**Pipes** are a text manipulation toy that I slowly developed over time.
The concept is that you start with some piece(s) of text as a **source** (e.g. chat messages, tweets, random dictionary words...)
and you modify them using **pipes** that perform some simple task (e.g. turn everything uppercase, swap random letters, translate...)
and by chaining together multiple **pipes** in sequence you create a **pipeline**.

You can execute a pipeline by typing something of the form:
    `>>> [source] > [pipe] > [pipe] > ...`

**[source]** can just be text, e.g. `Quentin Tarantino`.
It can also contain special sources that find/produce text, written as `{sourceName [args]}`.
    e.g. `{random}`, `Here's a simpsons quote: {simpsons}`, `dril once said "{dril q="my ass"}"`.

The list of possible sources can be seen by typing **>sources**

Each **[pipe]** is an item of the form `pipeName [args]`.
    e.g. `print`, `repeat n=3`, `translate from=en to=fr`

The list of possible pipes can be seen by typing **>pipes**

For both pipes and sources, **[args]** is a list of arguments: `[arg] [arg] [arg] ...`
Each **[arg]** can be of the form `argName=valueNoSpaces` or `argName="value with spaces"`.
To see information on a source/pipe's arguments, use **>source sourceName** or **>pipe pipeName**

Several example pipelines that you can try out:
    `>>> Quentin Tarantino > repeat n=4 -> letterize p=0.5 -> min_dist`
    `>>> {prev} > case A > convert fullwidth`
    `>>> {that} > case Aa`

PS: `->` is short for `> print >`
'''

###############################################################
#            A module providing commands for pipes            #
###############################################################

class PipesCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command(aliases=['pipe_help', 'pipes_info', 'pipe_info'])
    async def pipes_help(self):
        '''Print general info on how to use my wacky system of pipes.'''
        await self.say(infoText)
        
    # TODO: refactor Pipes and Sources into actual classes with this as a method.
    def get_embed(self, name, item):
        embed = discord.Embed(title=name, description=item.__doc__, color=0xfdca4b)
        if item.signature:
            sig = '\n'.join(item.signature)
            embed.add_field(name='Arguments', value=sig, inline=False)
        # bot takes credit for the method
        embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        return embed

    @commands.command(aliases=['pipe'])
    async def pipes(self, name=''):
        '''Print a list of all pipes and their descriptions, or details on a specific pipe.'''

        # Info on a specific pipe
        if name != '' and name in pipes:
            await self.bot.say(embed=self.get_embed(name, pipes[name]))

        # Info on a macro pipe
        elif name != '' and name in pipe_macros:
            await self.bot.say(embed=pipe_macros[name].embed())

        # Info on all pipes
        else:
            infos = []
            infos.append('Here\'s a list of pipes, use >pipes [pipe name] to see more info on a specific one.\nUse >pipe_macros for a list of user-defined pipes.\n')
            colW = len(max(pipes, key=len)) + 2
            for name in pipes:
                pipe = pipes[name]
                info = name + ' ' * (colW-len(name))
                if pipe.__doc__ is not None:
                    info += pipe.__small_doc__
                infos.append(info)
            text = texttools.block_format('\n'.join(infos))
            await self.say(text)

    @commands.command(aliases=['source'])
    async def sources(self, name=''):
        '''Print a list of all sources and their descriptions, or details on a specific source.'''

        # Info on a specific source
        if name != '' and name in sources:
            await self.bot.say(embed=self.get_embed(name, sources[name]))

        # Info on a macro source
        elif name != '' and name in source_macros:
            await self.bot.say(embed=source_macros[name].embed())

        # Info on all sources
        else:
            infos = []
            infos.append('Here\'s a list of sources, use >sources [source name] to see more info on a specific one.\nUse >source_macros for a list of user-defined sources.\n')
            colW = len(max(sources, key=len)) + 2
            for name in sources:
                source = sources[name]
                info = name + ' ' * (colW-len(name))
                if source.__doc__ is not None:
                    info += source.__small_doc__
                infos.append(info)
            text = texttools.block_format('\n'.join(infos))
            await self.say(text)

###############################################################
#                  Turn pipes into commands!                  #
###############################################################

def pipe_to_func(pipe):
    async def func(self, ctx):
        text = util.strip_command(ctx)
        pl = Pipeline('', ctx.message)
        text = pl.evaluate_all_sources(text)
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
        args = util.strip_command(ctx)
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