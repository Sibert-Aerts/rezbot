import emoji
import random
import asyncio
from datetime import datetime, timezone, timedelta
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
    async def _multi_source(*args, n, **kwargs):
        return await asyncio.gather(*[func(*args, **kwargs) for i in range(n)])
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
    previous_pipeline_output = []
    var_dict = {'TEST': ['testing', '1', '2', 'three!']}
    bot = None


#####################################################
#                      Sources                      #
#####################################################

#####################################################
#                 Sources : DISCORD                 #
#####################################################
_CATEGORY = 'DISCORD'

@make_source({}, pass_message=True)
async def that_source(message):
    '''The previous message in the channel.'''
    msg = ( await message.channel.history(limit=2).flatten() )[1]
    return [msg.content]


MESSAGE_WHAT_OPTIONS = ['content', 'id', 'timestamp', 'author_id']
@make_source({
    'what': Sig(str, 'content', '/'.join(MESSAGE_WHAT_OPTIONS), lambda w: w.lower() in MESSAGE_WHAT_OPTIONS)
}, pass_message=True)
async def message_source(message, what):
    ''' The message which triggered script execution. Useful in Event scripts. '''
    if what == 'content':
        return [message.content]
    if what == 'id':
        return [message.id]
    if what == 'timestamp':
        return [message.datetime.timestamp()]
    if what == 'author_id':
        return [message.author.id]


@make_source({
    'n': Sig(int, 1, 'The number of messages'),
    'i': Sig(int, 1, 'From which previous message to start counting. (0 for the message that triggers the script itself)'),
    'what': Sig(str, 'content', '/'.join(MESSAGE_WHAT_OPTIONS), lambda w: w.lower() in MESSAGE_WHAT_OPTIONS)
}, pass_message=True)
async def previous_message_source(message, n, i, what):
    '''
    A generalization of {this} and {message} that allows more messages and going further back.
    
    The N messages in this channel, counting backwards from the Ith previous message.
    i.e. N messages, ordered newest to oldest, with the newest being the Ith previous message.
    '''
    # Arbitrary limit on how far back you can load messages
    if i > 100: return ValueError('`I` should be smaller than 100')
    
    msgs = ( await message.channel.history(limit=n+i+1).flatten() )[i+1:i+1+n]
    if what == 'content':
        return [msg.content for msg in msgs]
    if what == 'id':
        return [msg.id for msg in msgs]
    if what == 'timestamp':
        return [msg.datetime.timestamp() for msg in msgs]
    if what == 'author_id':
        return [msg.author.id for msg in msgs]

MEMBER_WHAT_OPTIONS = ['nickname', 'username', 'id', 'avatar']
def _members_get_what(members, what):
    what = what.lower()
    if what == 'nickname':
        return [member.display_name for member in members]
    elif what == 'username':
        return [member.name for member in members]
    elif what == 'id':
        return [str(member.id) for member in members]
    elif what == 'avatar':
        return [str(member.avatar_url) for member in members]


@make_source({
    'what': Sig(str, 'nickname', '/'.join(MEMBER_WHAT_OPTIONS), lambda w: w.lower() in MEMBER_WHAT_OPTIONS)
}, pass_message=True)
async def me_source(message, what):
    '''The name (or other attribute) of the user invoking the script or event.'''
    return _members_get_what([message.author], what)


@make_source({
    'n'   : Sig(int, 1, 'The maximum number of members to return.'),
    'what': Sig(str, 'nickname', '/'.join(MEMBER_WHAT_OPTIONS), lambda w: w.lower() in MEMBER_WHAT_OPTIONS),
    'id'  : Sig(int, 0, 'The id to match the member by. If given the number of members return will be at most 1.'),
    'name': Sig(str, '', 'A string that should be part of their nickname or username.'),
    # 'rank': ...?
}, pass_message=True)
async def member_source(message, n, what, id, name):
    '''The name (or other attribute) of a random Server member meeting the filters.'''
    members = message.guild.members

    # Filter if necessary
    if id:
        members = filter(lambda m: m.id == id, members)
    if name:
        members = filter(lambda m: name in m.display_name or name in m.name, members)

    # Take a random sample
    members = list(members)
    if n < len(members):
        members = random.sample(members, n)

    return _members_get_what(members, what)


CHANNEL_WHAT_OPTIONS = ['name', 'topic', 'id', 'category', 'mention']

@make_source({
    'what': Sig(str, 'name', '/'.join(CHANNEL_WHAT_OPTIONS), lambda w: w.lower() in CHANNEL_WHAT_OPTIONS),
}, pass_message=True)
async def channel_source(message, what):
    '''The name (or other attribute) of the current channel.'''
    what = what.lower()
    channel = message.channel
    if what == 'name':
        return [channel.name]
    if what == 'id':
        return [channel.id]
    if what == 'topic':
        return [channel.topic]
    if what == 'category':
        return [channel.category.name] if channel.category else []
    if what == 'mention':
        return [channel.mention]


SERVER_WHAT_OPTIONS = ['name', 'description', 'icon', 'member_count']

@make_source({
    'what': Sig(str, 'name', '/'.join(SERVER_WHAT_OPTIONS), lambda w: w.lower() in SERVER_WHAT_OPTIONS),
}, pass_message=True)
async def server_source(message, what):
    '''The name (or other attribute) of the current server.'''
    what = what.lower()
    server = message.guild
    if what == 'name':
        return [server.name]
    if what == 'description':
        return [server.description]
    if what == 'icon':
        return [str(server.icon_url)]
    if what == 'member_count':
        return [server.member_count]


