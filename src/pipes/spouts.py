from datetime import datetime, timezone

import discord
from discord import Embed
from discord.errors import HTTPException
from discord.ext.commands import Bot

from .signature import Par, Signature
from .pipe import Spout, Pipes
from .sources import SourceResources
from .events import events
from resource.upload import uploads
from utils.util import parse_bool


spouts = Pipes()
spouts.command_spouts = []
_CATEGORY = 'NONE'

def make_spout(signature, command=False):
    '''Makes a Spout out of a function.'''
    def _make_spout(func):
        global spouts, _CATEGORY
        spout = Spout(Signature(signature), func, _CATEGORY)
        spouts.add(spout)
        if command:
            spouts.command_spouts.append(spout)
        return func
    return _make_spout

_CATEGORY = 'WIP'

def url(s):
    if len(s)>2 and s[0]=='<' and s[-1]=='>': return s[1:-1]
    return s

def hex(h):
    if h and h[0] == '#': h = h[1:]
    elif h and h[:2] == '0x': h = h[2:]
    return int(h, base=16)

#####################################################
#                  Spouts : EMBEDS                  #
#####################################################

@make_spout({
    'color':       Par(hex, 0x222222, 'The left-side border color as a hexadecimal value.'),
    'title':       Par(str, None, 'The title.', required=False),
    'link':        Par(url, None, 'A link opened by clicking the title.', required=False),
    'author':      Par(str, None, 'A name presented as the author\'s.', required=False),
    'author_icon': Par(url, None, 'Link to the author\'s portrait.', required=False),
    'thumb':       Par(url, None, 'Link to an image shown as a thumbnail.', required=False),
    'image':       Par(url, None, 'Link to an image shown in big.', required=False),
    'footer':      Par(str, '',   'The footer text.'),
    'footer_icon': Par(url, None, 'Link to the footer icon.', required=False),
    'timestamp':   Par(int, None, 'A timestamp representing the date that shows up in the footer.', required=False),
}, command=True)
async def embed_spout(bot, message, values, color, title, author, author_icon, link, thumb, image, footer, footer_icon, timestamp):
    ''' Outputs text as the body of a Discord embed box.'''
    embed = Embed(title=title, description='\n'.join(values), color=color, url=link)

    if timestamp is not None:
        embed.timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if image is not None:
        embed.set_image(url=image)
    if thumb is not None:
        embed.set_thumbnail(url=thumb)
    if author or author_icon:
        # This is not the empty string (↓↓), it's a soft hyphen to force icon to show up even when the name is empty.
        embed.set_author(name=author or '­', icon_url=author_icon)
    if footer or footer_icon:
        # It's a soft hyphen here also
        embed.set_footer(text=footer or '­', icon_url=footer_icon)

    await message.channel.send(embed=embed)


