import random

from discord import Embed
from discord.errors import HTTPException

from .signature import Sig
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
        spout = Spout(signature, func, _CATEGORY)
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
    return int(h, base=16)


@make_spout({
    'title':    Sig(str, None, 'The title.'),
    'color':    Sig(hex, 0x222222, 'The highlight color as a hexadecimal value.'),
    'footer':   Sig(str, '', 'The footer text.'),
    'link':     Sig(url, None, 'A link opened by clicking the title.', required=False),
    'image':    Sig(url, None, 'Link to an embedded image.', required=False)
})
async def embed_spout(bot, message, values, title, color, footer, link, image):
    '''Outputs text as a simple discord embed.'''
    embed = Embed(title=title, description='\n'.join(values), color=color, url=link)
    if footer:
        embed.set_footer(text=footer)
    if image:
        embed.set_image(url=image)
    await message.channel.send(embed=embed)


@make_spout({
    'name':     Sig(str, 'test_user', 'The account\'s display name.'),
    'handle':   Sig(str, 'test_user', 'The account\'s handle, (without the @).'),
    'icon':     Sig(url, 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png', 'URL linking to their profile picture.'),
    'retweets': Sig(str, '', 'The number of retweets, hidden if empty.'),
    'likes':    Sig(str, '', 'The number of likes, hidden if empty.'),
})
async def tweet_spout(bot, message, values, name, handle, icon, retweets, likes):
    '''Outputs text as a fake embedded tweet.'''
    e = Embed(description='\n'.join(values), color=0x1da1f2)
    e.set_author(name='{} (@{})'.format(name, handle), url='https://twitter.com/'+handle, icon_url=icon)
    e.set_footer(text='Twitter', icon_url='https://abs.twimg.com/icons/apple-touch-icon-192x192.png')
    if retweets: e.add_field(name='Retweets', value=retweets)
    if likes: e.add_field(name='Likes', value=likes)
    await message.channel.send(embed=e)


@make_spout({})
async def delete_message_spout(bot, message, values):
    '''Deletes the message that triggered the script's execution.'''
    await message.delete()


@make_spout({})
async def send_message_spout(bot, message, values):
    '''Sends input as a discord message. (WIP until `print` is integrated fully)
    If multiple lines of input are given, they're joined with newlines'''
    await message.channel.send('\n'.join(values))


@make_spout({'emote': Sig(str, None, 'The emote that you\'d like to use to react. (Emoji or custom emote)'),})
async def react_spout(bot, message, values, emote):
    '''Reacts to the message using the specified emote.'''
    try:
        await message.add_reaction(emote)
    except HTTPException as e:
        if e.text == 'Unknown Emoji':
            raise ValueError('Unknown Emote: `{}`'.format(emote))
        else:
            raise e


@make_spout({})
async def suppress_print_spout(bot, message, values):
    '''(WIP) Prevents the default behaviour of printing output to a Discord message.
    Useful for Event scripts that silently modify variables, or that don't do anything in certain circumstances.'''
    # NOP, just having *any* spout is enough to prevent the default "print" behaviour
    pass


@make_spout({'name' : Sig(str, None, 'The variable name')}, command=True)
async def set_spout(bot, message, values, name):
    '''Stores the input as a variable with the given name, which can be retreived with {get (name)}.'''
    SourceResources.var_dict[name] = values


@make_spout({
    'name' : Sig(str, None, 'The new file\'s name'),
    'sequential': Sig(parse_bool, True, 'Whether the order of entries matters when retrieving them from the file later.'),
    'sentences': Sig(parse_bool, False, 'Whether the entries should be split based on sentence recognition instead of a splitter regex.')
}, command=True)
async def new_file_spout(bot, message, values, name, sequential, sentences):
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

    uploads.add_file(name, joiner.join(values), message.author.display_name, message.author.id, splitter=joiner, sequential=sequential, sentences=sentences)


@make_spout({})
async def print_spout(bot, message, values):
    '''Appends the values to the output message. (WIP: /any/ other spout suppresses print output right now!)'''
    # The actual implementation of "print" is hardcoded into the pipeline processor code
    # This definition is just here so it shows up in the list of spouts
    pass


@make_spout({'name': Sig(str, None, 'The name of the event to be disabled.')})
async def disable_event_spout(bot, message, values, name):
    '''Disables the specified event.'''
    if name not in events:
        raise ValueError('Event %s does not exist!' % name)
    event = events[name]
    if message.channel.id in event.channels:
        event.channels.remove(message.channel.id)