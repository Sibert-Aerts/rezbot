import sys
from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    import bot as rezbot


class MyCommands(commands.Cog):
    '''Class holding useful methods for bot commands.'''
    bot: 'rezbot.Rezbot'

    def __init__(self, bot):
        self.bot = bot

    async def _die(self):
        '''Kill the bot.'''
        await self.bot.close()
        print('Bot killed.')
        sys.exit()