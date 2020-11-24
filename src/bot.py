
from datetime import datetime
import sys
import asyncio
from configparser import ConfigParser

import discord
from discord.ext import commands

import permissions
import patterns
from pipes.processor import PipelineProcessor
import utils.util as util

# Open the config so we can read the bot token from it, later
config = ConfigParser()
config.read('config.ini')

command_prefix = config['BOT']['prefix']
pipe_prefix = config['BOT']['pipe_prefix']

# bot happens here
bot = commands.Bot(command_prefix=command_prefix)

# initialise some of my own stuffs
patterns = patterns.Patterns(bot)
scriptProcessor = PipelineProcessor(bot, pipe_prefix)


@bot.event
async def on_ready():
    print()
    print('---------------- BOT READY ----------------')
    print(' Username:', bot.user.name)
    print(' ID:', bot.user.id)
    print(' Servers:', ', '.join(g.name for g in bot.guilds) )
    print(' Running discord.py %s' % discord.__version__)
    print(' Time: ' + datetime.now().strftime('%c') )
    print('-------------------------------------------')
    print()


@bot.event
async def on_message(message):
    # Do not listen to self.
    if message.author.id == bot.user.id:
        return

    # Do not listen to muted users
    if permissions.is_muted(message.author.id):
        return

    # Do not listen to bots
    if message.author.bot:
        return

    # See if it looks like a script, if it does: run the script and don't do anything else
    if await scriptProcessor.process_script(message):
        return

    # Try for patterns and custom Events if it doesn't look like a command
    if message.content[:len(command_prefix)] != command_prefix:
        await scriptProcessor.on_message(message)
        await patterns.process_patterns(message)

    # Try for commands
    await bot.process_commands(message)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    guild = bot.get_guild(payload.guild_id)
    if not guild: return
    channel = guild.get_channel(payload.channel_id)
    await scriptProcessor.on_reaction(channel, str(payload.emoji), payload.user_id, payload.message_id)


@bot.event
async def on_command_error(ctx, error):
    print('')
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.author.send('This command cannot be used in private messages.')
    elif isinstance(error, commands.DisabledCommand):
        await ctx.author.send('Sorry. This command is disabled and cannot be used.')
    elif isinstance(error, commands.CommandInvokeError):
        print('In {0.command.qualified_name}:'.format(ctx), file=sys.stderr)
        # traceback.print_tb(error.original.__traceback__)
        print('{0.__class__.__name__}: {0}'.format(error.original), file=sys.stderr)
    else:
        print('Command Error:', error)


if __name__ == '__main__':
    token = config['BOT']['token']
    bot.load_extension('botcommands')
    bot.load_extension('pipes.pipecommands')
    bot.load_extension('pipes.macrocommands')
    bot.load_extension('resource.youtubecaps.commands')
    bot.load_extension('resource.upload.commands')
    bot.run(token)
