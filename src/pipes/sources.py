from collections import defaultdict
import emoji
import re
import random
import asyncio
from datetime import datetime, timezone, timedelta
from functools import wraps, lru_cache

from discord.ext.commands import Bot

from .signature import Par, Signature, Option, Multi
from .pipe import Source, Sources
from utils.util import parse_bool

import utils.util as util
import utils.soapstone as soapstone
import utils.benedict as benedict
from utils.rand import choose, sample, choose_slice 
from utils.texttools import *
from utils.FROG import FROG
from utils.frinkiac import simpsons, futurama
import resource.tweets as tweets
from resource.jerkcity import JERKCITY
from resource.upload import uploads
from resource.variables import VariableStore
import resource.wikipedia as wikipedia

import nltk


#######################################################
#                     Decorations                     #
#######################################################

def multi_source(func):
    '''
    Decorates a function to take an argument 'n' that simply asynchronously calls the function multiple times.

    f: (*args) -> y      becomes     f': (*args, n=1) -> [y]
    e.g.
    rand()   -> 0.1      becomes     rand'(n=3) -> [0.5, 0.2, 0.3]
    '''
    @wraps(func)
    async def _multi_source(*args, n, **kwargs):
        return await asyncio.gather(*(func(*args, **kwargs) for i in range(n)))
    return _multi_source

def get_which(get_what):
    '''
    Takes a function
        get_what(items:List[X], what:T) -> results:List[Y]
    where `items` and `results` have equal length (i.e. one result per item)
    and extends it to
        get_which(items:List[X], which:List[T]) -> results:List[Y]
    and results has length (#items × #which) ordered so that it's first the attributes of item 1, then the attributes of item 2, etc.
    '''
    def _get_which(item, which):
        w = [ get_what(item, what) for what in which ]
        return [x for y in zip(*w) for x in y]
    return _get_which

sources = Sources()
sources.command_sources = []
_CATEGORY = 'NONE'

def make_source(signature, *, command=False, **kwargs):
    '''
    Makes a source out of a function.

    Keyword arguments:
        command: Whether or not the source should be usable as a standalone bot command (default: False)

        pass_message: Whether or not the function should receive the Discord message as its first argument (default: False)

        plural: The source's name pluralised (default: name + 's')

        depletable: Whether the source allows to request "all" elements (e.g. "{all words}" instead of just "{10 words}"),
    in this case `n` will be passed as -1 (default: False)
    '''
    def _make_source(func):
        global sources, _CATEGORY
        source = Source(Signature(signature), func, _CATEGORY, **kwargs)
        sources.add(source)
        if command:
            sources.command_sources.append(source)
        return func
    return _make_source

# Add fields here to make them easily accessible (readable and writable) both inside and outside of this file.
class SourceResources:
    bot: Bot = None
    previous_pipeline_output = defaultdict(list)
    variables = VariableStore('variables.json')

# So the typename correctly shows up as "regex"
def regex(*args, **kwargs): return re.compile(*args, **kwargs)

#####################################################
#                      Sources                      #
#####################################################

#####################################################
#                 Sources : DISCORD                 #
#####################################################
_CATEGORY = 'DISCORD'

#### MESSAGES #######################################

MESSAGE_WHAT = Option('content', 'id', 'timestamp', 'author_id')
@get_which
def messages_get_what(messages, what):
    if what == MESSAGE_WHAT.content:
        return [msg.content for msg in messages]
    if what == MESSAGE_WHAT.id:
        return [str(msg.id) for msg in messages]
    if what == MESSAGE_WHAT.timestamp:
        return [str(int((msg.created_at.replace(tzinfo=timezone.utc)).timestamp())) for msg in messages]
    if what == MESSAGE_WHAT.author_id:
        return [str(msg.author.id) for msg in messages]


@make_source({}, pass_message=True, plural='those')
async def that_source(message):
    '''The previous message in the channel.'''
    msg = [ msg async for msg in message.channel.history(limit=2) ][1]
    return [msg.content]


@make_source({
    'n': Par(int, 1, 'The number of next messages to wait for.', lambda n: n < 1000),
    'what': Par(Multi(MESSAGE_WHAT), 'content', '/'.join(MESSAGE_WHAT))
}, pass_message=True)
async def next_message_source(message, n, what):
    '''The next message to be sent in the channel.'''
    messages = []

    def check(msg):
        # ignore (most) messages that the bot normally ignores
        return msg.channel == message.channel \
            and not msg.author.bot \
            and msg.content[:len(SourceResources.bot.command_prefix)] != SourceResources.bot.command_prefix

    while len(messages) < n:
        messages.append( await SourceResources.bot.wait_for('message', check=check) )
    return messages_get_what(messages, what)


