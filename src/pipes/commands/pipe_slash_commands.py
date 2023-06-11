'''
A module providing a collection of slash commands for interacting with native Pipes, Sources and Spouts, as well as looking up any kind of Scriptoid.
'''
from discord.ext import commands
from discord import app_commands, Interaction, utils
from discord.app_commands import Choice

from pipes.pipe import Pipeoid, Pipes, Sources, Spouts
from pipes.implementations.pipes import pipes
from pipes.implementations.sources import sources
from pipes.implementations.spouts import spouts
from pipes.macros import Macro
from pipes.events import Event
from mycommands import MyCommands
import utils.texttools as texttools

from pipes.views import MacroView, EventView
from .slash_commands_util import autocomplete_scriptoid, choice_to_scriptoid


class PipeSlashCommands(MyCommands):

    # =========================================== General scriptoid Lookup ============================================

    @app_commands.command()
    @app_commands.describe(scriptoid_name='The scriptoid to look up')
    @app_commands.autocomplete(scriptoid_name=autocomplete_scriptoid)
    @app_commands.rename(scriptoid_name="scriptoid")
    async def lookup(self, interaction: Interaction, scriptoid_name: str):
        ''' Look up info on a specific Pipe, Source, Spout, Macro or Event. '''        
        reply = interaction.response.send_message
        try:
            scriptoid, scriptoids = choice_to_scriptoid(scriptoid_name)
        except:
            return await reply(f'Command failed, likely due to nonexistent scriptoid.', ephemeral=True)            

        # Get embed
        embed = scriptoid.embed(interaction)
        view = utils.MISSING

        # Take credit for native scriptoids
        if isinstance(scriptoid, Pipeoid):
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar)
        # Add Views to Macros and Events
        if isinstance(scriptoid, Macro):
            view = MacroView(scriptoid, scriptoids)
        if isinstance(scriptoid, Event):
            view = EventView(scriptoid, scriptoids, interaction.channel)

        await reply(embed=embed, view=view)

        if view:
            view.set_message(await interaction.original_response())


    # ============================================ Native scriptoid Listing ===========================================

    async def _list_scriptoids(self, interaction: Interaction, scriptoids: Pipes|Sources|Spouts, what: str, category_name: str):
        ## List pipes in a specific category
        reply = interaction.response.send_message
        
        if category_name or not scriptoids.categories:
            if category_name:
                category_name = category_name.upper()
                if category_name not in scriptoids.categories:
                    await reply(f'Unknown category "{category_name}".', ephemeral=True)
                    return
                scriptoids_to_display = scriptoids.categories[category_name]
            else:
                scriptoids_to_display = scriptoids.values()

            infos = []
            if category_name:
                infos.append(f'{what.capitalize()}s in category {category_name}:\n')
            else:
                infos.append(f'{what.capitalize()}s:\n')


            col_width = len(max((p.name for p in scriptoids_to_display), key=len)) + 3
            for pipe in scriptoids_to_display:
                info = pipe.name
                if pipe.doc:
                    info = info.ljust(col_width) + pipe.small_doc
                infos.append(info)

            infos.append('')
            infos.append(f'Use /lookup [{what} name] to see detailed info on a specific {what}.')
            if what != 'spout':
                infos.append(f'Use /{what}_macros for a list of user-defined {what}s.\n')
            await reply(texttools.block_format('\n'.join(infos)))

        ## List all categories
        else:
            infos = []
            infos.append(f'{what.capitalize()} categories:\n')
            
            col_width = len(max(scriptoids.categories, key=len)) + 2
            for category_name in scriptoids.categories:
                info = category_name.ljust(col_width)
                category = scriptoids.categories[category_name]
                MAX_PRINT = 8
                if len(category) > MAX_PRINT:
                    info += ', '.join(p.name for p in category[:MAX_PRINT-1]) + '... (%d more)' % (len(category)-MAX_PRINT+1)
                else:
                    info += ', '.join(p.name for p in category)
                infos.append(info)

            infos.append('')
            infos.append(f'Use /lookup [{what} name] to see more info on a specific {what}.')
            if what != 'spout':
                infos.append(f'Use /{what}_macros for a list of user-defined {what}s.\n')
            await reply(texttools.block_format('\n'.join(infos)))

    @app_commands.command()
    @app_commands.describe(category="The specific category of Pipes to list")
    @app_commands.choices(category=[Choice(name=cat, value=cat) for cat in pipes.categories])
    async def pipes(self, interaction: Interaction, category: str=None):
        ''' Display a list of native Pipes, which can be used in scripts. '''
        await self._list_scriptoids(interaction, pipes, 'pipe', category)

    @app_commands.command()
    @app_commands.describe(category="The specific category of Sources to list")
    @app_commands.choices(category=[Choice(name=cat, value=cat) for cat in sources.categories])
    async def sources(self, interaction: Interaction, category: str=None):
        ''' Display a list of native Sources, which can be used in scripts. '''
        await self._list_scriptoids(interaction, sources, 'source', category)

    @app_commands.command()
    async def spouts(self, interaction: Interaction):
        ''' Display a list of native Spouts, which can be used in scripts. '''
        await self._list_scriptoids(interaction, spouts, 'spout', None)


# Load the bot cog
async def setup(bot: commands.Bot):
    await bot.add_cog(PipeSlashCommands(bot))