import unicodedata2
import urllib.parse
import emoji
import utils.util as util
import random
import math
import textwrap
import re
import hashlib
from configparser import ConfigParser
from functools import wraps, lru_cache

from datamuse import datamuse
from google.cloud import translate_v2 as translate
import nltk
from simpleeval import SimpleEval
import spacy
spacy.LOADED_NLP = None

from .signature import Par, Signature, Option, Multi
from .pipe import Pipe, Pipes
from .logger import ErrorLog
from .templatedstring import TemplatedString
from utils.texttools import vowelize, consonize, letterize, letterize2, converters, min_dist, case_pattern
from utils.choicetree import ChoiceTree
from utils.rand import choose_slice
from utils.util import parse_bool
from resource.upload import uploads
import permissions

#######################################################
#                      Decorators                     #
#######################################################

def one_to_one(func):
    '''
    Decorate a function to accept an array of first arguments:
    i.e.
    f: (X, ...) -> Y        becomes     f': (List[X], ...) -> List[Y]
    e.g.
    pow(3, 2) == 9          becomes     pow'([3, 4, 5], 2) == [9, 16, 25]
    '''
    @wraps(func)
    def _one_to_one(input, *args, **kwargs):
        return [func(item, *args, **kwargs) for item in input]
    return _one_to_one

def one_to_many(func):
    '''
    Same as one_to_one except it flattens outputs:
    i.e.
    (X, ...) -> List[Y]     becomes     (List[X], ...) -> List[Y]
    '''
    @wraps(func)
    def _one_to_many(input, *args, **kwargs):
        return [out for item in input for out in func(item, *args, **kwargs)]
    return _one_to_many

def many_to_one(func):
    ''' Doesn't do anything, just a label. '''
    return func

_word_splitter = re.compile(r'([\w\'-]+)') # groups together words made out of letters or ' or -

def word_to_word(func):
    '''
    Decorator allowing a pipe to treat input on a word-by-word basis, with symbols etc. removed.
    '''
    @wraps(func)
    def _word_to_word(line, *args, **kwargs):
        split = re.split(_word_splitter, line)
        for i in range(1, len(split), 2):
            split[i] = func(split[i], *args, **kwargs)
        return ''.join(split)
    return one_to_one(_word_to_word)

pipes = Pipes()
pipes.command_pipes = []
_CATEGORY = 'NONE'

def make_pipe(signature, command=False, may_use=None):
    '''Makes a Pipe out of a function.'''
    def _make_pipe(func):
        global pipes, _CATEGORY
        pipe = Pipe(Signature(signature), func, category=_CATEGORY, may_use=may_use)
        pipes.add(pipe)
        if command:
            pipes.command_pipes.append(pipe)
        return func
    return _make_pipe


#####################################################
#                       Pipes                       #
#####################################################

#####################################################
#                   Pipes : FLOW                    #
#####################################################
_CATEGORY = 'FLOW'

@make_pipe( {
    'times': Par(int, None, 'Number of times repeated'),
    'max'  : Par(int, -1, 'Maximum number of outputs produced, -1 for unlimited.')
})
def repeat_pipe(input, times, max):
    '''Repeats each row a given number of times.'''
    if max == -1:
        return input * times
    else:
        times = min(times, math.ceil(max/len(input))) # Limit how many unnecessary items the [:max] in the next line shaves off
        return (input*times)[:max]


REMOVE_WHAT = Option('all', 'empty', 'whitespace')

@make_pipe({ 
    'what': Par(REMOVE_WHAT, REMOVE_WHAT.all, 'What to filter: all/empty/whitespace') 
})
def remove_pipe(items, what):
    '''
    Removes all items (or specific types of items) from the flow.

    all: Removes every item
    whitespace: Removes items that only consist of whitespace (including empty ones)
    empty: Only removes items equal to the empty string ("")
    '''
    if what == REMOVE_WHAT.all:
        return []
    if what == REMOVE_WHAT.whitespace:
        return [x for x in items if x.strip()]
    if what == REMOVE_WHAT.empty:
        return [x for x in items if x]


@make_pipe({})
def sort_pipe(input):
    '''Sorts the input values lexicographically.'''
    # IMPORTANT: `input` is passed BY REFERENCE, so we are NOT supposed to mess with it!
    out = input[:]
    out.sort()
    return out


@make_pipe({})
def reverse_pipe(input):
    '''Reverses the order of input items.'''
    return input[::-1]


@make_pipe({})
def shuffle_pipe(input):
    '''Randomly shuffles input values.'''
    # IMPORTANT NOTE: `input` is passed BY REFERENCE, so we are NOT supposed to mess with it!
    out = input[:]
    random.shuffle(out)
    return out


@make_pipe({
    'number' : Par(int, 1, 'The number of values to choose.', lambda x: x>=0)
})
def choose_pipe(input, number):
    '''Chooses random values with replacement (i.e. may return repeated values).'''
    return random.choices(input, k=number)


