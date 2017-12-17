from .pipe_decorations import *
from utils.texttools import *
from utils.rand import *
import utils.soapstone as soapstone
import utils.benedict as benedict

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
    'n': Sig(int, 1, 'The amount of random words')
}, command=True)
def random_source(n):
    '''Random dictionary words.'''
    return [choose(allWords) for i in range(n)]


@make_source({
    'pattern': Sig(str, None, 'The pattern to look for (regex)'),
    'n'      : Sig(int, 1, 'The number of sampled words.')
}, command=True)
def find_source(pattern, n):
    '''Random dictionary words matching a pattern.'''
    pattern = re.compile(pattern)
    items = [w for w in allWords if pattern.search(w) is not None]
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
def cumberbatch():
    '''A name that resembles that of Benedict Cumberbatch.'''
    return benedict.generate()