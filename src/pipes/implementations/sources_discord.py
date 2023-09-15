from datetime import timezone
import discord

from .sources import source_from_func, get_which, set_category, Context
from pipes.core.signature import Par, Option, Multi, regex, parse_bool, with_signature
from pipes.core.context import ContextError
from pipes.core.events import OnReaction

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
}, plural='those')
async def that_source(ctx: Context, what):
    '''The previous message in the channel, or the message being replied to.'''
    message = ctx.message
    if message.reference and message.reference.message_id:
        msg_id = message.reference.message_id
        msg = await ctx.channel.fetch_message(msg_id)
    else:
        msg = [ msg async for msg in message.channel.history(limit=2) ][1]
    return messages_get_what([msg], what)


@source_from_func({
    'n': Par(int, 1, 'The number of next messages to wait for.', lambda n: n < 1000),
    'what': Par(Multi(MESSAGE_WHAT), 'content', '/'.join(MESSAGE_WHAT))
})
async def next_message_source(ctx: Context, n, what):
    '''The next message to be sent in the channel.'''
    messages = []

    def check(msg):
        # ignore (most) messages that the bot normally ignores
        return msg.channel == ctx.channel \
            and not msg.author.bot \
            and msg.content[:len(ctx.bot.command_prefix)] != ctx.bot.command_prefix

    while len(messages) < n:
        messages.append( await ctx.bot.wait_for('message', check=check) )
    return messages_get_what(messages, what)


@source_from_func({
    'what': Par(Multi(MESSAGE_WHAT), 'content', '/'.join(MESSAGE_WHAT))
})
async def message_source(ctx: Context, what):
    '''The message which triggered script execution. Useful in Event scripts.'''
    return messages_get_what([ctx.message], what)


@source_from_func({
    'n': Par(int, 1, 'The number of messages'),
    'i': Par(int, 1, 'From which previous message to start counting. (0 for the message that triggers the script itself)', lambda i: i <= 10000),
    'what': Par(Multi(MESSAGE_WHAT), 'content', '/'.join(MESSAGE_WHAT)),
    'by': Par(int, 0, 'A user id, if given will filter the results down to only that users\' messages within the range of messages (if any).'),
})
async def previous_message_source(ctx: Context, n, i, what, by):
    '''
    A generalization of {that} and {message} that allows more messages and going further back.
    
    The N messages in this channel, counting backwards from the Ith previous message.
    i.e. N messages, ordered newest to oldest, with the newest being the Ith previous message.
    '''
    messages = [ msg async for msg in ctx.channel.history(limit=n+i) ][i:i+n]
    if by: messages = [m for m in messages if m.author.id == by]

    return messages_get_what(messages, what)


#### MEMBERS ########################################

MEMBER_WHAT = Option('name', 'global_name', 'username', 'mention', 'id', 'avatar', 'activity', 'color', 'is_bot',
    aliases={'name': ['display_name', 'nickname'], 'username': ['handle']})
@get_which
def members_get_what(members: list[discord.Member], what):
    if what == MEMBER_WHAT.display_name:
        return (member.display_name for member in members)
    elif what == MEMBER_WHAT.global_name:
        return (member.global_name or '' for member in members)
    elif what == MEMBER_WHAT.username:
        return (member.name for member in members)
    elif what == MEMBER_WHAT.mention:
        return (member.mention for member in members)
    elif what == MEMBER_WHAT.id:
        return (str(member.id) for member in members)
    elif what == MEMBER_WHAT.avatar:
        return (str(member.display_avatar) for member in members)
    elif what == MEMBER_WHAT.activity:
        return (str(member.activities[0]) if member.activities else '' for member in members)
    elif what == MEMBER_WHAT.color:
        return (str(member.color) for member in members)
    elif what == MEMBER_WHAT.is_bot:
        return (str(member.bot) for member in members)
    raise ValueError()

@source_from_func(aliases=['my'])
@with_signature(
    what = Par(Multi(MEMBER_WHAT), 'name', '/'.join(MEMBER_WHAT)),
)
async def me_source(ctx: Context, what):
    '''The name (or other attribute) of the member invoking the script or event.'''
    return members_get_what([ctx.origin.activator], what)