@make_source({
    'n': Sig(int, 1, 'The number of emojis'),
}, pass_message=True)
async def custom_emoji_source(message, what):
    '''The server's custom emojis.'''
    emojis = message.guild.emojis
    return random.sample( emojis, min(n, len(emojis)) )

#####################################################
#                  Sources : OTHER                  #
#####################################################
_CATEGORY = 'OTHER'

@make_source({})
async def output_source():
    '''The previous pipe outputs.'''
    return SourceResources.previous_pipeline_output


@make_source({
    'name'    : Sig(str, None, 'The variable name'),
    'default' : Sig(str, None, 'The default value if the variable isn\'t assigned (None for error)', required=False)
}, command=True)
async def get_source(name, default):
    '''Loads input stored using the "set" pipe'''
    if name in SourceResources.var_dict or default is None:
        return SourceResources.var_dict[name]
    else:
        return [default]


def bool_or_none(val):
    if val is None or val == 'None': return None
    return(util.parse_bool(val))

@make_source({
    'file' : Sig(str, None, 'The file name, "random" for a random file'),
    'n'    : Sig(int, 1, 'The amount of lines'),
    'sequential': Sig(bool_or_none, None, 'If the multiple lines should be sequential as opposed to random, "None" for file-dependent.', required=False),
    'sentences' : Sig(bool_or_none, None, 'If the file should be split on sentences as opposed to on dividing characters, "None" for file-dependent.', required=False),
    'query'     : Sig(str, '', 'Optional search query'),
    'pattern'   : Sig(str, '', 'Optional search regex'),
})
async def txt_source(file, n, sequential, sentences, query, pattern):
    '''Lines from an uploaded text file. Check >files for a list of files.'''
    if file == 'random':
        file = random.choice(list(uploads.files.keys()))

    if file not in uploads:
        raise KeyError('No file "%s" loaded! Check >files for a list of files.' % file)

    file = uploads[file]
    if sequential is None: sequential = file.info.sequential
    if sentences is None: sentences = file.info.sentences

    if sequential:
        return file.get_sequential(n, sentences, query=query, regex=pattern)
    else:
        return file.get_random(n, sentences, query=query, regex=pattern)


@make_source({
    'file'  : Sig(str, None, 'The file name'),
    'n'     : Sig(int, 1, 'The amount of lines'),
    'length': Sig(int, 0, 'The maximum length of the generated sentence. (0 for unlimited)'),
}, command=True)
async def markov_source(file, n, length):
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
async def roll_source(min, max):
    '''A dice roll between min and max.'''
    return str(random.randint(min, max))


@make_source({
    'format': Sig(str, '%Y/%m/%d %H:%M:%S', 'The format string, see http://strftime.org/ for syntax.'),
    'utc'   : Sig(int, 1, 'The UTC offset in hours.')
})
async def datetime_source(format, utc):
    '''The current date and time, with optional custom formatting.'''
    return [datetime.now(timezone(timedelta(hours=utc))).strftime(format)]


@make_source({
    'pattern': Sig(str, '', 'The pattern to look for (regex)'),
    'n'      : Sig(int, 1,  'The number of sampled words.')
})
async def words_source(pattern, n):
    '''Random dictionary words, optionally matching a pattern.'''
    if pattern != '':
        pattern = re.compile(pattern)
        items = [w for w in allWords if pattern.search(w) is not None]
    else:
        items = allWords
    return random.sample(items, min(n, len(items)))


@make_source({
    'n'     : Sig(int, 1, 'The number of generated messages.'),
    'game'  : Sig(str, '?', 'Which game should be used (1/2/3/B/? for random).', lambda x:x.lower() in ['?','1','2','3','b']),
    'phrase': Sig(str, '%phrase%', 'Overrides game argument. Construct a custom phrase using the following categories:\n{}'.format(', '.join([c for c in soapstone.phraseDict])))
}, command=True)
@multi_source
async def soapstone_source(game, phrase):
    '''Random Dark Souls soapstone messages.'''
    if phrase != '%phrase%':
        return soapstone.makePhrase(phrase)
    game = game.lower()
    if game == '?':
        game = choose(['1','2','3','b'])
    if game == '1':
        return soapstone.DarkSouls1.get()
    if game == '2':
        return soapstone.DarkSouls2.get()
    if game == '3':
        return soapstone.DarkSouls3.get()
    if game == 'b':
        return soapstone.Bloodborne.get()


@make_source({
    'n' : Sig(int, 1, 'The amount of names.')
}, command=True)
@multi_source
async def cumberbatch_source():
    '''Names that resembles that of Benedict Cumberbatch.'''
    return benedict.generate()


@make_source({
    'n' : Sig(int, 1, 'The amount of emoji.')
}, command=True)
@multi_source
async def emoji_source():
    '''Random emoji.'''
    return choose(list(emoji.UNICODE_EMOJI.keys())).replace(' ', '')


@make_source({
    'n'         : Sig(int, 1, 'The amount of captions.'),
    'q'         : Sig(str, '', 'Search query, empty for a random quote'),
    'multiline' : Sig(util.parse_bool, True, 'Allow captions longer than one line.')
})
async def simpsons_source(n, q, multiline):
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
async def futurama_source(n, q, multiline):
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
async def dril_source(q, n):
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
async def FROG_source(N):
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
async def JERKCITY_source(COMIC, Q, N, LINES, NAMES):
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