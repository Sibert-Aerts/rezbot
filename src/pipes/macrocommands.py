import itertools
import re
from typing import Any, Callable, Literal

import discord
from discord import app_commands, Interaction
from discord.app_commands import Choice
from discord.ext import commands


from .pipe import Pipes
from .processor import Pipeline, PipelineProcessor
from .pipes import pipes
from .sources import sources
from .macros import Macro, MacroSig, Macros, pipe_macros, source_macros
import utils.texttools as texttools
from mycommands import MyCommands


async def check_pipe_macro(code, reply):
    ''' Statically analyses pipe macro code for errors or warnings. '''
    errors = Pipeline(code).parser_errors
    if not errors: 
        return True
    if errors.terminal:
        await reply('Failed to save macro due to parsing errors:', embeds=[errors.embed()])
        return False
    else:
        await reply('Encountered warnings while parsing macro:', embeds=[errors.embed()])
        return True

async def check_source_macro(code, reply):
    ''' Statically analyses source macro code for errors or warnings. '''
    _, code = PipelineProcessor.split(code)
    return await check_pipe_macro(code, reply)
    

typedict: dict[str, tuple[Macros, bool, Pipes, Callable]] = {
    'pipe':         (pipe_macros, True,  pipes, check_pipe_macro),
    'hiddenpipe':   (pipe_macros, False, pipes, check_pipe_macro),
    'source':       (source_macros, True,  sources, check_source_macro),
    'hiddensource': (source_macros, False, sources, check_source_macro),
}
typedict_options = ', '.join('"' + t + '"' for t in typedict)

async def autocomplete_macro(interaction: Interaction, name: str):
    name = name.lower()
    results = []
    for macro in itertools.chain(pipe_macros.values(), source_macros.values()):
        if name in macro.name:
            choice_name = f"{macro.name} ({macro.kind})"
            value = macro.name + " " + macro.kind.lower()
            results.append(Choice(name=choice_name, value=value))
            if len(results) >= 25:
                break
    return results

def autocomplete_bound_macro(macros):
    async def _autocomplete_bound_macro(interaction: Interaction, name: str):
        name = name.lower()
        results = []
        for macro in macros.values():
            if name in macro.name:
                results.append(Choice(name=macro.name, value=macro.name))
                if len(results) >= 25:
                    break
        return results
    return _autocomplete_bound_macro


