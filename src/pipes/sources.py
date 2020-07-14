import emoji
import re
import random
import asyncio
from datetime import datetime, timezone, timedelta
from functools import wraps, lru_cache

from .signature import Sig
from .pipe import Source, Sources

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
import nltk
import wikipedia


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

def get_which(get_what):
    '''
    Takes a function
        get_what(items:List[X], attribute:str) -> results: List[Y]
    where items and results have equal length (i.e. one result per item)
    and extends it to
        get_which(items:List[X], attributes:str) -> results: List[Y]
    where attributes is a string of multiple (attribute)s joined by ","
    and results has length (#items × #attributes) ordered so that it's first the attributes of item 1, then the attributes of item 2, etc.
    
    e.g. if get_what = lambda x,y: x[y]
        then get_which({'foo': 'bar', 'abc': 'xyz'}, 'foo,abc,foo') returns ['bar', 'xyz', 'bar']
    '''
    def _get_which(item, which):
        w = [ get_what(item, what) for what in which.split(',') ]
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
        source = Source(signature, func, _CATEGORY, **kwargs)
        sources.add(source)
        if command:
            sources.command_sources.append(source)
        return func
    return _make_source

# Add fields here to make them easily accessible (readable and writable) both inside and outside of this file.
class SourceResources:
    previous_pipeline_output = []
    var_dict = {}
    bot = None


#####################################################
#                      Sources                      #
#####################################################

#####################################################
#                 Sources : DISCORD                 #
#####################################################
_CATEGORY = 'DISCORD'

#### MESSAGES #######################################

MESSAGE_WHAT_OPTIONS = ['content', 'id', 'timestamp', 'author_id']
@get_which
def _messages_get_what(messages, what):
    what = what.lower()
    if what == 'content':
        return [msg.content for msg in messages]
    if what == 'id':
        return [str(msg.id) for msg in messages]
    if what == 'timestamp':
        return [str(int(msg.created_at.timestamp())) for msg in messages]
    if what == 'author_id':
        return [str(msg.author.id) for msg in messages]


@make_source({}, pass_message=True, plural='those')
async def that_source(message):
    '''The previous message in the channel.'''
    msg = ( await message.channel.history(limit=2).flatten() )[1]
    return [msg.content]


@make_source({
    'n': Sig(int, 1, 'The number of next messages to wait for.', lambda n: n < 1000),
    'what': Sig(str, 'content', '/'.join(MESSAGE_WHAT_OPTIONS), options=MESSAGE_WHAT_OPTIONS, multi_options=True)
}, pass_message=True)
async def next_message_source(message, n, what):
    '''The next message to be sent in the channel.'''
    messages = []
    while len(messages) < n:
        messages.append( await SourceResources.bot.wait_for('message', check=lambda m: m.channel == message.channel) )
    return _messages_get_what(messages, what)


@make_source({
    'what': Sig(str, 'content', '/'.join(MESSAGE_WHAT_OPTIONS), options=MESSAGE_WHAT_OPTIONS, multi_options=True)
}, pass_message=True)
async def message_source(message, what):
    '''The message which triggered script execution. Useful in Event scripts.'''
    return _messages_get_what([message], what)


@make_source({
    'n': Sig(int, 1, 'The number of messages'),
    'i': Sig(int, 1, 'From which previous message to start counting. (0 for the message that triggers the script itself)'),
    'what': Sig(str, 'content', '/'.join(MESSAGE_WHAT_OPTIONS), options=MESSAGE_WHAT_OPTIONS, multi_options=True),
    'by': Sig(int, 0, 'A user id, if given will filter the results down to only that users\' messages within the range of messages (if any).'),
}, pass_message=True)
async def previous_message_source(message, n, i, what, by):
    '''
    A generalization of {this} and {message} that allows more messages and going further back.
    
    The N messages in this channel, counting backwards from the Ith previous message.
    i.e. N messages, ordered newest to oldest, with the newest being the Ith previous message.
    '''
    # Arbitrary limit on how far back you can load messages I guess?
    if i > 10000: raise ValueError('`I` should be smaller than 10000')

    messages = ( await message.channel.history(limit=n+i).flatten() )[i:i+n]
    if by:
        messages = [m for m in messages if m.author.id == by]

    return _messages_get_what(messages, what)