@make_pipe({
    'length' : Par(int, None, 'The desired slice length.', lambda x: x>=0),
    'cyclical': Par(parse_bool, False, 'Whether or not the slice is allowed to "loop back" to cover both some first elements and last elements. ' +
            'i.e. If False, elements at the start and end of the input have lower chance of being selected, if True all elements have an equal chance.')
})
def choose_slice_pipe(input, length, cyclical):
    '''Chooses a random contiguous sequence of inputs.'''
    return choose_slice(input, length, cyclical=cyclical)


@make_pipe({
    'number' : Par(int, 1, 'The number of values to sample.', lambda x: x>=0) 
})
def sample_pipe(input, number):
    '''
    Chooses random values without replacement.
    Never produces more values than the number it receives.
    '''
    return random.sample(input, min(len(input), number))


@make_pipe({
    'count' : Par(parse_bool, False, 'Whether each unique item should be followed by an item counting its number of occurrences')
})
def unique_pipe(input, count):
    '''Leaves only the first unique occurence of each item.'''
    if not count: return [*{*input}]

    values = []
    counts = []
    for value in input:
        try:
            counts[values.index(value)] += 1
        except:
            values.append(value)
            counts.append(1)
    counts = map(str, counts)
    return [x for tup in zip(values, counts) for x in tup]


@make_pipe({})
@many_to_one
def count_pipe(input):
    '''Counts the number of input items.'''
    return [str(len(input))]



#####################################################
#                  Pipes : STRING                   #
#####################################################
_CATEGORY = 'STRING'

# So the type name shows up as "regex"
def regex(*args, **kwargs): return re.compile(*args, **kwargs)


@make_pipe({
    'f' : Par(str, None, 'The format string. Items of the form {0}, {1} etc. are replaced with the respective item at that index.')
})
@many_to_one
def format_pipe(input, f):
    ''' Formats inputs according to a given template. '''
    ## Due to arguments automatically being formatted as described, this pipe does nothing but return `f` as its only output.
    return [f]


@make_pipe({})
@one_to_one
def reverse_text_pipe(text):
    ''' Reverses each text string individually. '''
    return text[::-1]


@make_pipe({})
@many_to_one
def length_pipe(input):
    ''' Gives the total length in characters of all items. '''
    return [str(sum( len(text) for text in input ))]


@make_pipe({
    'on' : Par(regex, None, 'Pattern to split on'),
    'lim': Par(int, 0, 'Maximum number of splits. (0 for no limit)')
})
@one_to_many
def split_pipe(text, on, lim):
    '''Splits the input into multiple outputs according to a pattern.'''
    return re.split(on, text, maxsplit=lim)


@make_pipe({
    's' : Par(str, '', 'The separator inserted between two items.')
})
@many_to_one
def join_pipe(input, s):
    ''' Joins inputs into a single item, separated by the given separator. '''
    return [s.join(input)]


@make_pipe({
    'pattern': Par(regex, None, 'The pattern to find')
})
@one_to_many
def find_all_pipe(text, pattern):
    '''
    Extracts all pattern matches from the input.
    Only groups (parentheses) are returned, or the entire matched string if no groups are present.
    '''
    matches = pattern.findall(text)
    # matches is either a List[str] or a List[Tuple[str]] depending on the regex
    if matches and isinstance(matches[0], tuple):
        return [match for tup in matches for match in tup]
    return matches


@make_pipe({
    'from': Par(regex, None, 'Pattern to replace'),
    'to' : Par(str, None, 'Replacement string'),
})
@one_to_one
def sub_pipe(text, to, **argc):
    '''
    Substitutes regex patterns in text.
    Use \\1, \\2, ... in the `to` string to insert matched groups (parentheses) of the regex pattern.
    '''
    return argc['from'].sub(to, text)

DIRECTION = Option('left', 'center', 'right')