@source_from_func(aliases=['them', 'their'])
@with_signature(
    what = Par(Multi(MEMBER_WHAT), 'name', '/'.join(MEMBER_WHAT)),
)
async def they_source(ctx: Context, what):
    '''
    The name (or other attribute) of the member who is the 'subject' in the current context.

    In context of an OnReact Event, represents the author of the reacted-to message.
    Otherwise, in a context where the triggering message is replying to another message, represents the replied message's author.
    '''
    them = None
    if ctx.origin.event and isinstance(ctx.origin.event, OnReaction):
        # Case 1: OnReact Event: Message author.
        #   i.e. {them} is the same as {member id={message author_id}}
        them = ctx.message.author
    elif ctx.message.reference and ctx.message.reference.message_id:
        # Case 2: Context message is replying to another message
        #   i.e. {them} is the same as {member id={that author_id}}
        msg_id = ctx.message.reference.message_id
        msg = await ctx.channel.fetch_message(msg_id)
        them = msg.author
    else:
        raise ContextError('No known "them" in the current context.')
    return members_get_what([them], what)


@source_from_func
@with_signature(
    what = Par(Multi(MEMBER_WHAT), 'name', '/'.join(MEMBER_WHAT)),
)
async def bot_source(ctx: Context, what):
    '''The name (or other attribute) of the bot's own Discord member.'''
    bot = ctx.bot.user
    if ctx.channel.guild:
        # Member has more contextual info than just User
        bot = ctx.channel.guild.get_member(bot.id)
    return members_get_what([bot], what)


@source_from_func(depletable=True)
@with_signature(
    n    = Par(int, 1, 'The maximum number of members to return.'),
    what = Par(Multi(MEMBER_WHAT), 'name', '/'.join(MEMBER_WHAT)),
    id   = Par(int, 0, 'The id to match the member by. If given the number of members return will be at most 1.'),
    name = Par(regex, None, 'A pattern that should match their one of their names.', required=False),
    # rank = Par(...)?
)
async def member_source(ctx: Context, n, what, id, name):
    '''The name (or other attribute) of a server member.'''
    members = ctx.message.guild.members

    # Filter if necessary
    if id:
        members = [m for m in members if m.id == id]
    if name:
        members = [
            m for m in members if
            m.nick and name.search(m.nick) or m.global_name and name.search(m.global_name) or name.search(m.name)
        ]

    # Take a random sample
    members = sample(members, n)
    return members_get_what(members, what)


#### CHANNEL ########################################

CHANNEL_WHAT = Option('name', 'id', 'topic', 'category', 'mention', 'is_nsfw')

@source_from_func({
    'what': Par(CHANNEL_WHAT, 'name', '/'.join(CHANNEL_WHAT)),
})
async def channel_source(ctx: Context, what):
    '''The name (or other attribute) of the current channel.'''
    channel = ctx.channel
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
})
async def server_source(ctx: Context, what):
    '''The name (or other attribute) of the current server.'''
    server = ctx.message.guild
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


@source_from_func(depletable=True, aliases=['emote', 'emotes'])
@with_signature(
    n =      Par(int, 1, 'The number of emojis'),
    name =   Par(str, None, 'An exact name to match.', required=False),
    search = Par(str, None, 'A string to search for in the name.', required=False),
    id =     Par(int, None, 'An exact emoji ID to match.', required=False),
    here =   Par(parse_bool, True, 'Whether to restrict to this server\'s emoji.'),
)
async def custom_emoji_source(ctx: Context, n, name, search, id, here):
    '''Discord custom emoji.'''
    if here:
        emojis = ctx.message.guild.emojis
    else:
        emojis = [e for guild in ctx.bot.guilds for e in guild.emojis]

    if name is not None:
        emojis = [e for e in emojis if e.name == name]
    elif id is not None:
        emojis = [e for e in emojis if e.id == id]
    elif search is not None:
        search = search.lower()
        emojis = [e for e in emojis if search in e.name.lower()]

    return [str(emoji) for emoji in sample(emojis, n)]