@make_source({
    'what': Par(Multi(MESSAGE_WHAT), 'content', '/'.join(MESSAGE_WHAT))
}, pass_message=True)
async def message_source(message, what):
    '''The message which triggered script execution. Useful in Event scripts.'''
    return messages_get_what([message], what)


@make_source({
    'n': Par(int, 1, 'The number of messages'),
    'i': Par(int, 1, 'From which previous message to start counting. (0 for the message that triggers the script itself)', lambda i: i <= 10000),
    'what': Par(Multi(MESSAGE_WHAT), 'content', '/'.join(MESSAGE_WHAT)),
    'by': Par(int, 0, 'A user id, if given will filter the results down to only that users\' messages within the range of messages (if any).'),
}, pass_message=True)
async def previous_message_source(message, n, i, what, by):
    '''
    A generalization of {that} and {message} that allows more messages and going further back.
    
    The N messages in this channel, counting backwards from the Ith previous message.
    i.e. N messages, ordered newest to oldest, with the newest being the Ith previous message.
    '''
    messages = [ msg async for msg in message.channel.history(limit=n+i) ][i:i+n]
    if by: messages = [m for m in messages if m.author.id == by]

    return messages_get_what(messages, what)

#### MEMBERS ########################################

MEMBER_WHAT = Option('nickname', 'username', 'id', 'avatar', 'activity', 'color')
@get_which
def members_get_what(members, what):
    if what == MEMBER_WHAT.nickname:
        return [member.display_name for member in members]
    elif what == MEMBER_WHAT.username:
        return [member.name for member in members]
    elif what == MEMBER_WHAT.id:
        return [str(member.id) for member in members]
    elif what == MEMBER_WHAT.avatar:
        return [str(member.avatar) for member in members]
    elif what == MEMBER_WHAT.activity:
        return [str(member.activities[0]) if member.activities else '' for member in members]
    elif what == MEMBER_WHAT.color:
        return [str(member.color) for member in members]

@make_source({
    'what': Par(Multi(MEMBER_WHAT), 'nickname', '/'.join(MEMBER_WHAT))
}, pass_message=True)
async def me_source(message, what):
    '''The name (or other attribute) of the user invoking the script or event.'''
    return members_get_what([message.author], what)


@make_source({
    'n'   : Par(int, 1, 'The maximum number of members to return.'),
    'what': Par(Multi(MEMBER_WHAT), 'nickname', '/'.join(MEMBER_WHAT)),
    'id'  : Par(int, 0, 'The id to match the member by. If given the number of members return will be at most 1.'),
    'name': Par(regex, None, 'A pattern that should match their nickname or username.', required=False),
    # 'rank': ...?
}, pass_message=True, depletable=True)
async def member_source(message, n, what, id, name):
    '''The name (or other attribute) of a random Server member meeting the filters.'''
    members = message.guild.members

    # Filter if necessary
    if id:
        members = filter(lambda m: m.id == id, members)
    if name:
        members = filter(lambda m: re.search(name, m.display_name) or re.search(name, m.name), members)

    # Take a random sample
    members = list(members)
    members = sample(members, n)

    return members_get_what(members, what)

#### CHANNEL ########################################

CHANNEL_WHAT = Option('name', 'topic', 'id', 'category', 'mention')

@make_source({
    'what': Par(CHANNEL_WHAT, 'name', '/'.join(CHANNEL_WHAT)),
}, pass_message=True)
async def channel_source(message, what):
    '''The name (or other attribute) of the current channel.'''
    channel = message.channel
    if what == CHANNEL_WHAT.name:
        return [channel.name]
    if what == CHANNEL_WHAT.id:
        return [str(channel.id)]
    if what == CHANNEL_WHAT.topic:
        return [channel.topic or '']
    if what == CHANNEL_WHAT.category:
        return [channel.category.name] if channel.category else []
    if what == CHANNEL_WHAT.mention:
        return [channel.mention]

#### SERVER ########################################

SERVER_WHAT = Option('name', 'description', 'icon', 'member_count', 'id')

