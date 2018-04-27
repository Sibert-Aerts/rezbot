from functools import wraps
import pickle

import discord
from discord.ext import commands

from .pipes import *
from .macros import Macro, pipe_macros, source_macros
from mycommands import MyCommands
import utils.texttools as texttools

typedict = {'pipe': pipe_macros, 'source': source_macros}
typedict_options = ', '.join('"' + t + '"' for t in typedict)

class MacroCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)

    async def what_complain(self):
        await self.say('First argument must be one of: {}.'.format(typedict_options))

    async def permission_complain(self):
        await self.say('You are not authorised to modify that macro. Try defining a new one instead.')

    @commands.command(pass_context=True, aliases=['def'])
    async def define(self, ctx, what, name):
        '''Define a macro.'''
        what = what.lower()
        try: macros = typedict[what]
        except: await self.what_complain(); return

        name = name.lower().split(' ')[0]
        if name in pipes or name in macros:
            await self.say('A {0} called "{1}" already exists, try `>redefine {0}` instead.'.format(what, name))
            return

        code = re.split('\s+', ctx.message.content, 3)[3]
        author = ctx.message.author
        macros[name] = Macro(name, code, author.name, author.id, author.avatar_url)
        await self.say('Defined a new {} called `{}` as {}'.format(what, name, texttools.block_format(code)))

    @commands.command(pass_context=True, aliases=['redef'])
    async def redefine(self, ctx, what, name):
        '''Redefine an existing macro.'''
        what = what.lower()
        try: macros = typedict[what]
        except: await self.what_complain(); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.say('A {} macro by that name was not found.'.format(what))
            return

        if not macros[name].authorised(ctx.message.author):
            await self.permission_complain(); return

        code = re.split('\s+', ctx.message.content, 3)[3]
        macros[name].code = code
        macros.write()
        await self.say('Redefined {} `{}` as {}'.format(what, name, texttools.block_format(code)))

    @commands.command(pass_context=True, aliases=['desc'])
    async def describe(self, ctx, what, name):
        '''Describe an existing macro.'''
        what = what.lower()
        try: macros = typedict[what]
        except: await self.what_complain(); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.say('A {} macro by that name was not found.'.format(what))
            return

        if macros[name].desc and not macros[name].authorised(ctx.message.author):
            await self.permission_complain(); return

        desc = re.split('\s+', ctx.message.content, 3)[3]
        macros[name].desc = desc
        macros.write()
        await self.say('Described {} `{}` as `{}`'.format(what, name, desc))

    @commands.command(pass_context=True, aliases=['del'])
    async def delete(self, ctx, what, name):
        '''Delete a macro by name.'''
        what = what.lower()
        try: macros = typedict[what]
        except: await self.what_complain(); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.say('A {} macro by that name was not found.'.format(what))
            return

        if not macros[name].authorised(ctx.message.author):
            await self.permission_complain(); return

        del macros[name]
        await self.say('Deleted {} macro `{}`.'.format(what, name))

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
                await self.say('No pipe macros loaded. Try adding one using >define.')
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

    # I just copy-pasted the whole function and replaced "pipe" with "source", sue me.

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
                await self.say('No source macros loaded. Try adding one using >define.')
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