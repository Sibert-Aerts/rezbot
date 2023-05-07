from datetime import timezone
import discord

from .sources import source_from_func, get_which, set_category, SourceResources
from ..signature import Par, Option, Multi, regex, parse_bool

from utils.texttools import *

#####################################################
#                 Sources : DISCORD                 #
#####################################################
set_category('DISCORD')

#### MESSAGES #######################################

MESSAGE_WHAT = Option('content', 'id', 'timestamp', 'author_id')
@get_which
def messages_get_what(messages, what):
    if what == MESSAGE_WHAT.content:
        return (msg.content for msg in messages)
    if what == MESSAGE_WHAT.id:
        return (str(msg.id) for msg in messages)
    if what == MESSAGE_WHAT.timestamp:
        return (str(int((msg.created_at.replace(tzinfo=timezone.utc)).timestamp())) for msg in messages)
    if what == MESSAGE_WHAT.author_id:
        return (str(msg.author.id) for msg in messages)


@source_from_func({
    'what': Par(Multi(MESSAGE_WHAT), 'content', '/'.join(MESSAGE_WHAT))
}, pass_message=True, plural='those')
async def that_source(message: discord.Message, what):
    '''The previous message in the channel, or the message being replied to.'''
    if message.reference and message.reference.message_id:
        msg_id = message.reference.message_id
        msg = await message.channel.fetch_message(msg_id)        
    else:
        msg = [ msg async for msg in message.channel.history(limit=2) ][1]
    return messages_get_what([msg], what)


@source_from_func({
    'n': Par(int, 1, 'The number of next messages to wait for.', lambda n: n < 1000),
    'what': Par(Multi(MESSAGE_WHAT), 'content', '/'.join(MESSAGE_WHAT))
}, pass_message=True)
async def next_message_source(message, n, what):
    '''The next message to be sent in the channel.'''
    messages = []

    def check(msg):
        # ignore (most) messages that the bot normally ignores
        return msg.channel == message.channel \
            and not msg.author.bot \
            and msg.content[:len(SourceResources.bot.command_prefix)] != SourceResources.bot.command_prefix

    while len(messages) < n:
        messages.append( await SourceResources.bot.wait_for('message', check=check) )
    return messages_get_what(messages, what)


@source_from_func({
    'what': Par(Multi(MESSAGE_WHAT), 'content', '/'.join(MESSAGE_WHAT))
}, pass_message=True)
async def message_source(message, what):
    '''The message which triggered script execution. Useful in Event scripts.'''
    return messages_get_what([message], what)


@source_from_func({
    'n': Par(int, 1, 'The number of messages'),
    'i': Par(int, 1, 'From which previous message to start counting. (0 for the message that triggers the script itself)', lambda i: i <= 10000),
    'what': Par(Multi(MESSAGE_WHAT), 'content', '/'.join(MESSAGE_WHAT)),
    'by': Par(int, 0, 'A user id, if given will filter the results down to only that users\' messages within the range of messages (if any).'),
}, pass_message=True)
async def previous_message_source(message, n, i, what, by):
    '''
    A generalization of {that} and {message} that allows more messages and going further back.
    
    The N messages in this channel, counting backwards from the Ith previous message.
    i.e. N messages, ordered newest to oldest, with the newest being the Ith previous message.
    '''
    messages = [ msg async for msg in message.channel.history(limit=n+i) ][i:i+n]
    if by: messages = [m for m in messages if m.author.id == by]

    return messages_get_what(messages, what)


#### MEMBERS ########################################

MEMBER_WHAT = Option('nickname', 'username', 'id', 'avatar', 'activity', 'color')
@get_which
def members_get_what(members: list[discord.Member], what):
    if what == MEMBER_WHAT.nickname:
        return (member.display_name for member in members)
    elif what == MEMBER_WHAT.username:
        return (member.name for member in members)
    elif what == MEMBER_WHAT.id:
        return (str(member.id) for member in members)
    elif what == MEMBER_WHAT.avatar:
        return (str(member.avatar) for member in members)
    elif what == MEMBER_WHAT.activity:
        return (str(member.activities[0]) if member.activities else '' for member in members)
    elif what == MEMBER_WHAT.color:
        return (str(member.color) for member in members)