#### MEMBERS ########################################

MEMBER_WHAT_OPTIONS = ['nickname', 'username', 'id', 'avatar']
@get_which
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
    # elif what == 'activity':
    #     return [str(member.activities[0]) if member.activities else '' for member in members]

@make_source({
    'what': Sig(str, 'nickname', '/'.join(MEMBER_WHAT_OPTIONS), options=MEMBER_WHAT_OPTIONS, multi_options=True)
}, pass_message=True)
async def me_source(message, what):
    '''The name (or other attribute) of the user invoking the script or event.'''
    return _members_get_what([message.author], what)


@make_source({
    'n'   : Sig(int, 1, 'The maximum number of members to return.'),
    'what': Sig(str, 'nickname', '/'.join(MEMBER_WHAT_OPTIONS), options=MEMBER_WHAT_OPTIONS, multi_options=True),
    'id'  : Sig(int, 0, 'The id to match the member by. If given the number of members return will be at most 1.'),
    'name': Sig(str, '', 'A regex that should match their nickname or username.'),
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

    return _members_get_what(members, what)

#### CHANNEL ########################################

CHANNEL_WHAT_OPTIONS = ['name', 'topic', 'id', 'category', 'mention']

@make_source({
    'what': Sig(str, 'name', '/'.join(CHANNEL_WHAT_OPTIONS), options=CHANNEL_WHAT_OPTIONS),
}, pass_message=True)
async def channel_source(message, what):
    '''The name (or other attribute) of the current channel.'''
    what = what.lower()
    channel = message.channel
    if what == 'name':
        return [channel.name]
    if what == 'id':
        return [str(channel.id)]
    if what == 'topic':
        return [channel.topic or '']
    if what == 'category':
        return [channel.category.name] if channel.category else []
    if what == 'mention':
        return [channel.mention]

#### SERVER ########################################

SERVER_WHAT_OPTIONS = ['name', 'description', 'icon', 'member_count']

@make_source({
    'what': Sig(str, 'name', '/'.join(SERVER_WHAT_OPTIONS), options=SERVER_WHAT_OPTIONS),
}, pass_message=True)
async def server_source(message, what):
    '''The name (or other attribute) of the current server.'''
    what = what.lower()
    server = message.guild
    if what == 'name':
        return [server.name]
    if what == 'description':
        return [server.description or '']
    if what == 'icon':
        return [str(server.icon_url or '')]
    if what == 'member_count':
        return [str(server.member_count)]


@make_source({
    'n': Sig(int, 1, 'The number of emojis'),
    'name': Sig(str, None, 'The name of the emoji if you want a specific one.', required=False),
}, pass_message=True, depletable=True)
async def custom_emoji_source(message, n, name):
    '''The server's custom emojis.'''
    emojis = message.guild.emojis
    if name:
        emojis = [e for e in emojis if e.name == name]
    return [ str(emoji) for emoji in sample(emojis, n) ]

#####################################################
#                   Sources : BOT                   #
#####################################################
_CATEGORY = 'BOT'

@make_source({})
async def output_source():
    '''The entire set of output from the previous script that ran.'''
    # TODO: make this work PER CHANNEL
    return SourceResources.previous_pipeline_output


@make_source({
    'name'    : Sig(str, None, 'The variable name'),
    'default' : Sig(str, None, 'The default value in case the variable isn\'t assigned (None to throw an error if it isn\'t assigned)', required=False)
}, command=True)
async def get_source(name, default):
    '''Loads variables stored using the "set" pipe'''
    if name in SourceResources.var_dict or default is None:
        return SourceResources.var_dict[name]
    else:
        return [default]


#####################################################
#                  Sources : FILE                   #
#####################################################
_CATEGORY = 'FILE'
# NOTE: the category can't be called "FILE" if I rename "txt" to "file", also the "file" source can't be a command then!

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
    'file'  : Sig(str, None, 'The file name'),
    'n'     : Sig(int, 1, 'The amount of lines'),
    'length': Sig(int, 0, 'The maximum length of the generated sentence. (0 for unlimited)'),
}, command=True)
async def markov_source(file, n, length):
    '''Randomly generated markov chains based on an uploaded file. Check >files for a list of files.'''
    file = uploads[file]
    return file.get_markov_lines(n, length)


