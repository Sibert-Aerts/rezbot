'''
A module providing a collection of slash commands for interacting with Macros.
'''

from typing import Literal

from discord.ext import commands
from discord import app_commands, Interaction

from pipes.macros import Macro, Macros, MacroSig, pipe_macros, source_macros
from mycommands import MyCommands
import utils.texttools as texttools
from utils.util import normalize_name

from pipes.views import MacroView
from .slash_commands_util import (
    scriptoid_type_map, macro_check_map, autocomplete_macro, choice_to_scriptoid,
)

class MacroSlashCommands(MyCommands):

    # ================================================ Macro Listing ================================================

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
        ''' Display a list of Pipe Macros. '''
        await self._list_macros(interaction, pipe_macros, hidden, mine)

    @app_commands.command()
    @app_commands.describe(hidden='If true, shows (only) hidden macros', mine='If true, only shows your authored macros')
    async def source_macros(self, interaction: Interaction, hidden: bool=False, mine: bool=False):
        ''' Display a list of Source Macros. '''
        await self._list_macros(interaction, source_macros, hidden, mine)


    # ================================================ Macro Management ===============================================

    macro_group = app_commands.Group(name='macro', description='Define, redefine, describe or delete Macros.')
    ''' The `/macro <action>` command group'''

    @macro_group.command(name='define')
    @app_commands.describe(
        macro_type="The type of Macro",
        name="The name of the Macro",
        code="The code to define the Macro as",
        description="The Macro's description",
        hidden="Whether the Macro should show up in the general Macro list",
        force="Force the Macro to save even if there are errors"
    )
    @app_commands.rename(macro_type="type")
    async def macro_define(self, interaction: Interaction,
        macro_type: Literal['Pipe', 'Source'],
        name: str,
        code: str,
        description: str=None,
        hidden: bool=False,
        force: bool=False
    ):
        ''' Define a new Macro. '''
        reply = interaction.response.send_message
        author = interaction.user
        
        natives = scriptoid_type_map[macro_type]
        macros = scriptoid_type_map[macro_type + '_macro']
        
        name = normalize_name(name)
        if name in natives or name in macros:
            return await reply(f'A {macro_type} called `{name}` already exists, try the `/macro edit` command.')

        check = macro_check_map[macros.kind]
        if not force and not await check(code, reply):
            return await interaction.channel.send('Run the command again with `force: True` to save it anyway.')            

        macro = Macro(macros.kind, name, code, author.name, author.id, desc=description, visible=not hidden)
        macros[name] = macro
        view = MacroView(macro, macros)
        embed = macro.embed(bot=self.bot, channel=interaction.channel)
        view.set_message(await reply(f'Successfully defined a new {macro_type} macro.', embed=embed, view=view))

    @macro_group.command(name='edit')
    @app_commands.describe(
        macro_choice="The Macro to edit",
        code="If given, the Macro's new code",
        description="If given, the Macro's new description",
        hidden="If given, the Macro's new visibility",
        force="Force the Macro to save even if there are errors"
    )
    @app_commands.autocomplete(macro_choice=autocomplete_macro)
    @app_commands.rename(macro_choice='macro')
    async def macro_edit(self, interaction: Interaction,
        macro_choice: str,
        code: str=None,
        description: str=None,
        hidden: bool=None,
        force: bool=None
    ):
        ''' Redefine one or more fields on an existing Macro. '''
        reply = interaction.response.send_message
        author = interaction.user

        try:
            macro, macros = choice_to_scriptoid(macro_choice, Macro)
        except:
            return await reply(f'Command failed, likely due to nonexistent Macro.', ephemeral=True)
        if not macro.authorised(author):
            return await reply('You are not authorised to modify that Macro. Try defining a new one instead.', ephemeral=True)

        check = macro_check_map[macros.kind]
        if not force and code and not await check(code, reply):
            return await interaction.channel.send('Run the command again with `force: True` to save it anyway.')

        if code is not None:
            macro.code = code
        if description is not None:
            macro.desc = description
        if hidden is not None:
            macro.visible = not hidden

        macros.write()
        view = MacroView(macro, macros)
        embed = macro.embed(bot=self.bot, channel=interaction.channel)
        view.set_message(await reply(f'Successfully edited the {macro.kind} Macro.', embed=embed, view=view))

    @macro_group.command(name='delete')
    @app_commands.describe(macro_choice="The Macro to delete")
    @app_commands.autocomplete(macro_choice=autocomplete_macro)
    @app_commands.rename(macro_choice='macro')
    async def macro_delete(self, interaction: Interaction, macro_choice: str):
        ''' Delete a Macro. '''
        reply = interaction.response.send_message
        author = interaction.user
    
        try:
            macro, macros = choice_to_scriptoid(macro_choice, Macro)
        except:
            return await reply(f'Command failed, likely due to nonexistent Macro.', ephemeral=True)
        if not macro.authorised(author):
            return await reply('You are not authorised to modify that Macro.')

        del macros[macro.name]
        await reply(f'Successfully deleted {macros.kind} Macro `{macro.name}`.')

    @macro_group.command(name='set_param')
    @app_commands.describe(
        macro_choice="The Macro",
        param="The name of the parameter to assign",
        description="The parameter's description to assign",
        default="The parameter's default value to assign",
        delete="If True, will delete this parameter instead",
    )
    @app_commands.autocomplete(macro_choice=autocomplete_macro)
    @app_commands.rename(macro_choice='macro')
    async def macro_set_param(self, interaction: Interaction,
        macro_choice: str,
        param: str,
        description: str=None,
        default: str=None,
        delete: bool=False,
    ):
        ''' Add, overwrite or delete a parameter on a Macro. '''
        reply = interaction.response.send_message
        author = interaction.user

        try:
            macro, macros = choice_to_scriptoid(macro_choice, Macro)
            param = normalize_name(param)
        except:
            return await reply(f'Command failed, likely due to nonexistent Macro.', ephemeral=True)
        if not macro.authorised(author):
            return await reply(f'You are not authorised to modify {macro.kind} Macro {macro.name}.', ephemeral=True)
        if not param:
            return await reply(f'Please use a valid parameter name.', ephemeral=True)

        existed = (param in macro.signature)
        if not delete:
            par = MacroSig(param, default, description)
            macro.signature[param] = par
        elif existed:
            del macro.signature[param]
        else:
            return await reply(f'Parameter `{param}` does not exist on {macro.kind} Macro {macro.name}.', ephemeral=True)

        macros.write()
        verbed = 'deleted' if delete else 'overwrote' if existed else 'added'
        embed = macro.embed(bot=self.bot, channel=interaction.channel)
        await reply(f'Successfully {verbed} parameter `{param}` on {macro.kind} Macro {macro.name}.', embed=embed)


# Load the bot cog
async def setup(bot: commands.Bot):
    await bot.add_cog(MacroSlashCommands(bot))