class MacroCommands(MyCommands):
    FORCE_MACRO_CACHE = None

    async def what_complain(self, channel):
        await channel.send('First argument must be one of: {}.'.format(typedict_options))

    async def not_found_complain(self, channel, what):
        await channel.send('A {} macro by that name was not found.'.format(what))

    async def permission_complain(self, channel):
        await channel.send('You are not authorised to modify that macro. Try defining a new one instead.')

    # ========================== Macro Management (message-commands) ==========================

    @commands.command(aliases=['def'])
    async def define(self, ctx, what, name):
        await self._define(ctx.message, what, name, re.split('\s+', ctx.message.content, 3)[3])

    async def _define(self, message: discord.Message, what, name, code, force=False):
        '''Define a macro.'''
        channel = message.channel
        what = what.lower()
        try: macros, visible, native, check = typedict[what]
        except: await self.what_complain(channel); return

        name = name.lower().split(' ')[0]
        if name in native or name in macros:
            await channel.send('A {0} called `{1}` already exists, try `>redefine {0}` instead.'.format(what, name))
            return

        if not force and not await check(code, channel.send):
            MacroCommands.FORCE_MACRO_CACHE = ('new', message, what, name, code)
            await channel.send('Reply `>force_macro` to save it anyway.')
            return

        author = message.author
        macros[name] = Macro(macros.kind, name, code, author.name, author.id, visible=visible)
        await channel.send('Defined a new {} macro called `{}` as {}'.format(what, name, texttools.block_format(code)))

    @commands.command(aliases=['redef'])
    async def redefine(self, ctx, what, name):
        await self._redefine(ctx.message, what, name, re.split('\s+', ctx.message.content, 3)[3])

    async def _redefine(self, message: discord.Message, what, name, code, force=False):
        '''Redefine an existing macro.'''
        channel = message.channel
        what = what.lower()
        try: macros, _, _, check = typedict[what]
        except: await self.what_complain(channel); return

        name = name.lower().split(' ')[0]
        if name not in macros:
            await self.not_found_complain(channel, what); return

        if not macros[name].authorised(message.author):
            await self.permission_complain(channel); return

        if not force and not await check(code, channel.send):
            MacroCommands.FORCE_MACRO_CACHE = ('edit', message, what, name, code)
            await channel.send('Reply `>force_macro` to save it anyway.')
            return

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


    # ========================== Macro Management (app-commands) ==========================

    macro_group = app_commands.Group(name='macro', description='Define, redefine, describe or delete a macro')
    ''' The `/macro <action>` command group'''

    @macro_group.command(name='define')
    @app_commands.describe(
        macro_type="The type of macro",
        name="The name of the macro",
        code="The code to define the macro as",
        description="The macro's description",
        hidden="Whether the macro should show up in the general macro list",
        force="Force the macro to save even if there are errors"
    )
    @app_commands.rename(macro_type="type")
    async def macro_define(self, interaction: Interaction,
        macro_type: Literal['pipe', 'source'],
        name: str,
        code: str,
        description: str=None,
        hidden: bool=False,
        force: bool=False
    ):
        ''' Define a new macro. '''
        author = interaction.user
        macros, _, natives, check = typedict[macro_type]
        
        def reply(text: str, **kwargs):
            return interaction.response.send_message(text, **kwargs)

        name = name.split(' ')[0].lower()
        if name in natives or name in macros:
            await reply(f'A {macro_type} called `{name}` already exists, try the `/redefine` command.')
            return

        if not force and not await check(code, reply):
            await interaction.channel.send('Run the command again with `force: True` to save it anyway.')
            return

        macro = Macro(macros.kind, name, code, author.name, author.id, desc=description, visible=not hidden)
        macros[name] = macro
        await reply(f'Successfully defined a new {macro_type} macro.', embed=macro.embed(interaction))

    @macro_group.command(name='edit')
    @app_commands.describe(
        macro="The macro to edit",
        code="If given, the macro's new code",
        description="If given, the macro's new description",
        hidden="If given, the macro's new visibility",
        force="Force the macro to save even if there are errors"
    )
    @app_commands.autocomplete(macro=autocomplete_macro)
    async def macro_edit(self, interaction: Interaction,
        macro: str,
        code: str=None,
        description: str=None,
        hidden: bool=None,
        force: bool=None
    ):
        ''' Redefine one or more fields on an existing macro. '''
        author = interaction.user
        name, macro_type = macro.split(' ')
        macros, _, natives, check = typedict[macro_type]

        def reply(text: str, **kwargs):
            return interaction.response.send_message(text, **kwargs)

        name = name.split(' ')[0].lower()
        if name not in macros:
            await reply(f'A {macro_type} macro by that name was not found.')
            return
        macro = macros[name]

        if not macro.authorised(author):
            await reply('You are not authorised to modify that macro. Try defining a new one instead.')
            return

        if not force and code and not await check(code, reply):
            await interaction.channel.send('Run the command again with `force: True` to save it anyway.')
            return

        if code is not None:
            macro.code = code
        if description is not None:
            macro.desc = description
        if hidden is not None:
            macro.visible = not hidden

        macros.write()
        await reply(f'Successfully edited the {macro_type} macro.', embed=macro.embed(interaction))

    @macro_group.command(name='delete')
    @app_commands.describe(macro="The macro to delete")
    @app_commands.autocomplete(macro=autocomplete_macro)
    async def macro_delete(self, interaction: Interaction, macro: str):
        ''' Delete a macro. '''
        author = interaction.user
        name, macro_type = macro.split(' ')
        macros, *_ = typedict[macro_type]

        def reply(text: str, **kwargs):
            return interaction.response.send_message(text, **kwargs)

        name = name.split(' ')[0].lower()
        if name not in macros:
            await reply(f'A {macro_type} macro by that name was not found.')
            return
        macro = macros[name]

        if not macro.authorised(author):
            await reply('You are not authorised to modify that macro.')
            return

        del macros[name]
        await reply(f'Successfully deleted {macro_type} macro `{name}`.')

    @macro_group.command(name='set_param')
    @app_commands.describe(
        macro="The macro",
        param="The name of the parameter to assign",
        description="The parameter's description to assign",
        default="The parameter's default value to assign",
    )
    @app_commands.autocomplete(macro=autocomplete_macro)
    async def macro_edit(self, interaction: Interaction,
        macro: str,
        param: str,
        description: str=None,
        default: str=None,
    ):
        ''' Add or overwrite a parameter on a macro. '''
        author = interaction.user
        name, macro_type = macro.split(' ')
        macros, *_ = typedict[macro_type]

        def reply(text: str, **kwargs):
            return interaction.response.send_message(text, **kwargs)

        name = name.split(' ')[0].lower()
        if name not in macros:
            await reply(f'A {macro_type} macro by that name was not found.')
            return
        macro = macros[name]

        if not macro.authorised(author):
            await reply('You are not authorised to modify that macro.')
            return

        is_overwrite = (param in macro.signature)
        par = MacroSig(param, default, description)
        macro.signature[param] = par
        macros.write()

        verbed = "overwrote" if is_overwrite else "added"
        await reply(f'Successfully {verbed} parameter `{param}`.', embed=macro.embed(interaction))


    # ========================== Macro listing ==========================

    async def _macros(self, ctx, what, name):
        macros, *_ = typedict[what]

        # Info on a specific macro
        if name != '' and name in macros:
            await ctx.send(embed=macros[name].embed(ctx))

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


    @commands.command(name='pipe_macros', aliases=['pipe_macro', 'macro_pipes', 'macro_pipe'])
    async def pipe_macros_command(self, ctx, name=''):
        '''A list of all pipe macros, or details on a specific pipe macro.'''
        await self._macros(ctx, 'pipe', name)

    @commands.command(name='source_macros', aliases=['source_macro', 'macro_sources', 'macro_source'])
    async def source_macros_command(self, ctx, name=''):
        '''A list of all source macros, or details on a specific source macro.'''
        await self._macros(ctx, 'source', name)


    # ========================== Macro listing (app-commands) ==========================

    async def _macros_app_command(self, interaction: Interaction, macros: Macros, hidden: bool, mine: bool):
        '''Reply with a list of macros.'''
        what = macros.kind.lower()
        qualified_what = what

        ## Filter based on the given name
        filtered_macros = macros.hidden() if hidden else macros.visible()
        if hidden:
            qualified_what = 'hidden ' + what
        if mine:
            author = interaction.user
            filtered_macros = [m for m in filtered_macros if int(macros[m].authorId) == author.id]
            qualified_what = 'your ' + what

        if not filtered_macros:
            await interaction.response.send_message(f'No {qualified_what} macros found.')
            return

        ## Boilerplate
        infos = []
        infos.append(f'Here\'s a list of all {qualified_what} macros, use /{what}_macro [name] to see more info on a specific one.')
        infos.append(f'Use /{what} for a list of native {qualified_what}s.')

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
        
        first = True
        for block in texttools.block_chunk_lines(infos):
            if first:
                await interaction.response.send_message(block)
                first = False
            else:
                await interaction.channel.send(block)

    @app_commands.command(name='pipe_macro')
    @app_commands.describe(hidden='If true, shows (only) hidden macros', mine='If true, only shows your authored macros')
    async def pipe_macros(self, interaction: Interaction, hidden: bool=False, mine: bool=False):
        ''' List pipe macros. '''
        await self._macros_app_command(interaction, pipe_macros, hidden, mine)

    @app_commands.command(name='source_macro')
    @app_commands.describe(hidden='If true, shows (only) hidden macros', mine='If true, only shows your authored macros')
    async def source_macros(self, interaction: Interaction, hidden: bool=False, mine: bool=False):
        ''' List source macros. '''
        await self._macros_app_command(interaction, source_macros, hidden, mine)

    # ========================== Dumping macros ==========================

    @commands.command(hidden=True)
    async def dump_pipe_macros(self, ctx):
        '''Uploads the raw file containing all pipe macros, for archival/backup/debug purposes.'''
        await ctx.send(file=discord.File(pipe_macros.DIR(pipe_macros.filename)))

    @commands.command(hidden=True)
    async def dump_source_macros(self, ctx):
        '''Uploads the raw file containing all source macros, for archival/backup/debug purposes.'''
        await ctx.send(file=discord.File(source_macros.DIR(source_macros.filename)))



command_regex = re.compile(r'\s*(NEW|EDIT|DESC)\s+(hidden)?(pipe|source)\s+([_a-z]\w+)\s*::\s*(.*)', re.S | re.I)
#                                ^^^command^^^     ^^^^^^^^what^^^^^^^^     ^^name^^^         code

async def parse_macro_command(bot, command, message):
    mc = bot.get_cog('MacroCommands')

    m = re.match(command_regex, command)
    if m is None: return False

    COM, wh, at, name, code = m.groups()
    what = (wh or '')+at
    what = what.lower()
    if COM == 'NEW':
        await mc._define(message, what, name, code)
    elif COM == 'EDIT':
        await mc._redefine(message, what, name, code)
    elif COM == 'DESC':
        await mc._describe(message, what, name, code)

    return True



# Load the bot cog
async def setup(bot):
    await bot.add_cog(MacroCommands(bot))