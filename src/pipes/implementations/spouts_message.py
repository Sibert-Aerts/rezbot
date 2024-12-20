from discord.errors import HTTPException

from .spouts import Par, Context, with_signature, spout_from_func, set_category

from pipes.core.state import BOT_STATE
from pipes.core.signature import parse_bool

import utils.rand as rand
import utils.texttools as texttools


#####################################################
#                 Spouts : MESSAGES                 #
#####################################################
set_category('MESSAGE')

@spout_from_func
@with_signature(
    earmark = Par(str, None, 'Earmark to uniquely identify this message in other scripting contexts.', required=False),
)
async def send_message_spout(ctx: Context, values, earmark):
    '''
    Sends input as a Discord message.
    If multiple lines of input are given, they're joined with line breaks.
    '''
    message = await ctx.channel.send('\n'.join(values))
    if earmark:
        BOT_STATE.earmarked_messages[earmark] = [message]


@spout_from_func
@with_signature(
    id =      Par(str, 'this', 'The message to reply to: this/that or a message ID.'),
    mention = Par(parse_bool, False, 'Whether the reply should ping the person being replied to.'),
    earmark = Par(str, None, 'Earmark to uniquely identify this message in other scripting contexts.', required=False),
)
async def reply_spout(ctx: Context, values, *, id, mention, earmark):
    '''
    Sends input as a Discord message replying to another message.
    If multiple lines of input are given, they're joined with line breaks.
    '''
    message = await ctx.get_message(id)
    reply = await message.reply('\n'.join(values), mention_author=mention)
    if earmark:
        BOT_STATE.earmarked_messages[earmark] = [reply]


@spout_from_func
@with_signature(
    member = Par(str, None, 'The member to send the message to. "me/them" or the member\'s handle or ID.'),
    earmark = Par(str, None, 'Earmark to uniquely identify this message in other scripting contexts.', required=False),
)
async def direct_message_spout(ctx: Context, values, *, member, earmark):
    '''
    Sends input as a direct Discord message to someone.
    If multiple lines of input are given, they're joined with line breaks.
    '''
    member = await ctx.get_member(member)
    activator = ctx.origin.activator

    # To prevent abuse (?), log every DM
    print(f'Executing direct_message spout: Sending DM to {member.name}, invoked by {activator.name}')
    print('\tMessage content:', values)

    msg = f'You\'ve received a direct message, invoked by {activator.name}'
    if ctx.origin.event and (author_id := ctx.origin.event.author_id) != activator.id:
        try:
            author = await ctx.get_member(str(author_id))
            msg += f' via an Event authored by {author.name}'
        except:
            msg += f' via an Event authored by {author_id}'

    msg += texttools.block_format('\n'.join(values))
    message = await member.send(msg)
    if earmark:
        BOT_STATE.earmarked_messages[earmark] = [message]


@spout_from_func
@with_signature(
    emote = Par(str, None, 'The emote that you\'d like to use to react. (Emoji or custom emote)'),
    id = Par(str, 'this', 'The message to react to: this/that or a message ID.'),
)
async def react_spout(ctx: Context, values, *, emote, id):
    ''' Reacts to the message using the specified emote. '''
    message = await ctx.get_message(id)
    try:
        await message.add_reaction(emote)
    except HTTPException as e:
        if e.text == 'Unknown Emoji':
            raise ValueError('Unknown Emote: `{}`'.format(emote))
        else:
            raise e


@spout_from_func
@with_signature(
    sticker = Par(str, None, 'Name or ID of the sticker.'),
    here    = Par(parse_bool, True, 'Whether to restrict to this server\'s stickers. Does not work currently.'),
)
async def sticker_spout(ctx: Context, values, *, sticker: str, here :bool):
    ''' Sends a message with a sticker attached. '''
    if here:
        stickers = list(ctx.message.guild.stickers)
    else:
        stickers = [s for guild in ctx.bot.guilds for s in guild.stickers]

    name_or_id = sticker
    sticker = None

    # Try ID match
    try: sticker = ctx.bot.get_sticker(int(name_or_id))
    except: pass
    # Try exact name match
    if sticker is None:
        sticker = next((s for s in stickers if s.name == name_or_id), None)
    # Try name search match
    if sticker is None:
        search = name_or_id.lower()
        stickers = [s for s in stickers if search in s.name.lower()]
        if stickers: sticker = rand.choose(stickers)

    if sticker is None:
        raise ValueError(f'Unknown sticker "{name_or_id}".')
    await ctx.channel.send(stickers=[sticker])


@spout_from_func
async def delete_message_spout(ctx: Context, values):
    ''' Deletes the message which is the subject of the script's execution. '''
    await ctx.message.delete()
