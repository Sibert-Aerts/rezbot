from functools import wraps
import pickle

import discord
from discord.ext import commands

from .pipes import pipes
from .sources import sources
from .macros import pipe_macros, source_macros
from .processor import Pipeline
from mycommands import MyCommands
import utils.texttools as texttools
import utils.util as util

###############################################################
#            A module providing commands for pipes            #
###############################################################

class PipeCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command(aliases=['pipe_help', 'pipes_info', 'pipe_info', 'pipes_guide', 'pipe_guide'])
    async def pipes_help(self):
        '''Links the guide to using pipes.'''
        await self.say('https://github.com/Sibert-Aerts/rezbot/blob/master/PIPESGUIDE.md')

    @commands.command(aliases=['pipe'])
    async def pipes(self, name=''):
        '''Print a list of all pipes and their descriptions, or details on a specific pipe.'''
        name = name.lower()

        # Info on a specific pipe
        if name != '' and name in pipes:
            embed = pipes[name].embed()
            # bot takes credit for native pipes
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)
            await self.bot.say(embed=embed)

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
                if pipe.doc: info += pipe.small_doc
                infos.append(info)
            text = texttools.block_format('\n'.join(infos))
            await self.say(text)

    @commands.command(aliases=['source'])
    async def sources(self, name=''):
        '''Print a list of all sources and their descriptions, or details on a specific source.'''
        name = name.lower()

        # Info on a specific source
        if name != '' and name in sources:
            embed = sources[name].embed()
            # bot takes credit for native sources
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)
            await self.bot.say(embed=embed)

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
                if source.doc: info += source.small_doc
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
        text = pl.evaluate_composite_source(text)
        text = '\n'.join(pipe.as_command(text))
        await self.say(text)
    func.__name__ = pipe.name
    func.__doc__ = pipe.command_doc()
    return func

# Turn those pipes into discord.py bot commands!
for pipe in pipes.command_pipes:
    func = pipe_to_func(pipe)
    # manually call the function decorator to make func into a command
    command = commands.command(pass_context=True)(func)
    setattr(PipeCommands, pipe.name, command)

###############################################################
#                 Turn sources into commands!                 #
###############################################################

def source_to_func(source):
    async def func(self, ctx):
        text = util.strip_command(ctx)
        pl = Pipeline('', ctx.message)
        text = pl.evaluate_composite_source(text)
        text = '\n'.join(source(ctx.message, text))
        await self.say(text)
    func.__name__ = source.name
    func.__doc__ = source.command_doc()
    return func

# Turn those sources into discord.py bot commands!
for source in sources.command_sources:
    func = source_to_func(source)
    # manually call the function decorator to make func into a command
    command = commands.command(pass_context=True)(func)
    setattr(PipeCommands, source.name, command)


# Load the bot cog
def setup(bot):
    bot.add_cog(PipeCommands(bot))