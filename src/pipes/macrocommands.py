from functools import wraps
import pickle

import discord
from discord.ext import commands

from .pipes import *
from .macros import Macro, pipe_macros, source_macros
from mycommands import MyCommands
import utils.texttools as texttools

typedict = {
    'pipe': (pipe_macros, True),
    'hiddenpipe': (pipe_macros, False),
    'source': (source_macros, True),
    'hiddensource': (source_macros, False),
}
typedict_options = ', '.join('"' + t + '"' for t in typedict)

class MacroCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)

    async def what_complain(self):
        await self.say('First argument must be one of: {}.'.format(typedict_options))

    async def not_found_complain(self, what):
        await self.say('A {} macro by that name was not found.'.format(what))

    async def permission_complain(self):
        await self.say('You are not authorised to modify that macro. Try defining a new one instead.')

    @commands.command(pass_context=True, aliases=['def'])
    async def define(self, ctx, what, name):
        '''Define a macro.'''
        what = what.lower()
        try: macros, visible = typedict[what]
        except: await self.what_complain(); return

        name = name.lower().split(' ')[0]
        if name in pipes or name in macros:
            await self.say('A {0} called "{1}" already exists, try `>redefine {0}` instead.'.format(what, name))
            return

        code = re.split('\s+', ctx.message.content, 3)[3]
        author = ctx.message.author
        macros[name] = Macro(name, code, author.name, author.id, author.avatar_url, visible=visible)
        await self.say('Defined a new {} called `{}` as {}'.format(what, name, texttools.block_format(code)))

    @commands.command(pass_context=True, aliases=['redef'])
    async def redefine(self, ctx, what, name):
        '''Redefine an existing macro.'''
        what = what.lower()
        try: macros, _ = typedict[what]
        except: await self.what_complain(); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.not_found_complain(what); return

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
        try: macros, _ = typedict[what]
        except: await self.what_complain(); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.not_found_complain(what); return

        if macros[name].desc and not macros[name].authorised(ctx.message.author):
            await self.permission_complain(); return

        desc = re.split('\s+', ctx.message.content, 3)[3]
        macros[name].desc = desc
        macros.write()
        await self.say('Described {} `{}` as `{}`'.format(what, name, desc))
        
    @commands.command(pass_context=True, aliases=['unhide'])
    async def hide(self, ctx, what, name):
        '''Toggle whether the given macro is hidden.'''
        what = what.lower()
        try: macros, _ = typedict[what]
        except: await self.what_complain(); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.not_found_complain(what); return

        if not macros[name].authorised(ctx.message.author):
            await self.permission_complain(); return

        macros[name].visible ^= True
        macros.write()
        await self.say('{} {} `{}`'.format('Unhid' if macros[name].visible else 'Hid', what, name))

    @commands.command(pass_context=True, aliases=['del'])
    async def delete(self, ctx, what, name):
        '''Delete a macro by name.'''
        what = what.lower()
        try: macros, _ = typedict[what]
        except: await self.what_complain(); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.not_found_complain(what); return

        if not macros[name].authorised(ctx.message.author):
            await self.permission_complain(); return

        del macros[name]
        await self.say('Deleted {} macro `{}`.'.format(what, name))

    async def _macros(self, ctx, what, name):
        macros, _ = typedict[what]

        # Info on a specific macro
        if name != '' and name in macros:
            await self.bot.say(embed=macros[name].embed())

        # Info on all of them
        else:
            if name == 'hidden':
                what2 = 'hidden' + what
                filtered_macros = macros.hidden()
            else:
                what2 = what
                filtered_macros = macros.visible()

            if not filtered_macros:
                await self.say('No {0} macros loaded. Try adding one using >define {0}.'.format(what2))
                return

            infos = []
            infos.append('Here\'s a list of all {what2} macros, use >{what}_macros [name] to see more info on a specific one.'.format(what2=what2, what=what))
            infos.append('Use >{what}s for a list of native {what}s.\n'.format(what=what))

            colW = len(max(filtered_macros, key=len)) + 2
            for name in filtered_macros:
                print('Wahoo')
                macro = macros[name]
                info = name + ' ' * (colW-len(name))
                if macro.desc is not None:
                    info += macro.desc
                infos.append(info)

            text = texttools.block_format('\n'.join(infos))
            await self.say(text)

    @commands.command(pass_context=True, aliases=['pipe_macro', 'macro_pipes', 'macro_pipe'])
    async def pipe_macros(self, ctx, name=''):
        '''Print a list of all pipe macros and their descriptions, or details on a specific pipe macro.'''
        await self._macros(ctx, 'pipe', name)

    # I just copy-pasted the whole function and replaced "pipe" with "source", sue me.

    @commands.command(pass_context=True, aliases=['source_macro', 'macro_sources', 'macro_source'])
    async def source_macros(self, ctx, name=''):
        '''Print a list of all source macros and their descriptions, or details on a specific source macro.'''
        await self._macros(ctx, 'source', name)


# Load the bot cog
def setup(bot):
    bot.add_cog(MacroCommands(bot))