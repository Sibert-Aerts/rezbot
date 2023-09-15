
import sys
import asyncio
from datetime import datetime
from configparser import ConfigParser

import discord
from discord.ext import commands

import permissions
import patterns
from pipes import PipelineProcessor


# Open the config so we can read info from it
config = ConfigParser()
config.read('config.ini')

bot_token = config['BOT']['token']
command_prefix = config['BOT']['prefix']
pipe_prefix = config['BOT']['pipe_prefix']

patterns_blacklist = []
if 'PATTERNS.PY BLACKLIST' in config:
    for key in config['PATTERNS.PY BLACKLIST']:
        patterns_blacklist.append(int(config['PATTERNS.PY BLACKLIST'][key]))


# Configure our intents
intents = discord.Intents.all()

# Block out all the stuff we don't care about
intents.dm_typing = False
intents.guild_typing = False
intents.integrations = False
intents.webhooks = False
intents.invites = False
intents.voice_states = False
intents.bans = False

# Configure logging
discord.utils.setup_logging()


class Rezbot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=command_prefix, case_insensitive=True, intents=intents)
        self.pattern_processor = patterns.Patterns(self)
        self.pipeline_processor = PipelineProcessor(self, pipe_prefix)

    async def on_ready(self):
        print()
        print('====================================== BOT READY =====================================')
        print(' Username:', self.user.name)
        print(' ID:', self.user.id)
        print(' Servers:', ', '.join(guild.name for guild in self.guilds) )
        print(' Running discord.py %s' % discord.__version__)
        print(' Time: ' + datetime.now().strftime('%c') )
        print('======================================================================================')
        print()

    def should_listen_to_user(self, user):
        # Do not listen to self.
        if user.id == self.user.id:
            return False
        # Do not listen to bots.
        if user.bot:
            return False
        # Do not listen to muted users.
        if permissions.is_muted(user.id):
            return False
        return True

    async def on_message(self, message: discord.Message):
        if not self.should_listen_to_user(message.author):
            return

        # See if it looks like a script, if it does: run the script and don't do anything else
        if await self.pipeline_processor.interpret_incoming_message(message):
            return

        # Try for patterns and custom Events if it doesn't look like a command
        if message.content[:len(command_prefix)] != command_prefix:
            await self.pipeline_processor.on_message(message)
            if (not message.guild or message.guild.id not in patterns_blacklist) and message.channel.id not in patterns_blacklist:
                await self.pattern_processor.process_patterns(message)

        # Try for commands
        await self.process_commands(message)

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        guild = self.get_guild(payload.guild_id)
        if not guild:
            return
        channel = guild.get_channel_or_thread(payload.channel_id)
        await self.pipeline_processor.on_reaction(channel, str(payload.emoji), payload.user_id, payload.message_id)

    async def on_command_error(self, ctx, error):
        print()
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.author.send('This command cannot be used in private messages.')
        elif isinstance(error, commands.DisabledCommand):
            await ctx.author.send('Sorry. This command is disabled and cannot be used.')
        elif isinstance(error, commands.CommandInvokeError):
            print(f'In {ctx.command.qualified_name}:', file=sys.stderr)
            # traceback.print_tb(error.original.__traceback__)
            print(f'{type(error.original).__name__}: {error.original}', file=sys.stderr)
        else:
            print('Command Error:', error)


async def main():
    # Create the bot
    bot = Rezbot()

    async with bot:
        await bot.load_extension('botcommands')
        # Old text-based commants
        await bot.load_extension('pipes.commands.pipe_commands')
        await bot.load_extension('pipes.commands.macro_commands')
        await bot.load_extension('pipes.commands.event_commands')
        # New slash commands
        await bot.load_extension('pipes.commands.pipe_slash_commands')
        await bot.load_extension('pipes.commands.macro_slash_commands')
        await bot.load_extension('pipes.commands.event_slash_commands')
        
        await bot.load_extension('resource.youtubecaps.commands')
        await bot.load_extension('resource.upload.commands')
        await bot.start(bot_token)


if __name__ == '__main__':
    asyncio.run(main())