@make_source({
    'what': Par(SERVER_WHAT, SERVER_WHAT.name, '/'.join(SERVER_WHAT)),
}, pass_message=True)
async def server_source(message, what):
    '''The name (or other attribute) of the current server.'''
    server = message.guild
    if what == SERVER_WHAT.name:
        return [server.name]
    if what == SERVER_WHAT.description:
        return [server.description or '']
    if what == SERVER_WHAT.icon:
        return [str(server.icon or '')]
    if what == SERVER_WHAT.member_count:
        return [str(server.member_count)]
    if what == SERVER_WHAT.id:
        return [str(server.id)]


@make_source({
    'n': Par(int, 1, 'The number of emojis'),
    'id': Par(int, None, 'An exact emoji ID to match.', required=False),
    'name': Par(str, None, 'An exact name to match.', required=False),
    'search': Par(str, None, 'A string to search for in the name.', required=False),
    'here': Par(parse_bool, True, 'Whether to restrict to this server\'s emoji.'),
}, pass_message=True, depletable=True)
async def custom_emoji_source(message, n, name, search, id, here):
    '''The server's custom emojis.'''
    if here:
        emojis = message.guild.emojis
    else:
        emojis = [e for guild in SourceResources.bot.guilds for e in guild.emojis]

    if name is not None:
        emojis = [e for e in emojis if e.name == name]
    elif id is not None:
        emojis = [e for e in emojis if e.id == id]
    elif search is not None:
        emojis = [e for e in emojis if search.lower() in e.name.lower()]

    return [ str(emoji) for emoji in sample(emojis, n) ]

#####################################################
#                   Sources : BOT                   #
#####################################################
_CATEGORY = 'BOT'

@make_source({}, pass_message=True)
async def output_source(message):
    '''The entire set of output from the previous script that ran.'''
    return SourceResources.previous_pipeline_output[message.channel]


@make_source({
    'name'    : Par(str, None, 'The variable name'),
    'default' : Par(str, None, 'The default value in case the variable isn\'t assigned (None to throw an error if it isn\'t assigned)', required=False)
}, command=True)
async def get_source(name, default):
    '''Loads variables stored using the "set" pipe'''
    return SourceResources.variables.get(name, None if default is None else [default])


#####################################################
#                  Sources : FILE                   #
#####################################################
_CATEGORY = 'FILE'
# NOTE: the category can't be called "FILE" if I rename "txt" to "file", also the "file" source can't be a command then!

def bool_or_none(val):
    if val is None or val == 'None': return None
    return(util.parse_bool(val))

@make_source({
    'file' : Par(str, None, 'The file name, "random" for a random file'),
    'n'    : Par(int, 1, 'The number of lines'),
    'sequential': Par(bool_or_none, None, 'If the multiple lines should be sequential as opposed to random, "None" for file-dependent.', required=False),
    'sentences' : Par(bool_or_none, None, 'If the file should be split on sentences as opposed to on dividing characters, "None" for file-dependent.', required=False),
    'query'     : Par(str, '', 'Optional search query'),
    'pattern'   : Par(regex, None, 'Optional search regex', required=False),
}, command=True, depletable=True)
async def txt_source(file, n, sequential, sentences, query, pattern):
    '''Lines from an uploaded text file. Check >files for a list of files.'''
    if file == 'random':
        file = random.choice(list(uploads.files.keys()))
    file = uploads[file]

    if sequential is None: sequential = file.info.sequential
    if sentences is None: sentences = file.info.sentences

    if sequential:
        return file.get_sequential(n, sentences, query=query, regex=pattern)
    else:
        return file.get_random(n, sentences, query=query, regex=pattern)


@make_source({
    'file'  : Par(str, None, 'The file name'),
    'n'     : Par(int, 1, 'The amount of lines'),
    'length': Par(int, 0, 'The maximum length of the generated sentence (0 for unlimited)'),
    'start' : Par(str, None, 'One or two starting words to continue a sentence from (NOTE: EXTREMELY FINNICKY)', required=False)
}, command=True)
async def markov_source(file, n, length, start):
    '''Randomly generated markov chains based on an uploaded file. Check >files for a list of files.'''
    file = uploads[file]
    return file.get_markov_lines(n, length, start)


