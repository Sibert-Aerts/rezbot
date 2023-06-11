import re
import random

from .sources import source_from_func, set_category, multi_source
from ..signature import Par, Option

import utils.util as util
import utils.soapstone as soapstone
from utils.rand import choose 
from utils.texttools import *
from utils.frinkiac import simpsons, futurama
import resource.tweets as tweets
from resource.jerkcity import JERKCITY


#####################################################
#                 Sources : QUOTES                  #
#####################################################
set_category('QUOTES')


@source_from_func({
    'n'         : Par(int, 1, 'The amount of captions.'),
    'q'         : Par(str, '', 'Search query, empty for a random quote'),
    'multiline' : Par(util.parse_bool, True, 'Allow captions longer than one line.')
}, plural='simpsons')
async def simpsons_source(ctx, n, q, multiline):
    '''Random simpsons captions from the Frinkiac.com API.'''
    out = []
    for i in range(n):
        if q == '':
            val = simpsons.random_caption().split('\n')
        else:
            val = simpsons.search_caption(q).split('\n')
        if multiline:
            out.extend(val)
        else:
            out.append(choose(val))
    return out


@source_from_func({
    'n'         : Par(int, 1, 'The amount of captions.'),
    'q'         : Par(str, '', 'Search query, empty for a random quote'),
    'multiline' : Par(util.parse_bool, True, 'Allow captions longer than one line.')
})
async def futurama_source(ctx, n, q, multiline):
    '''Random futurama captions from the Morbotron.com API.'''
    out = []
    for i in range(n):
        if q == '':
            val = futurama.random_caption().split('\n')
        else:
            val = futurama.search_caption(q).split('\n')
        if multiline:
            out.extend(val)
        else:
            out.append(choose(val))
    return out


@source_from_func({
    'query' : Par(str, '', 'Search query, empty for random tweets.'),
    'n' : Par(int, 1, 'The amount of tweets.')
}, depletable=True)
async def dril_source(ctx, query, n):
    '''Random dril tweets.'''
    out = []
    if query == '':
        out = tweets.dril.sample(n)
    else:
        out = tweets.dril.search(query, n)
    return [t['text'] for t in out]


@source_from_func({
    'query': Par(str, '', 'Search query, empty for random tweets.'),
    'n' :    Par(int, 1, 'The amount of tweets.')
}, depletable=True)
async def trump_source(ctx, query, n):
    '''Random trump tweets.'''
    out = []
    if query == '':
        out = tweets.trump.sample(n)
    else:
        out = tweets.trump.search(query, n)
    return [t['text'] for t in out]


@source_from_func({
    'COMIC' : Par(int, -1, 'EXACT COMIC NUMBER, -1 FOR QUERY COMIC.'),
    'QUERY' : Par(str, '', 'TITLE OR DIALOG TO LOOK FOR (FUZZY!), EMPTY FOR RANDOM COMICS.'),
    'N'     : Par(int, 1, 'NUMBER OF COMICS TO LOAD LINES FROM.', lambda x: x>0),
    'LINES' : Par(int, 1, 'NUMBER OF LINES PER COMIC (0 FOR ALL LINES).'),
    'NAMES' : Par(util.parse_bool, False, 'WHETHER OR NOT DIALOG ATTRIBUTIONS ("spigot: ") ARE KEPT')
}, plural='JERKCITIES', depletable=True)
async def JERKCITY_source(CTX, COMIC, QUERY, N, LINES, NAMES):
    ''' JERKCITY COMIC DIALOG '''
    ISSUES = []
    if COMIC == -1:
        if QUERY == '':
            ISSUES = JERKCITY.GET_RANDOM(N)
        else:
            ISSUES = JERKCITY.SEARCH(QUERY, N)
    else:
        ISSUES = [JERKCITY.GET(COMIC)] * N

    _LINES = []
    if LINES == 0:
        _LINES = [LINE for ISSUE in ISSUES for LINE in ISSUE.DIALOG.split('\n') if LINE.strip() != '']
    else:
        for ISSUE in ISSUES:
            THESE_LINES = [LINE for LINE in ISSUE.DIALOG.split('\n') if LINE.strip() != '']
            I = random.randint(0, len(THESE_LINES) - LINES) if len(THESE_LINES) >= LINES else 0
            _LINES.extend(THESE_LINES[I:I+LINES])

    if not NAMES:
        _NONAMES = []
        for LINE in _LINES:
            S = re.split(':\s*', LINE, 1)
            _NONAMES.append(S[1] if len(S) > 1 else LINE)
        _LINES = _NONAMES

    return _LINES

SOULS_GAME = Option('?','1','2','3','b','s', name='game', stringy=True)

@source_from_func({
    'n'     : Par(int, 1, 'The number of generated messages.'),
    'game'  : Par(SOULS_GAME, '?', 'Which game should be used (1/2/3/B/S/? for random).'),
    'phrase': Par(str, '%phrase%', 'Overrides game argument. Construct a custom phrase using the following categories:\nphrase, {}'.format(', '.join(soapstone.phraseDict)))
}, command=True)
@multi_source
async def soapstone_source(ctx, game, phrase):
    '''Random Dark Souls soapstone messages.'''
    if phrase != '%phrase%':
        return soapstone.makePhrase(phrase)
    if game == '?':
        game = choose(['1','2','3','b', 's'])
    if game == '1':
        return soapstone.DarkSouls1.get()
    if game == '2':
        return soapstone.DarkSouls2.get()
    if game == '3':
        return soapstone.DarkSouls3.get()
    if game == 'b':
        return soapstone.Bloodborne.get()
    if game == 's':
        return soapstone.Sekiro.get()


