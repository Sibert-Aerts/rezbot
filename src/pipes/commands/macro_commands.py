import re
from typing import Callable

import discord
from discord.ext import commands

from pipes.views.macro_views import MacroView

from pipes.core.pipe import Pipes
from pipes.core.pipeline import Pipeline
from pipes.implementations.pipes import NATIVE_PIPES
from pipes.implementations.sources import NATIVE_SOURCES
from pipes.core.macros import Macro, MacroParam, Macros, MACRO_PIPES, MACRO_SOURCES
import utils.texttools as texttools
from utils.util import normalize_name
from rezbot_commands import RezbotCommands


async def check_pipe_macro(code: str, reply):
    ''' Statically analyses pipe macro code for errors or warnings. '''
    errors = Pipeline.from_string(code).get_static_errors()
    if not errors:
        return True
    if errors.terminal:
        await reply('Failed to save Macro due to parsing errors:', embeds=[errors.embed()])
        return False
    else:
        await reply('Encountered warnings while parsing Macro:', embeds=[errors.embed()])
        return True


async def check_source_macro(code: str, reply):
    ''' Statically analyses source macro code for errors or warnings. '''
    errors = Pipeline.from_string_with_origin(code).get_static_errors()
    if not errors:
        return True
    if errors.terminal:
        await reply('Failed to save Macro due to parsing errors:', embeds=[errors.embed()])
        return False
    else:
        await reply('Encountered warnings while parsing Macro:', embeds=[errors.embed()])
        return True


typedict: dict[str, tuple[Macros, bool, Pipes, Callable]] = {
    'pipe':         (MACRO_PIPES, True,  NATIVE_PIPES, check_pipe_macro),
    'hiddenpipe':   (MACRO_PIPES, False, NATIVE_PIPES, check_pipe_macro),
    'source':       (MACRO_SOURCES, True,  NATIVE_SOURCES, check_source_macro),
    'hiddensource': (MACRO_SOURCES, False, NATIVE_SOURCES, check_source_macro),
}
typedict_options = ', '.join('"' + t + '"' for t in typedict)