@make_source({
    'file'   : Par(str, None, 'The file name'),
    'tag'    : Par(str, None, 'The POS tag'),
    'uniform': Par(util.parse_bool, False, 'Whether to pick pieces uniformly or based on their frequency'),
    'n'      : Par(int, 1, 'The amount of pieces')
}, depletable=True, plural='pos')
async def pos_source(file, tag, uniform, n):
    '''
        Returns a Piece Of Sentence from a given text file that match a given grammatical POS tag.

        See >files for a list of uploaded files.
        List of POS tags: https://universaldependencies.org/docs/u/pos/
        See also the `POS_fill` pipe.
    '''
    file = uploads[file]
    pos_buckets = file.get_pos_buckets()
    
    tag = tag.upper()
    if tag in pos_buckets:
        # Slightly inconsistent behaviour: "ALL" gives all unique words, but the normal case may give repeats
        # Also, "ALL" returns each word once, regardless of the word's weight ?
        if n == -1:
            return list(pos_buckets[tag].words)
        if uniform:
            return random.choices( pos_buckets[tag].words, k=n )
        return random.choices( pos_buckets[tag].words, cum_weights=pos_buckets[tag].cum_weights, k=n)
    else: # Sad fallback: just return the tag n times
        return [tag] * n if n > 0 else []



#####################################################
#                 Sources : QUOTES                  #
#####################################################
_CATEGORY = 'QUOTES'


@make_source({
    'n'         : Par(int, 1, 'The amount of captions.'),
    'q'         : Par(str, '', 'Search query, empty for a random quote'),
    'multiline' : Par(util.parse_bool, True, 'Allow captions longer than one line.')
}, plural='simpsons')
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
    'n'         : Par(int, 1, 'The amount of captions.'),
    'q'         : Par(str, '', 'Search query, empty for a random quote'),
    'multiline' : Par(util.parse_bool, True, 'Allow captions longer than one line.')
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
    'query' : Par(str, '', 'Search query, empty for random tweets.'),
    'n' : Par(int, 1, 'The amount of tweets.')
}, depletable=True)
async def dril_source(query, n):
    '''Random dril tweets.'''
    out = []
    if query == '':
        out = tweets.dril.sample(n)
    else:
        out = tweets.dril.search(query, n)
    return [t['text'] for t in out]


@make_source({
    'query': Par(str, '', 'Search query, empty for random tweets.'),
    'n' :    Par(int, 1, 'The amount of tweets.')
}, depletable=True)
async def trump_source(query, n):
    '''Random trump tweets.'''
    out = []
    if query == '':
        out = tweets.trump.sample(n)
    else:
        out = tweets.trump.search(query, n)
    return [t['text'] for t in out]


@make_source({
    'COMIC' : Par(int, -1, 'EXACT COMIC NUMBER, -1 FOR QUERY COMIC.'),
    'QUERY' : Par(str, '', 'TITLE OR DIALOG TO LOOK FOR (FUZZY!), EMPTY FOR RANDOM COMICS.'),
    'N'     : Par(int, 1, 'NUMBER OF COMICS TO LOAD LINES FROM.', lambda x: x>0),
    'LINES' : Par(int, 1, 'NUMBER OF LINES PER COMIC (0 FOR ALL LINES).'),
    'NAMES' : Par(util.parse_bool, False, 'WHETHER OR NOT DIALOG ATTRIBUTIONS ("spigot: ") ARE KEPT')
}, plural='JERKCITIES', depletable=True)
async def JERKCITY_source(COMIC, QUERY, N, LINES, NAMES):
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

@make_source({
    'n'     : Par(int, 1, 'The number of generated messages.'),
    'game'  : Par(SOULS_GAME, '?', 'Which game should be used (1/2/3/B/S/? for random).'),
    'phrase': Par(str, '%phrase%', 'Overrides game argument. Construct a custom phrase using the following categories:\nphrase, {}'.format(', '.join(soapstone.phraseDict)))
}, command=True)
@multi_source
async def soapstone_source(game, phrase):
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



#####################################################
#                  Sources : ETC.                   #
#####################################################
_CATEGORY = 'ETC'

@make_source({
    'min': Par(int, 1, 'The minimum value'),
    'max': Par(int, 20, 'The maximum value'),
    'n'  : Par(int, 1, 'The amount of rolls')
}, command=True)
@multi_source
async def roll_source(min, max):
    '''A dice roll between min and max.'''
    return str(random.randint(min, max))