@source_from_func({
    'what': Par(Multi(MEMBER_WHAT), 'nickname', '/'.join(MEMBER_WHAT))
}, pass_message=True)
async def me_source(message, what):
    '''The name (or other attribute) of the user invoking the script or event.'''
    return members_get_what([message.author], what)


@source_from_func({
    'n'   : Par(int, 1, 'The maximum number of members to return.'),
    'what': Par(Multi(MEMBER_WHAT), 'nickname', '/'.join(MEMBER_WHAT)),
    'id'  : Par(int, 0, 'The id to match the member by. If given the number of members return will be at most 1.'),
    'name': Par(regex, None, 'A pattern that should match their nickname or username.', required=False),
    # 'rank': ...?
}, pass_message=True, depletable=True)
async def member_source(message: discord.Message, n, what, id, name):
    '''The name (or other attribute) of a random Server member meeting the filters.'''
    members = message.guild.members

    # Filter if necessary
    if id:
        members = [m for m in members if m.id == id]
    if name:
        members = [m for m in members if name.search(m.display_name) or name.search(m.name)]

    # Take a random sample
    members = sample(members, n)

    return members_get_what(members, what)

#### CHANNEL ########################################

CHANNEL_WHAT = Option('name', 'id', 'topic', 'category', 'mention', 'is_nsfw')

@source_from_func({
    'what': Par(CHANNEL_WHAT, 'name', '/'.join(CHANNEL_WHAT)),
}, pass_message=True)
async def channel_source(message: discord.Message, what):
    '''The name (or other attribute) of the current channel.'''
    channel = message.channel
    if what == CHANNEL_WHAT.name:
        return [channel.name or '']
    if what == CHANNEL_WHAT.id:
        return [str(channel.id)]
    if what == CHANNEL_WHAT.topic:
        return [channel.topic or '']
    if what == CHANNEL_WHAT.category:
        return [channel.category and channel.category.name or '']
    if what == CHANNEL_WHAT.mention:
        return [channel.mention]
    if what == CHANNEL_WHAT.is_nsfw:
        return [str(channel.nsfw)]

#### SERVER ########################################

SERVER_WHAT = Option('name', 'description', 'icon', 'member_count', 'id')

@source_from_func({
    'what': Par(SERVER_WHAT, SERVER_WHAT.name, '/'.join(SERVER_WHAT)),
}, pass_message=True)
async def server_source(message, what):
    '''The name (or other attribute) of the current server.'''
    server = message.guild
    if what == SERVER_WHAT.name:
        return [server.name]
    if what == SERVER_WHAT.description:
        return [server.description or '']
    if what == SERVER_WHAT.icon:
        return [str(server.icon or '')]
    if what == SERVER_WHAT.member_count:
        return [str(server.member_count)]
    if what == SERVER_WHAT.id:
        return [str(server.id)]


@source_from_func({
    'n':      Par(int, 1, 'The number of emojis'),
    'id':     Par(int, None, 'An exact emoji ID to match.', required=False),
    'name':   Par(str, None, 'An exact name to match.', required=False),
    'search': Par(str, None, 'A string to search for in the name.', required=False),
    'here':   Par(parse_bool, True, 'Whether to restrict to this server\'s emoji.'),
}, pass_message=True, depletable=True)
async def custom_emoji_source(message, n, name, search, id, here):
    '''The server's custom emojis.'''
    if here:
        emojis = message.guild.emojis
    else:
        emojis = [e for guild in SourceResources.bot.guilds for e in guild.emojis]

    if name is not None:
        emojis = [e for e in emojis if e.name == name]
    elif id is not None:
        emojis = [e for e in emojis if e.id == id]
    elif search is not None:
        search = search.lower()
        emojis = [e for e in emojis if search in e.name.lower()]

    return [ str(emoji) for emoji in sample(emojis, n) ]