@make_source({
    'file'  : Sig(str, None, 'The file name'),
    'tag'   : Sig(str, None, 'The POS tag'),
    'n'     : Sig(int, 1, 'The amount of phrases or tokens')
}, depletable=True, plural='POS')
async def POS_source(file, tag, n):
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
        # Slightly inconsistent behaviour: "ALL" gives all unique words, but the normal case can give repeats
        if n == -1: return list(pos_buckets[tag])
        return random.choices( pos_buckets[tag], k=n)
    else: # Sad fallback: just return the tag n times
        return [tag] * n if n > 0 else []



#####################################################
#                 Sources : QUOTES                  #
#####################################################
_CATEGORY = 'QUOTES'


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
    'query' : Sig(str, '', 'Search query, empty for random tweets.'),
    'n' : Sig(int, 1, 'The amount of tweets.')
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
    'COMIC' : Sig(int, -1, 'EXACT COMIC NUMBER, -1 FOR QUERY COMIC.'),
    'QUERY' : Sig(str, '', 'TITLE OR DIALOG TO LOOK FOR (FUZZY!), EMPTY FOR RANDOM COMICS.'),
    'N'     : Sig(int, 1, 'NUMBER OF COMICS TO LOAD LINES FROM.', lambda x: x>0),
    'LINES' : Sig(int, 1, 'NUMBER OF LINES PER COMIC (0 FOR ALL LINES).'),
    'NAMES' : Sig(util.parse_bool, False, 'WHETHER OR NOT DIALOG ATTRIBUTIONS ("spigot: ") ARE KEPT')
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


@make_source({
    'n'     : Sig(int, 1, 'The number of generated messages.'),
    'game'  : Sig(str, '?', 'Which game should be used (1/2/3/B/? for random).', options=['?','1','2','3','b']),
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



#####################################################
#                  Sources : ETC.                   #
#####################################################
_CATEGORY = 'ETC'

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
    'start': Sig(int, 0, 'The starting of the range'),
    'end':   Sig(int, None, 'The end of the range (not included in the range!)'),
    'step':  Sig(int, 1, 'The step size')
})
async def range_source(start, end, step):
    ''' The complete range of numbers from start to end with a given step size.
    More precisely:
    The list [start, start + step, start + 2*step, ..., x ] so that x is "one step short" of reaching/passing end'''
    return list(map(str, range(start, end, step)))


@make_source({
    'format': Sig(str, '%Y/%m/%d %H:%M:%S', 'The format string, see http://strftime.org/ for syntax.'),
    'utc'   : Sig(int, 0, 'The UTC offset in hours.')
})
async def datetime_source(format, utc):
    '''The current date and time, with optional custom formatting.'''
    return [datetime.now(timezone(timedelta(hours=utc))).strftime(format)]


@make_source({
    'utc' : Sig(int, 0, 'The UTC offset in hours.')
})
async def timestamp_source(utc):
    '''The current date and time as a UNIX timestamp representing seconds since 1970.'''
    return [str(int(datetime.now(timezone(timedelta(hours=utc))).timestamp()))]


@make_source({
    'pattern': Sig(str, '', 'The pattern to look for (regex)'),
    'n'      : Sig(int, 1, 'The number of sampled words.')
}, depletable=True)
async def word_source(pattern, n):
    '''Random dictionary words, optionally matching a pattern.'''
    if pattern:
        try:
            pattern = re.compile(pattern)
        except Exception as e:
            raise ValueError( 'Invalid regex pattern `%s`: %s' % (pattern, e) )
        items = [w for w in allWords if pattern.search(w) is not None]
    else:
        items = allWords
    return sample(items, n)