@make_pipe({
    'width': Par(int, None, 'How many characters to trim each string down to.'),
    'where': Par(DIRECTION, DIRECTION.right, 'Which side to trim from: left/center/right'),
})
@one_to_one
def trim_pipe(text, width, where):
    ''' Trims input text to a certain width, discarding the rest. '''
    if where == DIRECTION.left:
        return text[-width:]
    if where == DIRECTION.right:
        return text[:width]
    if where == DIRECTION.center:
        diff = max(0, len(text)-width)
        return text[ diff//2 : -math.ceil(diff/2) ]


@make_pipe({
    'width': Par(int, None, 'The minimum width to pad to.'),
    'where': Par(DIRECTION, DIRECTION.right, 'Which side to pad on: left/center/right'),
    'fill' : Par(str, ' ', 'The character used to pad out the string.'),
})
@one_to_one
def pad_pipe(text, where, width, fill):
    ''' Pads input text to a certain width. '''
    if where == DIRECTION.left:
        return text.rjust(width, fill)
    if where == DIRECTION.center:
        return text.center(width, fill)
    if where == DIRECTION.right:
        return text.ljust(width, fill)


@make_pipe({})
@one_to_one
def strip_pipe(value):
    ''' Strips whitespace from the start and end of each input text. '''
    return value.strip()


WRAP_MODE = Option('dumb', 'smart')

@make_pipe({
    'mode' : Par(WRAP_MODE, WRAP_MODE.smart, 'How to wrap: dumb (char-by-char) or smart (on spaces).'),
    'width': Par(int, 40, 'The minimum width to pad to.')
})
@one_to_many
def wrap_pipe(text, mode, width):
    '''
    Text wraps input text.
    Split input text into multiple output lines so that each line is shorter than a given number of characters.
    '''
    if mode == WRAP_MODE.dumb:
        return [text[i:i+width] for i in range(0, len(text), width)]
    if mode == WRAP_MODE.smart:
        return textwrap.wrap(text, width)


@make_pipe({
    'pattern': Par(str, None, 'Case pattern to apply'),
})
def case_pipe(inputs, pattern):
    '''
    Converts the case of each input according to a pattern.

    A pattern is parsed as a sequence 4 types of actions:
    • Upper/lowercase characters (A/a) enforce upper/lowercase
    • Neutral characters (?!_-,.etc.) leave case unchanged
    • Carrot (^) swaps upper to lowercase and the other way around

    Furthermore, parentheseses will repeat that part to stretch the pattern to fit the entire input.

    Examples:
        A       Just turns the first character uppercase
        Aa      Turns the first character upper, the second lower
        A(a)    Turns the first character upper, all others lower
        A(-)A   Turns the first upper, the last lower
        ^(Aa)^  Reverses the first and last characters, AnD DoEs tHiS To tHe oNeS BeTwEeN
    '''
    return case_pattern(pattern, *inputs)


TABLE_ALIGN = Option('l', 'c', 'r', name='alignment')

@make_pipe({
    'columns':    Par(str, None, 'The names of the different columns separated by commas, OR an integer giving the number of columns.'),
    'alignments': Par(Multi(TABLE_ALIGN), 'l', 'How the columns should be aligned: l/c/r separated by commas.'),
    'sep':        Par(str, ' │ ', 'The column separator'),
    'max_width':  Par(int, 100, 'The maximum desired width the output table should have, -1 for no limit.'),
    'code_block': Par(parse_bool, True, 'If the table should be wrapped in a Discord code block (triple backticks).'),
})
@many_to_one
def table_pipe(input, columns, alignments, sep, code_block, max_width):
    '''
    Formats input as an ASCII-art table.
    
    If max_width is exceeded, the table will change layout to attempt to remain legible,
    at the cost of no longer strictly adhering to a proper table layout, or in extreme cases, a table layout whatsoever.
    '''
    try:
        colNames = None
        colCount = int(columns)
    except:
        colNames = columns.split(',')
        colCount = len(colNames)

    if colCount <= 0:
        raise ValueError('Number of columns should be at least 1.')
    # Pad out the list of alignments with itself
    alignments = alignments * math.ceil( colCount/len(alignments) )

    # `table` is a list of lists of strings: `entry = table[row][column]`
    table = [ input[i:i+colCount] for i in range(0, len(input), colCount) ]
    # Pad out the last row with empty strings
    table[-1] += [''] * (colCount - len(table[-1]))

    ## Calculate the desired width of each column
    colWidths = [ max(len(row[i]) for row in table) for i in range(colCount) ]
    if colNames:
        colWidths = [ max(w, len(name)) for (w, name) in zip(colWidths, colNames) ]

    formatWidth = len(sep)*(colCount-1) + 2
    tableWidth = sum(colWidths) + formatWidth
    
    def pad(text, width, where, what=' '):
        if where is TABLE_ALIGN.l: return text.ljust(width, what)
        if where is TABLE_ALIGN.c: return text.center(width, what)
        if where is TABLE_ALIGN.r: return text.rjust(width, what)

    if tableWidth <= max_width:
        ### BEST CASE: The ideal table lay-out fits within the max_width.
        rows = [ ' %s ' % sep.join( pad(row[i], colWidths[i], alignments[i]) for i in range(colCount) ) for row in table ]
        if colNames:
            rows = [ '_%s_' % sep.replace(' ', '_').join([ pad(colNames[i], colWidths[i], alignments[i], '_') for i in range(colCount) ]) ] + rows

    else:
        minRowWidths = [ sum(len(cell) for cell in row) + formatWidth for row in table ]
        minNamesWidth = 0 if not colNames else sum(len(name) for name in colNames) + formatWidth
        altTableWidth = max(minNamesWidth, max(minRowWidths))

        if max_width < 0 or altTableWidth <= max_width:
            ### OK CASE: Each row individually does fit within the max_width.
            # So we'll lay out each row 'individually', ruining the table alignment,
            #   but we do pad the cells so that the rows are at least equal in length.
            # "TODO": Is there some smarter way to pad those cells to try and preserve bits of grid-like structure?

            def w(n, m, i):
                ''' w equally distributes the spare width `n` over `m` different cells indexed `i` '''
                return n//m if i >= (n%m) else math.ceil(n/m)
                
            def pad2(text, extra, where, what=' '):
                if where is TABLE_ALIGN.l: return text.ljust(len(text) + extra, what)
                if where is TABLE_ALIGN.c: return text.center(len(text) + extra, what)
                if where is TABLE_ALIGN.r: return text.rjust(len(text) + extra, what)

            rows = []
            if colNames:
                room = altTableWidth-minNamesWidth
                s = [ pad2(colNames[i], w(room, colCount, i), alignments[i], '_') for i in range(colCount) ]
                rows.append('_%s_' % sep.replace(' ', '_').join(s))

            for r in range(len(table)):
                room = altTableWidth-minRowWidths[r]
                s = [ pad2(table[r][i], w(room, colCount, i), alignments[i], ' ') for i in range(colCount) ]
                rows.append(' %s ' % sep.join(s))

        else:
            ### BAD CASE: There are rows which even individually are simply too wide to fit the max_width.
            # So we simply lay out each row's entries one after the other, with different rows separated with a horizontal line
            if colNames: namesWidth = max(len(name) for name in colNames)
            rows = []
            for row in table:
                if colNames:
                    rows += [ pad(colNames[i], namesWidth, TABLE_ALIGN.r) + ': ' + row[i] for i in range(len(colNames)) ]
                else:
                    rows += row
                rows.append('─' * max_width)
            del rows[-1]

    return [ ('```\n%s\n```' if code_block else '%s') % '\n'.join(rows) ]


class MapType:
    ''' Type used as argument for the map pipe. '''
    def __init__(self, text: str):
        self.map = {}
        self.caseMap = {}
        self.invMap = {}
        self.invCaseMap = {}
        for entry in text.split(','):
            key, val = entry.split(':', 1)
            self.map[key] = val
            self.caseMap[key.lower()] = val
            self.invMap[val] = key
            self.invCaseMap[val.lower()] = key

    def __repr__(self): return '<Map with {} entries>'.format(len(self.map))

    def get(self, key):
        return self.map[key]
    def caseGet(self, key):
        return self.caseMap[key.lower()]
    def invGet(self, key):
        return self.invMap[key]
    def invCaseGet(self, key):
        return self.invCaseMap[key.lower()]


@make_pipe({
    'map': Par(MapType, None, 'A sequence `key:value` entries separated by commas.'),
    'default': Par(str, None, 'The default fallback value. Leave undefined to cause an error instead.', required=False),
    'case': Par(parse_bool, False, 'If mapping should be case sensitive.'),
    'invert': Par(parse_bool, False, 'If the map should map inversely (i.e. values to keys).'),
})
@one_to_one
def map_pipe(item: str, map: MapType, case: bool, invert: bool, default: str):
    ''' 
    Map specific items to specific other items via a literal map.

    Warning: Crudely implemented, special characters ',' and ':' cannot be escaped.
    '''
    try:
        return ((map.get if case else map.caseGet) if not invert else (map.invGet if case else map.invCaseGet))(item)
    except:
        if default is not None:
            return default
        raise KeyError('No map entry for item "{}"'.format(item))


@make_pipe({
    'file': Par(str, None, 'The name of the file to be matched from. >files for a list of files'),
    'min':  Par(int, 0, 'Upper limit on minimum distance (e.g. 1 to never get the same word).')
}, command=True)
@one_to_one
def nearest_pipe(text, min, file):
    ''' Replaces each item with the nearest item (by edit distance) from the given file. '''
    file = uploads[file]
    return min_dist(text, min, file.get())


@make_pipe({
    'random': Par(int, None, 'If given, only produces the given number of (possibly repeating) random expansions. ' \
        'If there are a large number of possible expansions and you only want a few random ones, this option is far more efficient '\
        'than simply generating all of them before randomly choosing some.', 
        required=False),
})
@one_to_many
def expand_pipe(text, random):
    '''
    Expands [bracket|choice] syntax.
    
    e.g.
    `[Mike|Jay] likes [cat|dog[|go]]s`
    produces
    ```
    Mike likes cats
    Jay likes cats
    Mike likes dogs
    Jay likes dogs
    Mike likes doggos
    Jay likes doggos
    ```
    '''
    tree = ChoiceTree(text, add_brackets=True)
    if random is None:
        return list(tree)
    else:
        return [tree.random() for i in range(random)]


#####################################################
#                   Pipes : META                    #
#####################################################
_CATEGORY = 'META'


@make_pipe({
    'f': Par(str, None, 'The format string. Items of the form {0}, {1} etc. are replaced with the respective item at that index, twice.')
})
@many_to_one
def format2_pipe(input, f):
    '''
    Formats inputs according to a template which may itself be constructed via template.

    (Should be read as "format²")
    
    In truth, the regular `format` pipe does nothing but discard all its inputs, only returning its `f` argument instead.
    Rezbot scripting already automatically "formats" the `f` argument, and so it behaves exactly as you want!

    However, if you want the *format itself* to be variable according to input, then this is the pipe for you.

    e.g. `>> ~{0~}+~{1~}|a|b > format2 {}`
    produces `a+b`
    '''
    return [f.format(*input)]


@make_pipe({
    'force_single': Par(parse_bool, False, 'Whether to force each input string to evaluate to one output string.')
})
async def evaluate_sources_pipe(items, force_single: bool):
    '''
    Evaluates sources in the literal strings it receives.
    '''
    errors = ErrorLog()
    output = []
    try:
        for item in items:
            values, errs = await TemplatedString.evaluate_string(item, None, None, forceSingle=force_single)
            if values: output.extend(values)
            errors.extend(errs)
    except:
        raise ValueError('Bad source strings! (Can\'t tell you specific errors right now sorry.)')
    if errors.terminal:
        raise ValueError('Bad source strings! (Can\'t tell you specific errors right now sorry.)')
    # TODO: pipes can produce/access error logs?
    return output


# TODO: "apply" pipe, whose args may be a pipe or even pipeline

#####################################################
#                  Pipes : LETTER                   #
#####################################################
_CATEGORY = 'LETTER'

@make_pipe({
    'p' : Par(float, 0.4, 'Character swap probability'),
}, command=True)
@one_to_one
def vowelize_pipe(text, p):
    ''' Randomly replaces vowels. '''
    return vowelize(text, p)


@make_pipe({
    'p' : Par(float, 0.4, 'Character swap probability'),
}, command=True)
@one_to_one
def consonize_pipe(text, p):
    ''' Randomly replaces consonants with funnier ones. '''
    return consonize(text, p)


@make_pipe({
    'p' : Par(float, 0.2, 'Character swap probability'),
}, command=True)
@one_to_one
def letterize_pipe(text, p):
    ''' Vowelizes and consonizes at the same time. '''
    return letterize(text, p)


@make_pipe({
    'p' : Par(float, 0.4, 'Character swap probability'),
}, command=True)
@one_to_one
def letterize2_pipe(text, p):
    ''' Letterizes, but smarter™. '''
    return letterize2(text, p)


@make_pipe({
    'to' : Par(Option(*converters, stringy=True), None, 'Which conversion should be used.'),
}, command=True)
@one_to_one
@util.format_doc(convs=', '.join(converters))
def convert_pipe(text, to):
    '''
    Character-by-character converts text into unicode abominations. 
    Options: {convs}
    '''
    return converters[to](text)



#####################################################
#                  Pipes : DATAMUSE                 #
#####################################################
_CATEGORY = 'DATAMUSE'
# TODO: 'n' parameter for all of these!!!!!!!!!!!!!

# Wrap the API in a LRU cache
datamuse_api = datamuse.Datamuse()
_datamuse = lru_cache()(datamuse_api.words)

@make_pipe({}, command=True)
@word_to_word
def rhyme_pipe(word):
    '''
    Replaces words with random (nearly) rhyming words.
    Thanks to datamuse.com
    '''
    res = _datamuse(rel_rhy=word, max=10) or _datamuse(rel_nry=word, max=10)
    # if not res:
    #     res = _datamuse(arhy=1, max=5, sl=word)
    if res:
        return random.choice(res)['word']
    else:
        return word


@make_pipe({}, command=True)
@word_to_word
def homophone_pipe(word):
    '''
    Replaces words with random homophones.
    Thanks to datamuse.com
    '''
    res = _datamuse(rel_hom=word, max=5)
    if res:
        return random.choice(res)['word']
    else:
        return word


@make_pipe({}, command=True)
@word_to_word
def synonym_pipe(word):
    '''
    Replaces words with random synonyms.
    Thanks to datamuse.com
    '''
    res = _datamuse(rel_syn=word, max=5)
    if res:
        return random.choice(res)['word']
    else:
        return word


@make_pipe({}, command=True)
@word_to_word
def antonym_pipe(word):
    '''
    Replaces words with random antonyms.
    Thanks to datamuse.com
    '''
    res = _datamuse(rel_ant=word, max=5)
    if res:
        return random.choice(res)['word']
    else:
        return word


@make_pipe({}, command=True)
@word_to_word
def part_pipe(word):
    '''
    Replaces words with something it is considered "a part of", inverse of comprises pipe.
    Thanks to datamuse.com
    '''
    res = _datamuse(rel_par=word, max=5)
    if res:
        return random.choice(res)['word']
    else:
        return word


@make_pipe({}, command=True)
@word_to_word
def comprises_pipe(word):
    '''
    Replaces words with things considered "its parts", inverse of "part" pipe.
    Thanks to datamuse.com
    '''
    res = _datamuse(rel_com=word, max=15)
    if res:
        return random.choice(res)['word']
    else:
        return word



#####################################################
#                  Pipes : LANGUAGE                 #
#####################################################
_CATEGORY = 'LANGUAGE'
translate_client = None

try:
    translate_client = translate.Client()
except Exception as e:
    print(e)
    print('[WARNING] Failed to initialise Google Cloud Translate client, translate features will be unavailable!')

@lru_cache(maxsize=100)
def translate_func(text, fro, to):
    response = translate_client.translate(text, source_language=fro, target_language=to, format_="text")
    return response['translatedText']

# Retreived once using translate_client.get_languages()
translate_languages = ['af', 'sq', 'am', 'ar', 'hy', 'az', 'eu', 'be', 'bn', 'bs', 'bg',
'ca', 'ceb', 'ny', 'zh-CN', 'zh-TW', 'co', 'hr', 'cs', 'da', 'nl', 'en', 'eo', 'et',
'tl', 'fi', 'fr', 'fy', 'gl', 'ka', 'de', 'el', 'gu', 'ht', 'ha', 'haw', 'iw', 'hi',
'hmn', 'hu', 'is', 'ig', 'id', 'ga', 'it', 'ja', 'jw', 'kn', 'kk', 'km', 'rw', 'ko',
'ku', 'ky', 'lo', 'la', 'lv', 'lt', 'lb', 'mk', 'mg', 'ms', 'ml', 'mt', 'mi', 'mr',
'mn', 'my', 'ne', 'no', 'or', 'ps', 'fa', 'pl', 'pt', 'pa', 'ro', 'ru', 'sm', 'gd',
'sr', 'st', 'sn', 'sd', 'si', 'sk', 'sl', 'so', 'es', 'su', 'sw', 'sv', 'tg', 'ta',
'tt', 'te', 'th', 'tr', 'tk', 'uk', 'ur', 'ug', 'uz', 'vi', 'cy', 'xh', 'yi', 'yo',
'zu', 'he', 'zh']

LANGUAGE = Option(*translate_languages, name='language', stringy=True)

@make_pipe({
    'from': Par(LANGUAGE + ['auto'], 'auto', 'The language code to translate from, "auto" to automatically detect the language.'),
    'to':   Par(LANGUAGE + ['random'], 'en', 'The language code to translate to, "random" for a random language.'),
}, command=True)
@one_to_one
def translate_pipe(text, to, **argc):
    '''
    Translates text using Google Translate.
    A list of languages can be browsed at https://cloud.google.com/translate/docs/languages
    '''
    if translate_client is None: return text
    if not text.strip(): return text

    fro = argc['from'] # Can't have a variable named 'from' because it's a keyword
    if fro == 'auto': fro = ''
    if to == 'random': to = random.choice(translate_languages)

    return translate_func(text, fro, to)


@make_pipe({})
@one_to_one
def detect_language_pipe(text):
    '''
    Detects language of a given text using Google Translate.
    Returns "und" if it cannot be determined.
    The list of languages can be browsed at https://cloud.google.com/translate/docs/languages
    '''
    if translate_client is None: return 'und'
    if text.strip() == '': return 'und'
    return translate_client.detect_language(text)['language']


@make_pipe({})
@one_to_many
def split_sentences_pipe(line):
    ''' Splits text into individual sentences using the Natural Language Toolkit (NLTK). '''
    return nltk.sent_tokenize(line)


@make_pipe({
    'file'   : Par(str, None, 'The file name'),
    'uniform': Par(parse_bool, False, 'Whether to pick pieces uniformly or based on their frequency'),
    'n'      : Par(int, 1, 'The amount of different phrases to generate')
}, command=True)
def pos_fill_pipe(phrases, file, uniform, n):
    '''
    Replaces POS tags of the form %TAG% with grammatically matching pieces from a given file.

    See >files for a list of uploaded files.
    List of POS tags: https://universaldependencies.org/docs/u/pos/
    See also the `pos` source.
    '''
    pos_buckets = uploads[file].get_pos_buckets()

    def repl(m):
        tag = m[1].upper()
        if tag in pos_buckets:
            if uniform:
                return random.choice( pos_buckets[tag].words )
            return random.choices( pos_buckets[tag].words, cum_weights=pos_buckets[tag].cum_weights, k=1 )[0]
        return m[0]

    return [ re.sub('%(\w+)%', repl, phrase) for phrase in phrases for _ in range(n) ]


POS_TAG = Option('ADJ', 'ADJ', 'ADP', 'PUNCT', 'ADV', 'AUX', 'SYM', 'INTJ', 'CONJ',
'X', 'NOUN', 'DET', 'PROPN', 'NUM', 'VERB', 'PART', 'PRON', 'SCONJ', 'SPACE', name='POS tag', stringy=True, prefer_upper=True)

@make_pipe({
    'include': Par(Multi(POS_TAG), None, 'Which POS tags to replace, separated by commas. If blank, uses the `exclude` list instead.', required=False),
    'exclude': Par(Multi(POS_TAG), 'PUNCT,SPACE,SYM,X', 'Which POS tags not to replace, separated by commas. Ignored if `include` is given.')
})
@one_to_one
def pos_unfill_pipe(text, include, exclude):
    '''
    Inverse of `pos_fill`: replaces parts of the given text with %TAG% formatted POS tags.
    
    List of POS tags: https://universaldependencies.org/docs/u/pos/
    See `pos_analyse` for a more complex alternative to this pipe.
    '''
    if spacy.LOADED_NLP is None: spacy.LOADED_NLP = spacy.load('en_core_web_sm')
    doc = spacy.LOADED_NLP(text)
    if include:
        return ''.join( f'%{t.pos_}%{t.whitespace_}' if t.pos_ in include else t.text_with_ws for t in doc )
    else:
        return ''.join( f'%{t.pos_}%{t.whitespace_}' if t.pos_ not in exclude else t.text_with_ws for t in doc )


@make_pipe({})
@one_to_many
def pos_analyse_pipe(text):
    '''
    Splits a piece of text into grammatically distinct pieces along with their POS tag.
    Each part of text turns into three output item: The original text, its POS tag, and its trailing whitespace.
    e.g. `pos_analyse > (3) format ("{}", {}, "{}")` nicely formats this pipe's output.
    
    List of POS tags: https://universaldependencies.org/docs/u/pos/
    '''
    if spacy.LOADED_NLP is None: spacy.LOADED_NLP = spacy.load('en_core_web_sm')
    doc = spacy.LOADED_NLP(text)
    # Return flattened tuples of (text, tag, whitespace)
    return [ x for t in doc for x in (t.text, t.pos_, t.whitespace_) ]



#####################################################
#                   Pipes : OPENAI                  #
#####################################################
_CATEGORY = 'OPENAI'

_is_openai_usable = False
def openai_setup():
    global openai, _is_openai_usable
    try: import openai
    except: return print('Could not import Python module `openai`, OpenAI-related features will not be available.')

    config = ConfigParser()
    config.read('config.ini')
    openai_api_key = config['OPENAI']['api_key']
    if not openai_api_key or openai_api_key == 'PutYourKeyHere':
        return print('OpenAI API key not set in config.ini, OpenAI-related features will not be available.')
    openai.api_key = openai_api_key
    _is_openai_usable = True

openai_setup()

@make_pipe({
    'n':                Par(int, 1, 'The amount of completions to generate.'),
    'max_tokens':       Par(int, 50, 'The limit of tokens to generate per completion, includes prompt.'),
    'temperature':      Par(float, .7, 'Value between 0 and 1 determining how creative/unhinged the generation is.'),
    'model':            Par(str, 'ada', 'The GPT model to use, generally: ada/babbage/curie/davinci.'),
    'presence_penalty': Par(float, 0, 'Value between -2 and 2, positive values discourage reusing already present words.'),
    'frequency_penalty':Par(float, 0, 'Value between -2 and 2, positive values discourage reusing frequently used words.'),
    'stop':             Par(str, None, 'String that, if generated, marks the immediate end of the completion.', required=False),
    'prepend_prompt':   Par(parse_bool, True, 'Whether to automatically prepend the input prompt to each completion.'),
    },
    may_use=lambda user: permissions.has(user.id, permissions.trusted),
    command=True,
)
@one_to_many
def gpt_complete_pipe(text, prepend_prompt, **kwargs):
    '''
    Generate a completion to the individual given inputs.
    Uses OpenAI GPT models.
    '''
    if not _is_openai_usable: return [text]

    response = openai.Completion.create(prompt=text, **kwargs)
    completions = [choice.text for choice in response.choices]
    if prepend_prompt:
        completions = [text + completion for completion in completions]
    return completions

@make_pipe({
    'instruction':  Par(str, None, 'The instruction that tells the model how to edit the prompt.'),
    'n':            Par(int, 1, 'The amount of completions to generate.'),
    'temperature':  Par(float, .7, 'Value between 0 and 1 determining how creative/unhinged the generation is.'),
    'model':        Par(str, 'text-davinci-edit-001', 'The GPT model to use, either text-davinci-edit-001 or code-davinci-edit-001.'),
    },
    may_use=lambda user: permissions.has(user.id, permissions.trusted)
)
@one_to_many
def gpt_edit_pipe(text, **kwargs):
    '''
    Edit the given input according to an instruction.    
    Uses OpenAI GPT models.
    '''
    if not _is_openai_usable: return [text]

    response = openai.Edit.create(input=text, **kwargs)
    return [choice.text for choice in response.choices]


#####################################################
#                  Pipes : ENCODING                 #
#####################################################
_CATEGORY = 'ENCODING'

@make_pipe({}, command=True)
@one_to_one
def demoji_pipe(text):
    '''Replaces emoji in text with their official names.'''
    out = []
    for c in text:
        if c in emoji.UNICODE_EMOJI:
            try:
                out.append( unicodedata2.name(c) + ' ' )
            except:
                out.append( '(UNKNOWN)' )
        else:
            out.append( c )
    return ''.join(out)


@make_pipe({}, command=True)
@one_to_one
def unicode_pipe(text):
    '''Replaces unicode characters with their official names.'''
    out = []
    for c in text:
        try: out.append(unicodedata2.name(c))
        except: out.append('UNKNOWN CHARACTER (%s)' % c)
    return ', '.join(out)


@make_pipe({
    'by': Par(int, 13, 'The number of places to rotate the letters by.'),
}, command=True)
@one_to_one
def rot_pipe(text, by):
    '''Applies a Caeserian cypher.'''
    if by % 26 == 0: return text
    out = []
    for c in text:
        o = ord(c)
        if 97 <= o <= 122: # lowercase
            c = chr( 97 + ( o - 97 + by ) % 26 )
        elif 65 <= o <= 90: # uppercase
            c = chr( 65 + ( o - 65 + by ) % 26 )
        out.append(c)
    return ''.join(out)


@make_pipe({})
@one_to_many
def ord_pipe(text):
    '''Turns each item into a sequence of integers representing each character.'''
    return [str(ord(s)) for s in text]


@make_pipe({})
@many_to_one
def chr_pipe(chars):
    '''Turns a sequence of integers representing characters into a single string.'''
    return [''.join(chr(int(c)) for c in chars)]


@make_pipe({})
@one_to_one
def url_encode_pipe(text):
    '''Turns a string into a URL (%) encoded string.'''
    return urllib.parse.quote(text)


@make_pipe({})
@one_to_one
def url_decode_pipe(text):
    '''Turns a URL (%) encoded string into its original string.'''
    return urllib.parse.unquote(text)


HASH_ALG = Option('python', 'blake2b', 'sha224', 'shake_128', 'sha3_384', 'md5', 'sha3_512', 'blake2s', 'sha256', 'sha1', 'sha3_224', 'shake_256', 'sha3_256', 'sha512', 'sha384', name='algorithm')

@make_pipe({
    'algorithm': Par(HASH_ALG, 'python', 'The hash algorithm to use.')
})
@one_to_one
def hash_pipe(text: str, algorithm: HASH_ALG) -> str:
    '''Applies a hash function.'''
    if algorithm == HASH_ALG.python:
        return str(hash(text))
    else:
        algorithm = hashlib.new(str(algorithm), usedforsecurity=False)
        algorithm.update(text.encode('utf-8'))
        return algorithm.hexdigest()
    return 



#####################################################
#                   Pipes : MATHS                   #
#####################################################
_CATEGORY = 'MATHS'

def smart_format(x: float):
    x = str(x)
    return re.sub('\.?0+$', '', x) if '.' in x else x

MATH_FUNCTIONS = {
    # Trigonometry
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'asin': math.asin,
    'acos': math.acos,
    'atan': math.atan,
    'atan2': math.atan2,
    # Exponentiation
    'exp': math.exp,
    'log': math.log,
    'log10': math.log10,
    'log2': math.log2,
    # This asshole
    'factorial': math.factorial,
    # Squares and roots
    'sqrt': math.sqrt,
    'hypot': math.hypot,
    # Reduction
    'floor': math.floor,
    'ceil': math.ceil,
    'round': round,
    'abs': abs,
    'sign': lambda x : -1 if x < 0 else 1 if x > 0 else 0,
    # Number theory
    'gcd': math.gcd,
    # Statistics
    'min': min,
    'max': max,
    'sum': sum,
    'avg': lambda *x : sum(x)/len(x)
}

SIMPLE_EVAL = SimpleEval(functions=MATH_FUNCTIONS, names={'e': math.e, 'pi': math.pi, 'inf': math.inf, 'True': True, 'False': False})

@make_pipe({
    'expr': Par(str, None, 'The mathematical expression to evaluate. Use {} notation to insert items into the expression.')
}, command=True)
@many_to_one
@util.format_doc(funcs=', '.join(c for c in MATH_FUNCTIONS))
def math_pipe(values, expr):
    '''
    Evaluates the mathematical expression given by the argument string.
    
    Available functions: {funcs}
    Available constants: True, False, e, pi and inf
    
    Note: For finding the min, max, sum or avg of an arbitrary number of arguments, use the respective min, max, sum and avg pipes.
    '''
    return [ smart_format(SIMPLE_EVAL.eval(expr)) ]


@make_pipe({})
@many_to_one
def max_pipe(values):
    ''' Produces the maximum value of the inputs evaluated as numbers. '''
    return [smart_format(max(float(x) for x in values))]


@make_pipe({})
@many_to_one
def min_pipe(values):
    ''' Produces the minimum value of the inputs evaluated as numbers. '''
    return [smart_format(min(float(x) for x in values))]


@make_pipe({})
@many_to_one
def sum_pipe(values):
    ''' Produces the sum of the inputs evaluated as numbers. '''
    return [smart_format(sum(float(x) for x in values))]


@make_pipe({})
@many_to_one
def avg_pipe(values):
    ''' Produces the mean average of the inputs evaluated as numbers. '''
    return [smart_format(sum(float(x) for x in values)/len(values))]