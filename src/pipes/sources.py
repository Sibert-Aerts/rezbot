import emoji
import random

from .pipe_decorations import *
from utils.texttools import *
from utils.rand import *
from utils.FROG import FROG
import utils.soapstone as soapstone
import utils.benedict as benedict
from utils.frinkiac import simpsons, futurama
import resource.tweets as tweets
from resource.jerkcity import JERKCITY
import utils.util as util

# Add fields here to make them easily accessible (readable and writable) both inside and outside of this file.
class SourceResources:
    previous_pipe_output = ['Nothing here']
    var_dict = {'TEST': ['testing', '1', '2', 'three!']}
    bot = None

#####################################################
#                      Sources                      #
#####################################################


@make_source({})
def prev_source():
    '''The previous pipe outputs.'''
    return SourceResources.previous_pipe_output


@make_source({}, pass_message=True)
def that_source(message):
    '''The previous message in the channel.'''
    msg = [m for m in SourceResources.bot.messages if m.channel == message.channel][-2]
    return [msg.content]


@make_source({'name' : Sig(str, None, 'The variable name')})
def get_source(name):
    '''Loads input stored using the "set" pipe'''
    return SourceResources.var_dict[name]


@make_source({
    'min': Sig(int, 1, 'The minimum value'),
    'max': Sig(int, 20, 'The maximum value'),
    'n'  : Sig(int, 1, 'The amount of rolls')
}, command=True)
@multi_source
def roll_source(min, max):
    '''A dice roll between min and max.'''
    return str(random.randint(min, max))


@make_source({
    'pattern': Sig(str, '', 'The pattern to look for (regex)'),
    'n'      : Sig(int, 1,  'The number of sampled words.')
})
def words_source(pattern, n):
    '''Random dictionary words, optionally matching a pattern.'''
    if pattern != '':
        pattern = re.compile(pattern)
        items = [w for w in allWords if pattern.search(w) is not None]
    else:
        items = allWords
    return random.sample(items, min(n, len(items)))


@make_source({
    'n'     : Sig(int, 1, 'The number of generated messages.'),
    'game'  : Sig(str, '?', 'Which Dark Souls game should be used (? for random).', lambda x:x in ['?','1','2','3']),
    'phrase': Sig(str, '%phrase%', 'Overrides game argument. Construct a custom phrase using the following categories:\n{}'.format(', '.join([c for c in soapstone.phraseDict])))
}, command=True)
@multi_source
def soapstone_source(game, phrase, multi_index):
    '''Random Dark Souls soapstone messages.'''
    if phrase != '%phrase%':
        return soapstone.makePhrase(phrase)
    if game == '?':
        game = choose(['1','2','3'])
    if game == '1':
        return soapstone.DarkSouls1.get()
    if game == '2':
        return soapstone.DarkSouls2.get()
    if game == '3':
        return soapstone.DarkSouls3.get()


@make_source({
    'n' : Sig(int, 1, 'The amount of names.')
}, command=True)
@multi_source
def cumberbatch_source():
    '''Names that resembles that of Benedict Cumberbatch.'''
    return benedict.generate()


@make_source({
    'n' : Sig(int, 1, 'The amount of emoji.')
}, command=True)
@multi_source
def emoji_source():
    '''Random emoji.'''
    return choose(list(emoji.UNICODE_EMOJI.keys())).replace(' ', '')


@make_source({
    'n'         : Sig(int, 1, 'The amount of captions.'),
    'q'         : Sig(str, '', 'Search query, empty for a random quote'),
    'multiline' : Sig(util.parse_bool, True, 'Allow captions longer than one line.')
})
def simpsons_source(n, q, multiline):
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


@make_source({
    'n'         : Sig(int, 1, 'The amount of captions.'),
    'q'         : Sig(str, '', 'Search query, empty for a random quote'),
    'multiline' : Sig(util.parse_bool, True, 'Allow captions longer than one line.')
})
def futurama_source(n, q, multiline):
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


@make_source({
    'q' : Sig(str, '', 'Search query, empty for random tweets.'),
    'n' : Sig(int, 1, 'The amount of tweets.')
})
def dril_source(q, n):
    '''Random dril tweets.'''
    out = []
    if q == '':
        out = tweets.dril.sample(n)
    else:
        out = tweets.dril.search(q, n)
    return [t['text'] for t in out]


@make_source({
    # 'TIP' : Sig(int, -1, 'THE SPECIFIC FROG TIP YOU WISH TO SEE.'),
    'N' : Sig(int, 1, 'NUMBER OF FROG TIPS.')
}, command=True)
def FROG_source(N):
    '''\
    FROG TIPS FOR HOME CONSUMERS, AS SEEN ON HTTPS://FROG.TIPS.
    
    FOR MORE INFORMATION PLEASE CONSULT HTTPS://FROG.TIPS/API/1/.
    '''
    TIPS = [FROG.GET_RANDOM() for _ in range(N)]
    return [T['tip'] for T in TIPS]


@make_source({
    'COMIC' : Sig(int, -1, 'EXACT COMIC NUMBER, -1 FOR QUERY COMIC.'),
    'Q'     : Sig(str, '', 'TITLE OR DIALOG TO LOOK FOR, EMPTY FOR RANDOM COMICS.'),
    'N'     : Sig(int, 1, 'NUMBER OF COMICS TO LOAD LINES FROM.', lambda x: x>0),
    'LINES' : Sig(int, 1, 'NUMBER OF LINES PER COMIC (0 FOR ALL LINES).'),
    'NAMES' : Sig(util.parse_bool, True, 'WHETHER OR NOT DIALOG ATTRIBUTIONS ("spigot: ") ARE KEPT')
})
def JERKCITY_source(COMIC, Q, N, LINES, NAMES):
    ''' JERKCITY COMIC DIALOG '''
    ISSUES = []
    if COMIC == -1:
        if Q == '':
            ISSUES = JERKCITY.GET_RANDOM(N)
        else:
            ISSUES = JERKCITY.SEARCH(Q, N)
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
        _LINES = [re.split(':\s*', LINE, 1)[1] for LINE in _LINES]

    return _LINES