import random

from discord import Embed

from .signature import Sig
from .pipe import Spout, Pipes


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
    return int(h, base=16)


@make_spout({
    'title':    Sig(str, '', 'The title.'),
    'color':    Sig(hex, 0, 'The highlight color as a hexadecimal value.'),
})
async def embed_spout(bot, message, values, title, color):
    '''Outputs text as a simple discord embed.'''
    e = Embed(title=title, description='\n'.join(values), color=color)
    await message.channel.send(embed=e)


@make_spout({
    'name':     Sig(str, 'test_user', 'The account\'s display name.'),
    'handle':   Sig(str, 'test_user', 'The account\'s handle, (without the @).'),
    'icon':     Sig(url, 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png', 'URL linking to their profile picture.'),
    'retweets': Sig(str, '', 'The number of retweets, hidden if empty.'),
    'likes':    Sig(str, '', 'The number of likes, hidden if empty.'),
})
async def tweet_spout(bot, message, values, name, handle, icon, retweets, likes):
    '''Outputs text as an embedded tweet.'''
    e = Embed(description='\n'.join(values), color=0x4f545c)
    e.set_author(name='{} (@{})'.format(name, handle), url='https://twitter.com/'+handle, icon_url=icon)
    e.set_footer(text='Twitter', icon_url='https://abs.twimg.com/icons/apple-touch-icon-192x192.png')
    if retweets: e.add_field(name='Retweets', value=retweets)
    if likes: e.add_field(name='Likes', value=likes)
    await message.channel.send(embed=e)


@make_spout({}, command=True)
async def trump_tweet_spout(bot, message, values):
    '''Outputs text as an embedded tweet from the president of the united states.'''
    e = Embed(description='\n'.join(values), color=0x4f545c)
    e.set_author(name='Donald J. Trump (@realDonaldTrump)', url='https://twitter.com/realDonaldTrump', icon_url='https://pbs.twimg.com/profile_images/874276197357596672/kUuht00m_bigger.jpg')
    e.set_footer(text='Twitter', icon_url='https://abs.twimg.com/icons/apple-touch-icon-192x192.png')
    e.add_field(name='Retweets', value=random.randint(5000, 50000))
    e.add_field(name='Likes', value=random.randint(25000, 150000))
    await message.channel.send(embed=e)


@make_spout({})
async def delete_message_spout(bot, message, values):
    '''Deletes the message that triggered the script's execution.'''
    await message.delete()


@make_spout({})
async def message_spout(bot, message, values):
    '''Prints the message as a message, PLACEHOLDER until i properly turn print into a spout.....'''
    await message.channel.send('\n'.join(values))


@make_spout({})
async def suppress_print_spout(bot, message, values):
    '''(WIP) Prevents the default behaviour of printing output to a Discord message.
    Useful for Event scripts that silently modify variables, or that don't do anything in certain circumstances.'''
    # NOP, just having *any* spout is enough to prevent the default "print" behaviour
    pass