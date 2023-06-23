from discord.errors import HTTPException
from discord.ext.commands import Bot

from .spouts import Par, Context, with_signature, spout_from_func, set_category
from pipes.signature import parse_bool 
import utils.rand as rand


#####################################################
#                 Spouts : MESSAGES                 #
#####################################################
set_category('MESSAGE')

@spout_from_func
async def send_message_spout(bot, ctx: Context, values):
    '''
    Sends input as a Discord message.
    If multiple lines of input are given, they're joined with line breaks.
    '''
    await ctx.channel.send('\n'.join(values))


@spout_from_func({
    'id':      Par(int, -1, 'The message ID to reply to, -1 for the script\'s subject message.'),
    'mention': Par(parse_bool, False, 'Whether the reply should mention the person being replied to.'),
})
async def reply_spout(bot, ctx: Context, values, *, id, mention):
    '''
    Sends input as a Discord message replying to another message.
    If multiple lines of input are given, they're joined with line breaks.
    '''
    if id > 0:
        message = await ctx.channel.fetch_message(id)
    else:
        message = ctx.message
    await message.reply('\n'.join(values), mention_author=mention)


@spout_from_func({
    'emote': Par(str, None, 'The emote that you\'d like to use to react. (Emoji or custom emote)'),
})
async def react_spout(bot, ctx: Context, values, emote):
    ''' Reacts to the message using the specified emote. '''
    try:
        await ctx.message.add_reaction(emote)
    except HTTPException as e:
        if e.text == 'Unknown Emoji':
            raise ValueError('Unknown Emote: `{}`'.format(emote))
        else:
            raise e


@spout_from_func
@with_signature(
    sticker = Par(str, None, 'Name or ID of the sticker.'),
    here    = Par(parse_bool, True, 'Whether to restrict to this server\'s stickers.'),
)
async def sticker_spout(bot: Bot, ctx: Context, values: list[str], *, sticker: str, here :bool):
    ''' Sends a message with a sticker attached. '''    
    if here:
        stickers = list(ctx.message.guild.stickers)
    else:
        stickers = [s for guild in ctx.bot.guilds for s in guild.stickers]

    name_or_id = sticker
    sticker = None

    # Try ID match
    try: sticker = bot.get_sticker(int(name_or_id))
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
async def delete_message_spout(bot, ctx: Context, values):
    ''' Deletes the message which is the subject of the script's execution. '''
    await ctx.message.delete()
