import itertools
from typing import Literal

import discord
from discord.ext import commands
from discord import app_commands, Interaction
from discord.app_commands import Choice

from .pipe import Pipe, Source, Spout, Pipes
from .pipes import pipes
from .sources import sources, SourceResources
from .spouts import spouts
from .macros import Macros, Macro, MacroSig, pipe_macros, source_macros
from .events import Event, Events, events
from .macrocommands import typedict
from mycommands import MyCommands
import utils.texttools as texttools
import utils.util as util

'''
A module providing a collection of slash commands for interacting with scripting/pipes/macros/events.
'''

pipeoid_type_map: dict[str, Pipes|Macros|Events]  = {
    "Source": sources,
    "Pipe": pipes,
    "Spout": spouts,
    "Source_macro": source_macros,
    "Pipe_macro": pipe_macros,
    "Event": events,
}

async def autocomplete_pipeoid(interaction: Interaction, name: str):
    name = name.lower()
    results = []
    pipeoids = itertools.chain(*(p.values() for p in pipeoid_type_map.values()))
    for pipeoid in pipeoids:
        if name in pipeoid.name:
            if isinstance(pipeoid, Event):
                choice_name = f"{pipeoid.name} (Event)"
                value = pipeoid.name + ' Event'
            elif isinstance(pipeoid, Pipe):
                choice_name = f"{pipeoid.name} ({type(pipeoid).__name__})"
                value = pipeoid.name + ' ' + type(pipeoid).__name__
            else:
                choice_name = f"{pipeoid.name} ({pipeoid.kind} Macro)"
                value = f"{pipeoid.name} {pipeoid.kind}_macro"

            results.append(Choice(name=choice_name, value=value))
            if len(results) >= 25:
                break

    return results

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

class PipeSlashCommands(MyCommands):

    # ============================================ General Pipeoid Lookup =============================================

    @app_commands.command()
    @app_commands.describe(pipeoid='The pipeoid to look up')
    @app_commands.autocomplete(pipeoid=autocomplete_pipeoid)
    async def lookup(self, interaction: Interaction, pipeoid: str):
        ''' Look up info on a specific pipe, source, spout, macro or event. '''
        try:
            name, pipeoid_type = pipeoid.strip().split(' ')
            pipeoids = pipeoid_type_map[pipeoid_type]
            pipeoid = pipeoids[name]
        except:
            await interaction.response.send_message(f'Command failed, likely due to nonexistent lookup.', ephemeral=True)
            return

        # Get embed
        if isinstance(pipeoid, Event):
            embed = pipeoid.embed(interaction)
        else:
            embed = pipeoid.embed()

        # Take credit for native pipeoids
        if isinstance(pipeoid, Pipe):
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar)

        await interaction.response.send_message(embed=embed)


    # ================================================= Macro Listing =================================================

    async def _list_macros(self, interaction: Interaction, macros: Macros, hidden: bool, mine: bool):
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

    @app_commands.command()
    @app_commands.describe(hidden='If true, shows (only) hidden macros', mine='If true, only shows your authored macros')
    async def pipe_macros(self, interaction: Interaction, hidden: bool=False, mine: bool=False):
        ''' Display a list of pipe macros. '''
        await self._list_macros(interaction, pipe_macros, hidden, mine)

    @app_commands.command()
    @app_commands.describe(hidden='If true, shows (only) hidden macros', mine='If true, only shows your authored macros')
    async def source_macros(self, interaction: Interaction, hidden: bool=False, mine: bool=False):
        ''' Display a list of source macros. '''
        await self._list_macros(interaction, source_macros, hidden, mine)


    # ================================================ Macro Management ===============================================

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



# Load the bot cog
async def setup(bot: commands.Bot):
    await bot.add_cog(PipeSlashCommands(bot))