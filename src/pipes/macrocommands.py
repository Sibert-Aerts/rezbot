import discord
import re
from discord.ext import commands

from .pipes import pipes
from .sources import sources
from .macros import Macro, MacroSig, pipe_macros, source_macros
import utils.texttools as texttools

typedict = {
    'pipe': (pipe_macros, True, pipes),
    'hiddenpipe': (pipe_macros, False, pipes),
    'source': (source_macros, True, sources),
    'hiddensource': (source_macros, False, sources),
}
typedict_options = ', '.join('"' + t + '"' for t in typedict)


class MacroCommands(commands.Cog):
    async def what_complain(self, channel):
        await channel.send('First argument must be one of: {}.'.format(typedict_options))

    async def not_found_complain(self, channel, what):
        await channel.send('A {} macro by that name was not found.'.format(what))

    async def permission_complain(self, channel):
        await channel.send('You are not authorised to modify that macro. Try defining a new one instead.')

    @commands.command(aliases=['def'])
    async def define(self, ctx, what, name):
        await self._define(ctx.message, what, name, re.split('\s+', ctx.message.content, 3)[3])

    async def _define(self, message, what, name, code):
        '''Define a macro.'''
        channel = message.channel
        what = what.lower()
        try: macros, visible, native = typedict[what]
        except: await self.what_complain(channel); return

        name = name.lower().split(' ')[0]
        if name in native or name in macros:
            await channel.send('A {0} called "{1}" already exists, try `>redefine {0}` instead.'.format(what, name))
            return

        author = message.author
        macros[name] = Macro(name, code, author.name, author.id, str(author.avatar_url), visible=visible)
        await channel.send('Defined a new {} macro called `{}` as {}'.format(what, name, texttools.block_format(code)))

    @commands.command(aliases=['redef'])
    async def redefine(self, ctx, what, name):
        await self._redefine(ctx.message, what, name, re.split('\s+', ctx.message.content, 3)[3])

    async def _redefine(self, message, what, name, code):
        '''Redefine an existing macro.'''
        channel = message.channel
        what = what.lower()
        try: macros, *_ = typedict[what]
        except: await self.what_complain(channel); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.not_found_complain(channel, what); return

        if not macros[name].authorised(message.author):
            await self.permission_complain(channel); return

        macros[name].code = code
        macros.write()
        await channel.send('Redefined {} `{}` as {}'.format(what, name, texttools.block_format(code)))

    @commands.command(aliases=['desc'])
    async def describe(self, ctx, what, name):
        await self._describe(ctx.message, what, name, re.split('\s+', ctx.message.content, 3)[3])

    async def _describe(self, message, what, name, desc):
        '''Describe an existing macro.'''
        channel = message.channel
        what = what.lower()
        try: macros, *_ = typedict[what]
        except: await self.what_complain(channel); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.not_found_complain(channel, what); return

        if macros[name].desc and not macros[name].authorised(message.author):
            await self.permission_complain(channel); return

        macros[name].desc = desc
        macros.write()
        await channel.send('Described {} `{}` as `{}`'.format(what, name, desc))

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
                    info += macro.desc.split('\n')[0][:100]
                infos.append(info)

            blocks = [[]]
            l = 0
            for info in infos:
                if l + len(info) > 1800:
                    blocks.append([])
                    l = 0
                l += len(info)
                blocks[-1].append(info)
            
            for block in blocks:
                await ctx.send(texttools.block_format('\n'.join(block)))

    @commands.command(aliases=['pipe_macro', 'macro_pipes', 'macro_pipe'])
    async def pipe_macros(self, ctx, name=''):
        '''A list of all pipe macros, or details on a specific pipe macro.'''
        await self._macros(ctx, 'pipe', name)

    @commands.command(aliases=['source_macro', 'macro_sources', 'macro_source'])
    async def source_macros(self, ctx, name=''):
        '''A list of all source macros, or details on a specific source macro.'''
        await self._macros(ctx, 'source', name)

#                                   command       what    name     value
command_regex = re.compile(r'\s*(NEW|EDIT|DESC)\s+(\w+)\s+(\S+)\s*::(.*)', re.S)

async def parse_macro_command(command, message):
    mc = MacroCommands()

    m = re.match(command_regex, command)
    if m is None:
        print('Error: failed to parse command: {}'.format(command))
        await message.channel.send('Error: Poorly formed command.')

    COM, what, name, value = m.groups()
    what = what.lower()
    if COM == 'NEW':
        await mc._define(message, what, name, value)
    elif COM == 'EDIT':
        await mc._redefine(message, what, name, value)
    elif COM == 'DESC':
        await mc._describe(message, what, name, value)



# Load the bot cog
def setup(bot):
    bot.add_cog(MacroCommands())