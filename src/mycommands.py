import sys
import utils.texttools as texttools

class MyCommands:
    '''Class holding useful methods for bot commands.'''
    def __init__(self, bot):
        self.bot = bot

    async def say_bot(self, str):
        str = texttools.bot_format(str)
        await self.say(str)

    async def say_block(self, str):
        str = texttools.block_format(str)
        await self.say(str)

    async def say(self, str):
        msg = await self.bot.say(str)

    async def send_message(self, channel, str):
        str = texttools.bot_format(str)
        msg = await self.bot.send_message(channel, str)

    async def _die(self):
        '''Kill the bot.'''
        await self.bot.logout()
        await self.bot.close()
        print('Bot killed.')
        sys.exit()