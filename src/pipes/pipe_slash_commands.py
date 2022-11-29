import itertools

import discord
from discord.ext import commands
from discord import app_commands, Interaction
from discord.app_commands import Choice

from .pipe import Pipe, Source, Spout, Pipes
from .pipes import pipes
from .sources import sources, SourceResources
from .spouts import spouts
from .macros import Macros, pipe_macros, source_macros
from .events import Event, Events, events
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


class PipeSlashCommands(MyCommands):

    # ========================== Pipeoid lookup ==========================

    @app_commands.command(name='lookup')
    @app_commands.describe(pipeoid='The pipe to look up')
    @app_commands.autocomplete(pipeoid=autocomplete_pipeoid)
    async def pipe_info(self, interaction: Interaction, pipeoid: str):
        '''Look up info on a specific pipe, source, spout, macro or event.'''
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


# Load the bot cog
async def setup(bot: commands.Bot):
    await bot.add_cog(PipeSlashCommands(bot))