@make_source({
    'n' : Sig(int, 1, 'The amount of emoji.')
}, command=True)
@multi_source
async def emoji_source():
    '''Random emoji.'''
    return choose(list(emoji.UNICODE_EMOJI.keys())).replace(' ', '')



#####################################################
#               Sources : WIKIPEDIA.                #
#####################################################
_CATEGORY = 'WIKI'

# Cache Wikipedia pages based on (name, language)
@lru_cache()
def _wikipedia_page(page, language):
    wikipedia.set_lang(language)
    return wikipedia.page(page)
    
WIKIPEDIA_WHAT = ['title', 'url', 'summary', 'content', 'images', 'videos', 'audio', 'links']
_img_re = re.compile(r'(?i)(png|jpe?g|gif|webp)$')
_banned_imgs = ['https://upload.wikimedia.org/wikipedia/commons/7/74/Red_Pencil_Icon.png']
_vid_re = re.compile(r'(?i)(webm|gif|mp4)$')
_aud_re = re.compile(r'(?i)(mp3|ogg|ogv|wav)$')
_svg_re = re.compile(r'(?i)(svg)$')

def _wikipedia_get_what(page, what, n):
    what = what.lower()
    if what == 'title':
        return [page.title]
    elif what == 'url':
        return [page.url]
    elif what == 'summary':
        if not hasattr(page, 'summary_sentences'):
            sentences = nltk.sent_tokenize(page.summary)
            sentences = [ re.sub(r'\n[\n\s]*', ' ', s) for s in sentences ]
            page.summary_sentences = sentences
        return choose_slice( page.summary_sentences, n )
    elif what == 'content':
        if not hasattr(page, 'content_sentences'):
            # Get rid of section titles before parsing sentences
            content = re.sub(r'^==+ .+ ==+\s*$', '', page.content, flags=re.M)
            sentences = nltk.sent_tokenize(content)
            sentences = [ re.sub(r'\n[\n\s]*', ' ', s) for s in sentences ]
            page.content_sentences = sentences
        return choose_slice( page.content_sentences, n )
    elif what == 'images':
        return sample( [img for img in page.images if _img_re.search(img) and img not in _banned_imgs], n )
    elif what == 'videos':
        return sample( list(filter(_vid_re.search, page.images)), n )
    elif what == 'audio':
        return sample( list(filter(_aud_re.search, page.images)), n )
    elif what == 'links':
        return sample( page.links, n )

@make_source({
    'language': Sig(str, 'en', 'Which language Wikipedia you want to use. (list: https://meta.wikimedia.org/wiki/List_of_Wikipedias)'),
    'lines': Sig(int, 1, 'The number of (what) you want ,for summary/content this means number of sentences.'),
    'what': Sig(str, 'Summary', 'Which part(s) of the pages you want: ' + '/'.join(WIKIPEDIA_WHAT), options=WIKIPEDIA_WHAT, multi_options=True),
    'n' : Sig(int, 1, 'The number of random pages to fetch')
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
    
    which = what.split(',')
    return [ s for page in pages for what in which for s in _wikipedia_get_what(page, what, lines) ]


@make_source({
    'page': Sig(str, None, 'The page you want information from. (For a random page, use wikipedia_random.)'),
    'language': Sig(str, 'en', 'Which language Wikipedia you want to use. (list: https://meta.wikimedia.org/wiki/List_of_Wikipedias)'),
    'what': Sig(str, 'summary', 'Which part(s) of the page you want: ' + '/'.join(WIKIPEDIA_WHAT), options=WIKIPEDIA_WHAT, multi_options=True),
    'n' : Sig(int, 1, 'The number of (what) you want, for summary/content this means number of sentences.')
}, depletable=True)
async def wikipedia_source(page, what, language, n):
    '''
    Fetches various information from a Wikipedia page.
    
    Donate to wikimedia: https://donate.wikimedia.org/
    '''
    page = _wikipedia_page(page, language)
    return [ s for what in what.split(',') for s in _wikipedia_get_what(page, what, n) ]


@make_source({
    'query': Sig(str, None, 'The search query')
})
async def wikipedia_search_source(query):
    '''Returns the top Wikipedia search results for the query.'''
    return wikipedia.search(query)