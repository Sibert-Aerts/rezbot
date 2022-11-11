import sys
import utils.texttools as texttools
from discord.ext import commands

class MyCommands(commands.Cog):
    '''Class holding useful methods for bot commands.'''
    bot: commands.Bot

    def __init__(self, bot):
        self.bot = bot

    async def say_block(self, s, **kwargs):
        await self.say(texttools.block_format(s), **kwargs)

    async def say(self, *args, **kwargs):
        await self.bot.say(*args, **kwargs)

    async def _die(self):
        '''Kill the bot.'''
        await self.bot.close()
        print('Bot killed.')
        sys.exit()