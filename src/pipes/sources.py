import emoji
import random
from datetime import datetime
from functools import wraps

from .signature import Sig
from .pipe import Source, Pipes

from utils.texttools import *
from utils.rand import *
from utils.FROG import FROG
import utils.soapstone as soapstone
import utils.benedict as benedict
from utils.frinkiac import simpsons, futurama
import resource.tweets as tweets
from resource.jerkcity import JERKCITY
import utils.util as util
from resource.upload import uploads


#######################################################
#                     Decorations                     #
#######################################################

def multi_source(func):
    '''
    Decorates a function to take an argument 'n' that simply calls the function multiple times.

    f: (*args) -> y      becomes     f': (*args, n=1) -> [y]
    e.g.
    rand()   -> 0.1      becomes     rand'(n=3) -> [0.5, 0.2, 0.3]
    '''
    @wraps(func)
    def _multi_source(*args, n, **kwargs):
        return [func(*args, **kwargs) for i in range(n)]
    return _multi_source

sources = Pipes()
sources.command_sources = []
_CATEGORY = 'NONE'

def make_source(signature, pass_message=False, command=False):
    '''Makes a source out of a function'''
    def _make_source(func):
        global sources, _CATEGORY
        source = Source(signature, func, _CATEGORY, pass_message)
        sources.add(source)
        if command:
            sources.command_sources.append(source)
        return func
    return _make_source

# Add fields here to make them easily accessible (readable and writable) both inside and outside of this file.
class SourceResources:
    previous_pipeline_output = ['Nothing here']
    var_dict = {'TEST': ['testing', '1', '2', 'three!']}
    bot = None

#####################################################
#                      Sources                      #
#####################################################


@make_source({})
def output_source():
    '''The previous pipe outputs.'''
    return SourceResources.previous_pipeline_output


@make_source({}, pass_message=True)
def that_source(message):
    '''The previous message in the channel.'''
    msg = [m for m in SourceResources.bot.messages if m.channel == message.channel][-2]
    return [msg.content]


@make_source({}, pass_message=True)
def message_source(message):
    '''The message which the bot is responding to, only useful with reactive scripts!'''
    return [message.content]


@make_source({'name' : Sig(str, None, 'The variable name')})
def get_source(name):
    '''Loads input stored using the "set" pipe'''
    return SourceResources.var_dict[name]

def bool_or_none(val):
    if val is None or val == 'None': return None
    return(util.parse_bool(val))

txt_modes = ['s', 'r']
@make_source({
    'file' : Sig(str, None, 'The file name, "random" for a random file'),
    'n'    : Sig(int, 1, 'The amount of lines'),
    'sequential': Sig(bool_or_none, None, 'If the multiple lines should be sequential as opposed to random, "None" for file-dependent.', required=False),
    'sentences' : Sig(bool_or_none, None, 'If the file should be split on sentences as opposed to on dividing characters, "None" for file-dependent.', required=False),
    'query'     : Sig(str, '', 'Optional search query'),
})
def txt_source(file, n, sequential, sentences, query):
    '''Lines from an uploaded text file. Check >files for a list of files.'''
    if file == 'random':
        file = random.choice(list(uploads.files.keys()))

    if file not in uploads:
        raise KeyError('No file "%s" loaded! Check >files for a list of files.' % file)

    file = uploads[file]
    if sequential is None: sequential = file.info.sequential
    if sentences is None: sentences = file.info.sentences

    if sequential:
        return file.get_sequential(n, query, sentences)
    else:
        return file.get_random(n, query, sentences)


@make_source({
    'file'  : Sig(str, None, 'The file name'),
    'n'     : Sig(int, 1, 'The amount of lines'),
    'length': Sig(int, 0, 'The maximum length of the generated sentence. (0 for unlimited)'),
}, command=True)
def markov_source(file, n, length):
    '''Randomly generated markov chains based on an uploaded file. Check >files for a list of files.'''
    if file not in uploads:
        raise KeyError('No file "%s" loaded! Check >files for a list of files.' % file)
    file = uploads[file]
    return file.get_markov_lines(n, length)


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
    'format': Sig(str, '%Y/%m/%d %H:%M:%S', 'The format string, see http://strftime.org/ for syntax.'),
})
def datetime_source(format):
    '''The current date and time, with optional custom formatting.'''
    return [datetime.now().strftime(format)]


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


@make_source({'n' : Sig(int, 1, 'The amount of members.')}, pass_message=True)
def member_source(message, n):
    '''Gets a random member.'''
    members = list(message.server.members)
    return [m.name for m in random.sample(members, min(n, len(members)))]


@make_source({}, pass_message=True)
def me_source(message):
    '''The name of the user invoking the command.'''
    return [message.author.name]


@make_source({
    'n'     : Sig(int, 1, 'The number of generated messages.'),
    'game'  : Sig(str, '?', 'Which Dark Souls game should be used (? for random).', lambda x:x in ['?','1','2','3']),
    'phrase': Sig(str, '%phrase%', 'Overrides game argument. Construct a custom phrase using the following categories:\n{}'.format(', '.join([c for c in soapstone.phraseDict])))
}, command=True)
@multi_source
def soapstone_source(game, phrase):
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
    'NAMES' : Sig(util.parse_bool, False, 'WHETHER OR NOT DIALOG ATTRIBUTIONS ("spigot: ") ARE KEPT')
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