@make_source({
    'start': Par(int, 0, 'The starting of the range'),
    'end':   Par(int, None, 'The end of the range (not included in the range!)'),
    'step':  Par(int, 1, 'The step size')
})
async def range_source(start, end, step):
    ''' The complete range of numbers from start to end with a given step size.
    More precisely:
    The list [start, start + step, start + 2*step, ..., x ] so that x is "one step short" of reaching/passing end'''
    return list(map(str, range(start, end, step)))


@make_source({
    'format': Par(str, '%Y/%m/%d %H:%M:%S', 'The format, see http://strftime.org/ for syntax.'),
    'utc'   : Par(float, 0, 'The offset from UTC in hours.'),
    'timestamp': Par(int, None, 'The UNIX UTC timestamp to format, leave empty to use the current time.', required=False),
    'parse': Par(str, None, 'A datetime string to parse and reformat, leave empty to use the current time.', required=False),
    'pformat': Par(str, '%Y/%m/%d %H:%M:%S', 'The format according to which to parse `parse`.'),
})
async def datetime_source(format, utc, timestamp, parse, pformat):
    '''
    The current date and time formatted to be human readable.
    The `utc` parameter determines timezone and daylight savings offsets.
    '''
    tz = timezone(timedelta(hours=utc))
    if timestamp and parse:
        raise ValueError("Values given for both `timestamp` and `parse` arguments.")
    if timestamp:
        time = datetime.fromtimestamp(timestamp, tz)
    elif parse:
        time = datetime.strptime(parse, pformat)
        # Date is assumed UTC unless it (somehow) specifies
        if time.tzinfo is None:
            time.replace(tzinfo=timezone.utc)
        time.astimezone(tz)
    else:
        time = datetime.now(tz) 
    return [time.strftime(format)]


@make_source({
    'utc'   : Par(float, 0, 'The offset from UTC in hours to interpret the date as being.'),
    'parse': Par(str, None, 'A datetime string to parse and reformat, leave empty to use the current time.', required=False),
    'pformat': Par(str, '%Y/%m/%d %H:%M:%S', 'The format according to which to parse `parse`.'),
    })
async def timestamp_source(utc, parse, pformat):
    '''
    A date and time as a UNIX timestamp, representing seconds since 1970/01/01 00:00:00 UTC.
    The UNIX timestamp is independent of timezones.
    '''
    tz = timezone(timedelta(hours=utc))
    if parse is not None:
        time = datetime.strptime(parse, pformat).replace(tzinfo=tz)
    else:
        time = datetime.now(tz) 
    return [str(int(time.timestamp()))]


@make_source({
    'pattern': Par(regex, None, 'The pattern to look for', required=False),
    'n'      : Par(int, 1, 'The number of sampled words.')
}, depletable=True)
async def word_source(pattern, n):
    '''Random dictionary words, optionally matching a pattern.'''
    if pattern:
        items = [w for w in allWords if pattern.search(w)]
    else:
        items = allWords
    return sample(items, n)


EMOJI_LIST = list(emoji.EMOJI_DATA)

@make_source({
    'n' : Par(int, 1, 'The amount of emoji.'),
    'oldest' : Par(float, 0.6, 'How old the emoji can be, inclusive.'),
    'newest' : Par(float, 15, 'How new the emoji can be, inclusive.'),
}, command=True)
async def emoji_source(n, oldest, newest):
    '''
    Random emoji.
    
    For oldest/newest, float values represent "Emoji versions" as defined by the Unicode Consortium.
    '''
    emoji_list = EMOJI_LIST

    # Only filter if it's even needed
    if oldest > 0.6 or newest < 15:
        def condition(e):
            age = emoji.EMOJI_DATA[e]["E"]
            return (age >= oldest and age <= newest) 
        emoji_list = list(filter(condition, emoji_list))

    return choose(emoji_list, n)



#####################################################
#               Sources : WIKIPEDIA                 #
#####################################################
_CATEGORY = 'WIKI'

# Cache the most recent Wikipedia pages based on (name, language)
@lru_cache(maxsize=20)
def _wikipedia_page(page, language):
    wikipedia.set_lang(language)
    return wikipedia.page(page)
    
