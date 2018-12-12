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

@make_spout({
    'name':     Sig(str, 'test_user', 'The account\'s display name.'),
    'handle':   Sig(str, 'test_user', 'The account\'s handle, (without the @).'),
    'icon':     Sig(url, 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png', 'URL linking to their profile picture.')
})
async def tweet_spout(send_message, values, name, handle, icon):
    '''Outputs text as an embedded tweet.'''
    e = Embed(description='\n'.join(values), color=0x4f545c)
    e.set_author(name='{} (@{})'.format(name, handle), url='https://twitter.com/'+handle, icon_url=icon)
    e.set_footer(text='Twitter', icon_url='https://abs.twimg.com/icons/apple-touch-icon-192x192.png')
    e.add_field(name='Retweets', value=random.randint(500, 5000))
    e.add_field(name='Likes', value=random.randint(1000, 10000))
    await send_message(embed=e)

@make_spout({}, command=True)
async def trump_tweet_spout(send_message, values):
    '''Outputs text as an embedded tweet from the president of the united states.'''
    e = Embed(description='\n'.join(values), color=0x4f545c)
    e.set_author(name='Donald J. Trump (@realDonaldTrump)', url='https://twitter.com/realDonaldTrump', icon_url='https://pbs.twimg.com/profile_images/874276197357596672/kUuht00m_bigger.jpg')
    e.set_footer(text='Twitter', icon_url='https://abs.twimg.com/icons/apple-touch-icon-192x192.png')
    e.add_field(name='Retweets', value=random.randint(5000, 50000))
    e.add_field(name='Likes', value=random.randint(25000, 150000))
    await send_message(embed=e)