class MacroCommands(RezbotCommands):
    FORCE_MACRO_CACHE = None

    async def what_complain(self, channel):
        await channel.send('First argument must be one of: {}.'.format(typedict_options))

    async def not_found_complain(self, channel, what):
        await channel.send('A {} macro by that name was not found.'.format(what))

    async def permission_complain(self, channel):
        await channel.send('You are not authorised to modify that macro. Try defining a new one instead.')

    # ========================== Macro Management (message-commands) ==========================

    @commands.command(aliases=['def'], hidden=True)
    async def define(self, ctx, what, name):
        await self._define(ctx.message, what, name, re.split('\s+', ctx.message.content, 3)[3])

    async def _define(self, message: discord.Message, what, name, code, force=False):
        '''Define a macro.'''
        channel = message.channel
        what = what.lower()
        try: macros, visible, native, check = typedict[what]
        except: await self.what_complain(channel); return

        name = normalize_name(name)
        if name in native or name in macros:
            await channel.send('A {0} called `{1}` already exists, try `>redefine {0}` instead.'.format(what, name))
            return

        if not force and not await check(code, channel.send):
            MacroCommands.FORCE_MACRO_CACHE = ('new', message, what, name, code)
            await channel.send('Reply `>force_macro` to save it anyway.')
            return

        author = message.author
        macro = macros[name] = Macro(macros.kind, name, code, author.name, author.id, visible=visible)

        view = MacroView(macro, macros)
        view.set_message(await channel.send('Defined a new macro.', embed=macro.embed(bot=self.bot, channel=message.channel), view=view))

    @commands.command(aliases=['redef'], hidden=True)
    async def redefine(self, ctx, what, name):
        await self._redefine(ctx.message, what, name, re.split('\s+', ctx.message.content, 3)[3])

    async def _redefine(self, message: discord.Message, what, name, code, force=False):
        '''Redefine an existing macro.'''
        channel = message.channel
        what = what.lower()
        try: macros, _, _, check = typedict[what]
        except: return await self.what_complain(channel)

        name = normalize_name(name)
        if name not in macros:
            return await self.not_found_complain(channel, what)
        macro = macros[name]

        if not macro.authorised(message.author):
            return await self.permission_complain(channel)

        if not force and not await check(code, channel.send):
            MacroCommands.FORCE_MACRO_CACHE = ('edit', message, what, name, code)
            await channel.send('Reply `>force_macro` to save it anyway.')
            return

        macro.code = code
        macros.write()
        view = MacroView(macro, macros)
        view.set_message(await channel.send('Redefined the Macro.', embed=macro.embed(bot=self.bot, channel=message.channel), view=view))

    @commands.command(aliases=['desc'], hidden=True)
    async def describe(self, ctx, what, name):
        await self._describe(ctx.message, what, name, re.split('\s+', ctx.message.content, 3)[3])

    async def _describe(self, message: discord.Message, what, name, desc):
        '''Describe an existing macro.'''
        channel = message.channel
        what = what.lower()
        try: macros, *_ = typedict[what]
        except: return await self.what_complain(channel)

        name = normalize_name(name)
        if name not in macros:
            return await self.not_found_complain(channel, what)
        macro = macros[name]

        if not macro.authorised(message.author):
            return await self.permission_complain(channel)

        macro.desc = desc
        macros.write()
        view = MacroView(macro, macros)
        view.set_message(await channel.send('Updated the Macro\'s description.', embed=macro.embed(bot=self.bot, channel=message.channel), view=view))

    @commands.command(aliases=['unhide'], hidden=True)
    async def hide(self, ctx, what, name):
        '''Toggle whether the given macro is hidden.'''
        what = what.lower()
        try: macros, *_ = typedict[what]
        except: await self.what_complain(ctx); return

        name = normalize_name(name)
        if name not in macros:
            await self.not_found_complain(ctx, what); return

        if not macros[name].authorised(ctx.author):
            await self.permission_complain(ctx); return

        macros[name].visible ^= True
        macros.write()
        await ctx.send('{} {} `{}`'.format('Unhid' if macros[name].visible else 'Hid', what, name))

    @commands.command(aliases=['del'], hidden=True)
    async def delete(self, ctx, what, name):
        '''Delete a macro by name.'''
        what = what.lower()
        try: macros, *_ = typedict[what]
        except: await self.what_complain(ctx); return

        name = normalize_name(name)
        if name not in macros:
            await self.not_found_complain(ctx, what); return

        if not macros[name].authorised(ctx.author):
            await self.permission_complain(ctx); return

        del macros[name]
        await ctx.send('Deleted {} macro `{}`.'.format(what, name))

    @commands.command(hidden=True)
    async def force_macro(self, ctx):
        ''' Force the bot to save the most recently rejected macro. '''
        if MacroCommands.FORCE_MACRO_CACHE is None: return
        (cmd, message, what, name, code) = MacroCommands.FORCE_MACRO_CACHE
        if not message.channel == ctx.channel: return

        if cmd == 'new':
            await self._define(message, what, name, code, force=True)
        elif cmd == 'edit':
            await self._redefine(message, what, name, code, force=True)

        MacroCommands.FORCE_MACRO_CACHE = None


    @commands.command(aliases=['add_arg', 'set_sig', 'add_sig', 'set_param', 'add_param'], hidden=True)
    async def set_arg(self, ctx, what, name, signame, sigdefault, sigdesc=None):
        '''Add or change an argument to a macro.'''
        what = what.lower()
        try: macros, *_ = typedict[what]
        except: await self.what_complain(ctx); return

        name = normalize_name(name)
        if name not in macros:
            await self.not_found_complain(ctx, what); return

        if not macros[name].authorised(ctx.author):
            await self.permission_complain(ctx); return

        sig = MacroParam(signame, sigdefault, sigdesc)
        macros[name].signature[signame] = sig
        macros.write()
        await ctx.send('Added argument ({}) to {} {}'.format(sig, what, name))

    @commands.command(aliases=['delete_sig', 'del_sig', 'del_arg'], hidden=True)
    async def delete_arg(self, ctx, what, name, signame):
        '''Remove an argument from a macro.'''
        what = what.lower()
        try: macros, *_ = typedict[what]
        except: await self.what_complain(ctx); return

        name = normalize_name(name)
        if name not in macros:
            await self.not_found_complain(ctx, what); return

        if not macros[name].authorised(ctx.author):
            await self.permission_complain(ctx); return

        del macros[name].signature[signame]
        macros.write()
        await ctx.send('Removed signature "{}" from {} {}'.format(signame, what, name))


    # ========================== Macro listing ==========================

    async def _macros(self, ctx: commands.Context, what, name):
        macros, *_ = typedict[what]

        # Info on a specific macro
        if name != '' and name in macros:
            macro = macros[name]
            view = MacroView(macro, macros)
            view.set_message(await ctx.send(embed=macro.embed(bot=self.bot, channel=ctx.channel), view=view))

        # Info on all of them
        else:
            ## Filter based on the given name
            if name == 'hidden':
                what2 = 'hidden ' + what
                filtered_macros = macros.hidden()
            elif name == 'mine' or name == 'my':
                what2 = 'your ' + what
                filtered_macros = [m for m in macros if int(macros[m].authorId) == ctx.author.id]
            else:
                what2 = what
                filtered_macros = macros.visible()

            if not filtered_macros:
                await ctx.send('No {0} macros found.'.format(what2))
                return

            ## Boilerplate
            infos = []
            infos.append('Here\'s a list of all {what2} macros, use >{what}_macros [name] to see more info on a specific one.'.format(what2=what2, what=what))
            infos.append('Use >{what}s for a list of native {what}s.'.format(what=what))

            ## Separate those with and without descriptions
            desced_macros = [m for m in filtered_macros if macros[m].desc]
            undesced_macros = [m for m in filtered_macros if not macros[m].desc]

            ## Format the ones who have a description as a nice two-column block
            if desced_macros:
                infos.append('')
                colW = len(max(desced_macros, key=len)) + 2
                for name in desced_macros:
                    macro = macros[name]
                    info = name +  ' ' * (colW-len(name))
                    desc = macro.desc.split('\n', 1)[0]
                    info += desc if len(desc) <= 80 else desc[:75] + '(...)'
                    infos.append(info)

            ## Format the other ones as just a list
            if undesced_macros:
                infos.append('\nWithout descriptions:')
                infos += texttools.line_chunk_list(undesced_macros)

            for block in texttools.block_chunk_lines(infos): await ctx.send(block)

    @commands.command(name='pipe_macros', aliases=['pipe_macro', 'macro_pipes', 'macro_pipe'], hidden=True)
    async def pipe_macros_command(self, ctx, name=''):
        '''A list of all pipe macros, or details on a specific pipe macro.'''
        await self._macros(ctx, 'pipe', name)

    @commands.command(name='source_macros', aliases=['source_macro', 'macro_sources', 'macro_source'], hidden=True)
    async def source_macros_command(self, ctx, name=''):
        '''A list of all source macros, or details on a specific source macro.'''
        await self._macros(ctx, 'source', name)


    # ========================== Dumping macros ==========================

    @commands.command(hidden=True)
    async def dump_pipe_macros(self, ctx):
        '''Uploads the raw file containing all pipe macros, for archival/backup/debug purposes.'''
        await ctx.send(file=discord.File(MACRO_PIPES.DIR(MACRO_PIPES.json_filename)))

    @commands.command(hidden=True)
    async def dump_source_macros(self, ctx):
        '''Uploads the raw file containing all source macros, for archival/backup/debug purposes.'''
        await ctx.send(file=discord.File(MACRO_SOURCES.DIR(MACRO_SOURCES.json_filename)))


command_regex = re.compile(r'\s*(NEW|EDIT|DESC)\s+(hidden)?(pipe|source)\s+([_a-z]\w+)\s*::\s*(.*)', re.S | re.I)
#                                ^^^command^^^     ^^^^^^^^what^^^^^^^^     ^^name^^^         code

async def parse_macro_command(bot, command, message):
    mc = bot.get_cog('MacroCommands')

    m = re.match(command_regex, command)
    if m is None: return False

    command, wh, at, name, code = m.groups()
    what = ((wh or '') + at).lower()

    if command == 'NEW':
        await mc._define(message, what, name, code)
    elif command == 'EDIT':
        await mc._redefine(message, what, name, code)
    elif command == 'DESC':
        await mc._describe(message, what, name, code)

    return True



# Load the bot cog
async def setup(bot):
    await bot.add_cog(MacroCommands(bot))
