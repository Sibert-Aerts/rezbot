import discord
import re
from discord.ext import commands

from .pipes import pipes
from .sources import sources
from .macros import Macro, MacroSig, pipe_macros, source_macros
from mycommands import MyCommands
import utils.texttools as texttools

typedict = {
    'pipe': (pipe_macros, True, pipes),
    'hiddenpipe': (pipe_macros, False, pipes),
    'source': (source_macros, True, sources),
    'hiddensource': (source_macros, False, sources),
}
typedict_options = ', '.join('"' + t + '"' for t in typedict)

class MacroCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)

    async def what_complain(self, ctx):
        await ctx.send('First argument must be one of: {}.'.format(typedict_options))

    async def not_found_complain(self, ctx, what):
        await ctx.send('A {} macro by that name was not found.'.format(what))

    async def permission_complain(self, ctx):
        await ctx.send('You are not authorised to modify that macro. Try defining a new one instead.')

    @commands.command(aliases=['def'])
    async def define(self, ctx, what, name):
        '''Define a macro.'''
        what = what.lower()
        try: macros, visible, native = typedict[what]
        except: await self.what_complain(channel); return

        name = name.lower().split(' ')[0]
            await ctx.send('A {0} called "{1}" already exists, try `>redefine {0}` instead.'.format(what, name))
        if name in native or name in macros:
            return

        code = re.split('\s+', ctx.message.content, 3)[3]
        author = ctx.author
        macros[name] = Macro(name, code, author.name, author.id, str(author.avatar_url), visible=visible)
        await ctx.send('Defined a new {} called `{}` as {}'.format(what, name, texttools.block_format(code)))

    @commands.command(aliases=['redef'])
    async def redefine(self, ctx, what, name):
        '''Redefine an existing macro.'''
        what = what.lower()
        try: macros, *_ = typedict[what]
        except: await self.what_complain(ctx); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.not_found_complain(ctx, what); return

        if not macros[name].authorised(ctx.author):
            await self.permission_complain(ctx); return

        code = re.split('\s+', ctx.message.content, 3)[3]
        macros[name].code = code
        macros.write()
        await ctx.send('Redefined {} `{}` as {}'.format(what, name, texttools.block_format(code)))

    @commands.command(aliases=['desc'])
    async def describe(self, ctx, what, name):
        '''Describe an existing macro.'''
        what = what.lower()
        try: macros, *_ = typedict[what]
        except: await self.what_complain(ctx); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.not_found_complain(ctx, what); return

        if macros[name].desc and not macros[name].authorised(ctx.author):
            await self.permission_complain(ctx); return

        desc = re.split('\s+', ctx.message.content, 3)[3]
        macros[name].desc = desc
        macros.write()
        await ctx.send('Described {} `{}` as `{}`'.format(what, name, desc))

    @commands.command(aliases=['unhide'])
    async def hide(self, ctx, what, name):
        '''Toggle whether the given macro is hidden.'''
        what = what.lower()
        try: macros, *_ = typedict[what]
        except: await self.what_complain(ctx); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.not_found_complain(ctx, what); return

        if not macros[name].authorised(ctx.author):
            await self.permission_complain(ctx); return

        macros[name].visible ^= True
        macros.write()
        await ctx.send('{} {} `{}`'.format('Unhid' if macros[name].visible else 'Hid', what, name))

    @commands.command(aliases=['del'])
    async def delete(self, ctx, what, name):
        '''Delete a macro by name.'''
        what = what.lower()
        try: macros, *_ = typedict[what]
        except: await self.what_complain(ctx); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.not_found_complain(ctx, what); return

        if not macros[name].authorised(ctx.author):
            await self.permission_complain(ctx); return

        del macros[name]
        await ctx.send('Deleted {} macro `{}`.'.format(what, name))


    @commands.command(aliases=['set_sig', 'add_sig', 'add_arg'])
    async def set_arg(self, ctx, what, name, signame, sigdefault, sigdesc=None):
        '''Add or change an argument to a macro.'''
        what = what.lower()
        try: macros, *_ = typedict[what]
        except: await self.what_complain(ctx); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.not_found_complain(ctx, what); return

        if not macros[name].authorised(ctx.author):
            await self.permission_complain(ctx); return

        sig = MacroSig(signame, sigdefault, sigdesc)
        macros[name].signature[signame] = sig
        macros.write()
        await ctx.send('Added argument ({}) to {} {}'.format(sig, what, name))

    @commands.command(aliases=['delete_sig', 'del_sig', 'del_arg'])
    async def delete_arg(self, ctx, what, name, signame):
        '''Remove an argument from a macro.'''
        what = what.lower()
        try: macros, *_ = typedict[what]
        except: await self.what_complain(ctx); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.not_found_complain(ctx, what); return

        if not macros[name].authorised(ctx.author):
            await self.permission_complain(ctx); return

        del macros[name].signature[signame]
        macros.write()
        await ctx.send('Removed signature "{}" from {} {}'.format(signame, what, name))


    async def _macros(self, ctx, what, name):
        macros, *_ = typedict[what]

        # Info on a specific macro
        if name != '' and name in macros:
            await ctx.send(embed=macros[name].embed())

        # Info on all of them
        else:
            if name == 'hidden':
                what2 = 'hidden ' + what
                filtered_macros = macros.hidden()
            elif name == 'mine' or name == 'my':
                what2 = 'your ' + what
                filtered_macros = [m for m in macros if macros[m].authorId == ctx.author.id]
            else:
                what2 = what
                filtered_macros = macros.visible()

            if not filtered_macros:
                await ctx.send('No {0} macros loaded. Try adding one using >define {0}.'.format(what2))
                return

            infos = []
            infos.append('Here\'s a list of all {what2} macros, use >{what}_macros [name] to see more info on a specific one.'.format(what2=what2, what=what))
            infos.append('Use >{what}s for a list of native {what}s.\n'.format(what=what))

            colW = len(max(filtered_macros, key=len)) + 2
            for name in filtered_macros:
                macro = macros[name]
                info = name + ' ' * (colW-len(name))
                if macro.desc is not None:
                    info += macro.desc.split('\n')[0]
                infos.append(info)

            text = texttools.block_format('\n'.join(infos))
            await ctx.send(text)

    @commands.command(aliases=['pipe_macro', 'macro_pipes', 'macro_pipe'])
    async def pipe_macros(self, ctx, name=''):
        '''A list of all pipe macros, or details on a specific pipe macro.'''
        await self._macros(ctx, 'pipe', name)

    @commands.command(aliases=['source_macro', 'macro_sources', 'macro_source'])
    async def source_macros(self, ctx, name=''):
        '''A list of all source macros, or details on a specific source macro.'''
        await self._macros(ctx, 'source', name)


# Load the bot cog
def setup(bot):
    bot.add_cog(MacroCommands(bot))