WIKIPEDIA_WHAT = Option('title', 'url', 'summary', 'content', 'images', 'videos', 'audio', 'links')
_img_re = re.compile(r'(?i)(png|jpe?g|gif|webp)$')
_banned_imgs = ['https://upload.wikimedia.org/wikipedia/commons/7/74/Red_Pencil_Icon.png', 'https://upload.wikimedia.org/wikipedia/commons/f/f9/Double-dagger-14-plain.png']
_vid_re = re.compile(r'(?i)(webm|gif|mp4|ogv)$')
_aud_re = re.compile(r'(?i)(mp3|ogg|wav)$')
_svg_re = re.compile(r'(?i)(svg)$')

def _wikipedia_get_what(page, what, n):
    if what == WIKIPEDIA_WHAT.title:
        return [page.title]
    elif what == WIKIPEDIA_WHAT.url:
        return [page.url]
    elif what == WIKIPEDIA_WHAT.summary:
        if not hasattr(page, 'summary_sentences'):
            sentences = nltk.sent_tokenize(page.summary)
            sentences = [ re.sub(r'\n[\n\s]*', ' ', s) for s in sentences ]
            page.summary_sentences = sentences
        return choose_slice( page.summary_sentences, n )
    elif what == WIKIPEDIA_WHAT.content:
        if not hasattr(page, 'content_sentences'):
            # Get rid of section titles before parsing sentences
            content = re.sub(r'^==+ .+ ==+\s*$', '', page.content, flags=re.M)
            sentences = nltk.sent_tokenize(content)
            sentences = [ re.sub(r'\n[\n\s]*', ' ', s) for s in sentences ]
            page.content_sentences = sentences
        return choose_slice( page.content_sentences, n )
    elif what == WIKIPEDIA_WHAT.images:
        return sample( [img for img in page.images if _img_re.search(img) and img not in _banned_imgs], n )
    elif what == WIKIPEDIA_WHAT.videos:
        return sample( list(filter(_vid_re.search, page.images)), n )
    elif what == WIKIPEDIA_WHAT.audio:
        return sample( list(filter(_aud_re.search, page.images)), n )
    elif what == WIKIPEDIA_WHAT.links:
        return sample( page.links, n )

@make_source({
    'language': Par(str, 'en', 'Which language Wikipedia you want to use. (list: https://meta.wikimedia.org/wiki/List_of_Wikipedias)'),
    'lines': Par(int, 1, 'The number of (what) you want ,for summary/content this means number of sentences.'),
    'what': Par(Multi(WIKIPEDIA_WHAT), 'summary', 'Which part(s) of the pages you want: ' + '/'.join(WIKIPEDIA_WHAT)),
    'n' : Par(int, 1, 'The number of random pages to fetch')
})
async def wikipedia_random_source(what, language, lines, n):
    '''
    Fetches information from one or more random Wikipedia pages.
    '''
    pages = []
    for _ in range(n):
        while True:
            ## Despite the module/API's insistence, wikipedia.random() may return an ambiguous page title
            ## and EVEN when you then pick a random disambiguated one, it may still be ambiguous (or invalid) anyway???
            ## So JUST KEEP freaking trying, it only fails like 1% of the time anyway
            page = wikipedia.random()
            try:
                pages.append( _wikipedia_page(page, language) )
                break
            except wikipedia.DisambiguationError as e:
                try:
                    page = choose(e.options)
                    pages.append( _wikipedia_page(page, language) )
                    break
                except:
                    pass
            except:
                pass
    
    return [ s for page in pages for wh in what for s in _wikipedia_get_what(page, wh, lines) ]


@make_source({
    'page': Par(str, None, 'The page you want information from. (For a random page, use wikipedia_random.)', lambda s: s),
    'language': Par(str, 'en', 'Which language Wikipedia you want to use. (list: https://meta.wikimedia.org/wiki/List_of_Wikipedias)'),
    'what': Par(Multi(WIKIPEDIA_WHAT), 'summary', 'Which part(s) of the pages you want: ' + '/'.join(WIKIPEDIA_WHAT)),
    'n'   : Par(int, 1, 'The number of (what) you want, for summary/content this means number of sentences.')
}, depletable=True)
async def wikipedia_source(page, what, language, n):
    '''
    Fetches various information from a Wikipedia page.
    
    Donate to wikimedia: https://donate.wikimedia.org/
    '''
    page = _wikipedia_page(page, language)
    return [ s for wh in what for s in _wikipedia_get_what(page, wh, n) ]


@make_source({
    'query': Par(str, None, 'The search query')
})
async def wikipedia_search_source(query):
    '''Returns the top Wikipedia search results for the query.'''
    return wikipedia.search(query)
