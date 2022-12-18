
import sys
import asyncio
from datetime import datetime
from configparser import ConfigParser

import discord
from discord.ext import commands

import permissions
import patterns
from pipes.processor import PipelineProcessor

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

# Create the bot
bot = commands.Bot(command_prefix=command_prefix, case_insensitive=True, intents=intents)

# Initialise own managers
patternProcessor = patterns.Patterns(bot)
scriptProcessor = PipelineProcessor(bot, pipe_prefix)

@bot.event
async def on_ready():
    print()
    print('====================================== BOT READY =====================================')
    print(' Username:', bot.user.name)
    print(' ID:', bot.user.id)
    print(' Servers:', ', '.join(guild.name for guild in bot.guilds) )
    print(' Running discord.py %s' % discord.__version__)
    print(' Time: ' + datetime.now().strftime('%c') )
    print('======================================================================================')
    print()


@bot.event
async def on_message(message: discord.Message):
    # Do not listen to self.
    if message.author.id == bot.user.id:
        return
    # Do not listen to bots.
    if message.author.bot:
        return
    # Do not listen to muted users.
    if permissions.is_muted(message.author.id):
        return

    # See if it looks like a script, if it does: run the script and don't do anything else
    if await scriptProcessor.process_script(message):
        return

    # Try for patterns and custom Events if it doesn't look like a command
    if message.content[:len(command_prefix)] != command_prefix:
        await scriptProcessor.on_message(message)
        if (not message.guild or message.guild.id not in patterns_blacklist) and message.channel.id not in patterns_blacklist:
            await patternProcessor.process_patterns(message)

    # Try for commands
    await bot.process_commands(message)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    guild = bot.get_guild(payload.guild_id)
    if not guild: return
    channel = guild.get_channel_or_thread(payload.channel_id)
    await scriptProcessor.on_reaction(channel, str(payload.emoji), payload.user_id, payload.message_id)


@bot.event
async def on_command_error(ctx, error):
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
    async with bot:
        await bot.load_extension('botcommands')
        await bot.load_extension('pipes.pipecommands')
        await bot.load_extension('pipes.pipe_slash_commands')
        await bot.load_extension('pipes.macrocommands')
        await bot.load_extension('resource.youtubecaps.commands')
        await bot.load_extension('resource.upload.commands')
        await bot.start(bot_token)

if __name__ == '__main__':
    asyncio.run(main())