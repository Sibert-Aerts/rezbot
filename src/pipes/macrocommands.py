from functools import wraps
import pickle

import discord
from discord.ext import commands

from .pipes import *
from .macros import Macro, pipe_macros, source_macros
from mycommands import MyCommands
import utils.texttools as texttools

class MacroCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command(pass_context=True, aliases=['def_pipe'])
    async def define_pipe(self, ctx, name):
        '''Define a pipe macro. First argument is the name, everything after that is the code.'''
        name = name.lower().split(' ')[0]
        if name in pipes or name in pipe_macros:
            await self.say('A pipe by that name already exists, try >redefine instead.')
            return
        code = re.split('\s+', ctx.message.content, 2)[2]
        author = ctx.message.author
        pipe_macros[name] = Macro(name, code, author.name, author.id, author.avatar_url)
        await self.say('Defined a new pipe called `{}` as {}'.format(name, texttools.block_format(code)))

    @commands.command(pass_context=True, aliases=['redef_pipe'])
    async def redefine_pipe(self, ctx, name):
        '''Redefine a pipe macro. First argument is the name, everything after that is the code.'''
        name = name.lower().split(' ')[0]
        if name not in pipe_macros:
            await self.say('A pipe macro by that name was not found!')
            return
        code = re.split('\s+', ctx.message.content, 2)[2]
        pipe_macros[name].code = code
        pipe_macros.write()
        await self.say('Redefined `{}` as {}'.format(name, texttools.block_format(code)))

    @commands.command(pass_context=True, aliases=['desc_pipe'])
    async def describe_pipe(self, ctx, name):
        '''Describe a pipe macro. First argument is the name, everything after that is the description.'''
        name = name.lower().split(' ')[0]
        if name not in pipe_macros:
            await self.say('A pipe macro by that name was not found!')
            return
        desc = re.split('\s+', ctx.message.content, 2)[2]
        pipe_macros[name].desc = desc
        pipe_macros.write()
        await self.say('Described `{}` as `{}`'.format(name, desc))

    @commands.command(pass_context=True, aliases=['del_pipe'])
    async def delete_pipe(self, ctx, name):
        '''Delete a pipe macro by name.'''
        name = name.lower().split(' ')[0]
        if name not in pipe_macros:
            await self.say('A pipe macro by that name was not found!')
            return
        del pipe_macros[name]
        await self.say('Deleted pipe macro `{}`.'.format(name))

    @commands.command(pass_context=True, aliases=['pipe_macro', 'macro_pipes', 'macro_pipe'])
    async def pipe_macros(self, ctx, name=''):
        '''Print a list of all pipe macros and their descriptions, or details on a specific pipe macro.'''
        infos = []

        # Info on a specific pipe
        if name != '' and name in pipe_macros:
            await self.bot.say(embed=pipe_macros[name].embed())

        # Info on all pipes
        else:
            if not pipe_macros:
                await self.say('No pipe macros loaded! Try adding one using >define_pipe!')
                return

            infos.append('Here\'s a list of all pipe macros, use >pipe_macros [name] to see more info on a specific one.\nUse >pipes for a list of native pipes.\n')
            colW = len(max(pipe_macros, key=len)) + 2
            for name in pipe_macros:
                pipe = pipe_macros[name]
                info = name + ' ' * (colW-len(name))
                if pipe.desc is not None:
                    info += pipe.desc
                infos.append(info)

            text = texttools.block_format('\n'.join(infos))
            await self.say(text)

    # I just copy-pasted the whole block and replaced "pipe" with "source", sue me.

    @commands.command(pass_context=True, aliases=['def_source'])
    async def define_source(self, ctx, name):
        '''Define a source macro. First argument is the name, everything after that is the code.'''
        name = name.lower().split(' ')[0]
        if name in sources or name in source_macros:
            await self.say('A source by that name already exists, try >redefine instead.')
            return
        code = re.split('\s+', ctx.message.content, 2)[2]
        author = ctx.message.author
        source_macros[name] = Macro(name, code, author.name, author.id, author.avatar_url)
        await self.say('Defined a new source called `{}` as {}'.format(name, texttools.block_format(code)))

    @commands.command(pass_context=True, aliases=['redef_source'])
    async def redefine_source(self, ctx, name):
        '''Redefine a source macro. First argument is the name, everything after that is the code.'''
        name = name.lower().split(' ')[0]
        if name not in source_macros:
            await self.say('A source macro by that name was not found!')
            return
        code = re.split('\s+', ctx.message.content, 2)[2]
        source_macros[name].code = code
        source_macros.write()
        await self.say('Redefined `{}` as {}'.format(name, texttools.block_format(code)))

    @commands.command(pass_context=True, aliases=['desc_source'])
    async def describe_source(self, ctx, name):
        '''Describe a source macro. First argument is the name, everything after that is the description.'''
        name = name.lower().split(' ')[0]
        if name not in source_macros:
            await self.say('A source macro by that name was not found!')
            return
        desc = re.split('\s+', ctx.message.content, 2)[2]
        source_macros[name].desc = desc
        source_macros.write()
        await self.say('Described `{}` as `{}`'.format(name, desc))

    @commands.command(pass_context=True, aliases=['del_source'])
    async def delete_source(self, ctx, name):
        '''Delete a source macro by name.'''
        name = name.lower().split(' ')[0]
        if name not in source_macros:
            await self.say('A source macro by that name was not found!')
            return
        del source_macros[name]
        await self.say('Deleted source macro `{}`.'.format(name))

    @commands.command(pass_context=True, aliases=['source_macro', 'macro_sources', 'macro_source'])
    async def source_macros(self, ctx, name=''):
        '''Print a list of all source macros and their descriptions, or details on a specific source macro.'''
        infos = []

        # Info on a specific source
        if name != '' and name in source_macros:
            await self.bot.say(embed=source_macros[name].embed())

        # Info on all sources
        else:
            if not source_macros:
                await self.say('No source macros loaded! Try adding one using >define_source!')
                return

            infos.append('Here\'s a list of all source macros, use >source_macros [name] to see more info on a specific one.\nUse >sources for a list of native sources.\n')
            colW = len(max(source_macros, key=len)) + 2
            for name in source_macros:
                source = source_macros[name]
                info = name + ' ' * (colW-len(name))
                if source.desc is not None:
                    info += source.desc
                infos.append(info)

            text = texttools.block_format('\n'.join(infos))
            await self.say(text)


# Load the bot cog
def setup(bot):
    bot.add_cog(MacroCommands(bot))