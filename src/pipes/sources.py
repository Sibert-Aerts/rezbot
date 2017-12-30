import emoji

from .pipe_decorations import *
from utils.texttools import *
from utils.rand import *
import utils.soapstone as soapstone
import utils.benedict as benedict
import utils.frinkiac as frinkiac
import resource.tweets as tweets
import utils.util as util

# Add fields here to make them easily accessible (readable and writable) both inside and outside of this file.
class SourceResources:
    previous_pipe_output = ['Nothing here']
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


@make_source({
    'pattern': Sig(str, '', 'The pattern to look for (regex)'),
    'n'      : Sig(int, 1,  'The number of sampled words.')
}, command=True)
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
            val = frinkiac.random_caption().split('\n')
        else:
            val = frinkiac.search_caption(q).split('\n')
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