@make_spout({
    'name':     Par(str, 'test_user', 'The account\'s display name.'),
    'handle':   Par(str, 'test_user', 'The account\'s handle, (without the @).'),
    'icon':     Par(url, 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png', 'URL linking to their profile picture.'),
    'retweets': Par(str, '', 'The number of retweets, hidden if empty.'),
    'likes':    Par(str, '', 'The number of likes, hidden if empty.'),
    'timestamp':Par(int, None, 'Time the tweet was sent, "now" if empty.', required=False),
}, command=True)
async def tweet_spout(bot, message, values, name, handle, icon, retweets, likes, timestamp):
    ''' Outputs text as a fake tweet embed. '''
    embed = Embed(description='\n'.join(values), color=0x1da1f2)
    embed.set_author(name='{} (@{})'.format(name, handle), url='https://twitter.com/'+handle, icon_url=icon)
    embed.set_footer(text='Twitter', icon_url='https://abs.twimg.com/icons/apple-touch-icon-192x192.png')
    embed.timestamp = datetime.now(tz=timezone.utc) if timestamp is None else datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if retweets:
        embed.add_field(name='Retweets', value=retweets)
    if likes:
        embed.add_field(name='Likes', value=likes)
    await message.channel.send(embed=embed)


#####################################################
#                 Spouts : MESSAGES                 #
#####################################################

@make_spout({})
async def delete_message_spout(bot, message, values):
    ''' Deletes the message which triggered the script's execution. '''
    await message.delete()


@make_spout({})
async def send_message_spout(bot, message, values):
    '''
    Sends input as a discord message. (WIP until `print` is integrated fully)
    If multiple lines of input are given, they're joined with line breaks.
    '''
    await message.channel.send('\n'.join(values))


@make_spout({
    'id': Par(int, -1, 'The message ID to reply to, -1 for the original message.'),
})
async def reply_spout(bot, message: discord.Message, values, id):
    '''
    Sends input as a discord message replying to another message.
    If multiple lines of input are given, they're joined with line breaks.
    '''
    if id > 0:
        message = await message.channel.fetch_message(id)
    await message.reply('\n'.join(values))


@make_spout({
    'emote': Par(str, None, 'The emote that you\'d like to use to react. (Emoji or custom emote)'),
})
async def react_spout(bot, message, values, emote):
    ''' Reacts to the message using the specified emote. '''
    try:
        await message.add_reaction(emote)
    except HTTPException as e:
        if e.text == 'Unknown Emoji':
            raise ValueError('Unknown Emote: `{}`'.format(emote))
        else:
            raise e


@make_spout({
    'sticker': Par(str, None, 'Name or ID of the sticker.'),
})
async def sticker_spout(bot: Bot, message: discord.Message, values: list[str], sticker: str):
    ''' Sends a message with a sticker attached. '''
    guild_stickers = list(message.guild.stickers)
    name_or_id = sticker
    sticker = None
    try:
        sticker = bot.get_sticker(int(name_or_id))
    except:
        sticker = next((s for s in guild_stickers if s.name == name_or_id), None)
    if sticker is None:
        raise ValueError(f'Unknown sticker "{name_or_id}".')
    await message.channel.send(stickers=[sticker])


#####################################################
#                   Spouts : STATE                  #
#####################################################

@make_spout({
    'name' :   Par(str, None, 'The variable name'),
    'persist': Par(parse_bool, False, 'Whether the variable should persist indefinitely.')
}, command=True)
async def set_spout(bot, message, values, name, persist):
    '''
    Stores the input as a variable with the given name.
    Variables can be retrieved via the `get` Source.
    If `persist`=True, variables will never disappear until manually deleted by the `delete_var` Spout.
    '''
    SourceResources.variables.set(name, values, persistent=persist)


@make_spout({
    'name' :  Par(str, None, 'The variable name'),
    'strict': Par(parse_bool, False, 'Whether an error should be raised if the variable does not exist.')
}, command=True)
async def delete_var_spout(bot, message, values, name, strict):
    ''' Deletes the variable with the given name. '''
    try:
        SourceResources.variables.delete(name)
    except:
        if strict:
            raise KeyError(f'No variable "{name}" found.')


@make_spout({
    'name' : Par(str, None, 'The new file\'s name'),
    'sequential': Par(parse_bool, True, 'Whether the order of entries matters when retrieving them from the file later.'),
    'sentences': Par(parse_bool, False, 'Whether the entries should be split based on sentence recognition instead of a splitter regex.'),
    'editable': Par(parse_bool, False, 'Whether the file should be able to be modified at a later time.'),
    'categories': Par(str, '', 'Comma-separated, case insensitive list of categories the file should be filed under.')
})
async def new_file_spout(bot, message, values, name, sequential, sentences, editable, categories):
    '''Writes the input to a new txt file.'''
    # Files are stored as raw txt's, but we want to make sure our list of strings remain distinguishable.
    # So we join the list of strings by a joiner that we determine for sure is NOT a substring of any of the strings,
    # so that if we split on the joiner later we get the original list of strings.
    if not sentences:
        joiner = '\n'
        while any(joiner in value for value in values):
            joiner += '&'
        if len(joiner) > 1: joiner += '\n'
    else:
        joiner = '\n'

    uploads.add_file(name, joiner.join(values), message.author.display_name, message.author.id,
        editable=editable, splitter=joiner, sequential=sequential, sentences=sentences, categories=categories)


#####################################################
#                  Spouts : SPECIAL                 #
#####################################################

@make_spout({})
async def suppress_print_spout(bot, message, values):
    '''
    (WIP) Prevents the default behaviour of printing output to a Discord message.
    Useful for Event scripts that silently modify variables, or that don't do anything in certain circumstances.
    '''
    # NOP, just having *any* spout is enough to prevent the default "print" behaviour
    pass


@make_spout({})
async def print_spout(bot, message, values):
    ''' Appends the values to the output message. (WIP: /any/ other spout suppresses print output right now!) '''
    # The actual implementation of "print" is hardcoded into the pipeline processor code
    # This definition is just here so it shows up in the list of spouts
    pass


@make_spout({
    'name': Par(str, None, 'The name of the event to be disabled.')
})
async def disable_event_spout(bot, message, values, name):
    ''' Disables the specified event. '''
    if name not in events:
        raise ValueError('Event %s does not exist!' % name)
    event = events[name]
    if message.channel.id in event.channels:
        event.channels.remove(message.channel.id)