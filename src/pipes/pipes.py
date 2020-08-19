import unicodedata2
import emoji
import utils.util as util
import random
import math
import textwrap
import re
from functools import wraps, lru_cache

from datamuse import datamuse
from google.cloud import translate
import nltk
from simpleeval import SimpleEval
import spacy
spacy.LOADED_NLP = None

from .signature import Par, Signature, Option, Multi
from .pipe import Pipe, Pipes
from utils.texttools import vowelize, consonize, letterize, letterize2, converters, min_dist, case_pattern
from utils.rand import choose_slice
from utils.util import parse_bool
from resource.upload import uploads

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

def make_pipe(signature, command=False):
    '''Makes a Pipe out of a function.'''
    def _make_pipe(func):
        global pipes, _CATEGORY
        pipe = Pipe(Signature(signature), func, _CATEGORY)
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
    # Isn't decorated as_map so both input and output are expected to be arrays.
    if max == -1:
        return input * times
    else:
        times = min(times, math.ceil(max/len(input))) # Limit how many unnecessary items the [:max] in the next line shaves off
        return (input*times)[:max]

REMOVE_WHAT = Option('all', 'empty', 'whitespace')

@make_pipe({ 
    'what': Par(REMOVE_WHAT, REMOVE_WHAT.all, 'What to filter: all/empty/whitespace') 
})
def remove_pipe(input, what):
    '''
    Removes all items (or specific types of items) from the flow.

    all: Removes every item
    whitespace: Removes items that only consist of whitespace (including empty ones)
    empty: Only removes items equal to the empty string ("")
    '''
    if what == REMOVE_WHAT.all:
        return []
    if what == REMOVE_WHAT.whitespace:
        return [x for x in input if x.isspace()]
    if what == REMOVE_WHAT.empty:
        return [x for x in input if x != '']


@make_pipe({})
def sort_pipe(input):
    '''Sorts the input values lexicographically.'''
    # IMPORTANT: `input` is passed BY REFERENCE, so we are NOT supposed to mess with it!
    out = input[:]
    out.sort()
    return out


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
    'number' : Par(int, 1, 'The number of values to sample.', lambda x: x>=0) 
})
def sample_pipe(input, number):
    '''
    Chooses random values without replacement.
    Never produces more values than the number it receives.
    '''
    return random.sample(input, min(len(input), number))


@make_pipe({
    'length' : Par(int, None, 'The desired slice length.', lambda x: x>=0),
    'cyclical': Par(parse_bool, False, 'Whether or not the slice is allowed to "loop back" to cover both some first elements and last elements. ' +
            'i.e. If False, elements at the start and end of the input have lower chance of being selected, if True all elements have an equal chance.')
})
def choose_slice_pipe(input, length, cyclical):
    '''Chooses a random contiguous sequence of inputs.'''
    return choose_slice(input, length, cyclical=cyclical)


@make_pipe({
    'count' : Par(parse_bool, False, 'Whether each unique item should be followed by a count of how many there were of it.')
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
def reverse_pipe(input):
    '''Reverses the order of input items.'''
    return input[::-1]


@make_pipe({})
@many_to_one
def count_pipe(input):
    '''Counts the number of input items.'''
    return [str(len(input))]


#####################################################
#                  Pipes : STRING                   #
#####################################################
_CATEGORY = 'STRING'

# So the name correctly shows up as "regex"
def regex(*args, **kwargs): return re.compile(*args, **kwargs)

@make_pipe({
    'on' : Par(regex, None, 'Pattern to split on'),
    'lim': Par(int, 0, 'Maximum number of splits. (0 for no limit)')
})
@one_to_many
def split_pipe(text, on, lim):
    '''Splits the input into multiple outputs according to a pattern.'''
    return re.split(on, text, maxsplit=lim)


@make_pipe({
    'pattern': Par(regex, None, 'The pattern to find')
})
@one_to_many
def find_all_pipe(text, pattern):
    '''
    Extracts all pattern matches from the input.
    Only groups (parentheses) are returned, if none are given, the entire match is returned instead.
    '''
    matches = pattern.findall(text)
    # matches is either a List[str] or a List[Tuple[str]] depending on the regex
    if matches and isinstance(matches[0], tuple):
        return [match for tup in matches for match in tup]
    return matches


@make_pipe({
    'from': Par(regex, None, 'Pattern to replace (regex)'),
    'to' : Par(str, None, 'Replacement string'),
})
@one_to_one
def sub_pipe(text, to, **argc):
    '''
    Substitutes patterns in text.
    Use \\1, \\2, ... in the `to` string to insert matched groups (parentheses) of the regex pattern.
    '''
    return re.sub(argc['from'], to, text, re.S)

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


@make_pipe({})
@one_to_one
def strip_pipe(value):
    ''' Strips whitespace from the start and end of each input text. '''
    return value.strip()


@make_pipe({
    'pattern': Par(str, None, 'Case pattern to obey'),
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


@make_pipe({
    'f' : Par(str, None, 'The format string. Items of the form {0}, {1} etc. are replaced with the respective item at that index.')
})
@many_to_one
def format_pipe(input, f):
    ''' Formats input text according to a format template. '''
    ## Due to arguments automatically being formatted as described, this pipe does nothing but return `f` as its only output.
    return [f]

@make_pipe({
    's' : Par(str, '', 'The separator inserted between two items.')
})
@many_to_one
def join_pipe(input, s):
    ''' Joins inputs into a single item, separated by the given separator. '''
    return [s.join(input)]

TABLE_ALIGN = Option('l', 'c', 'r', name='alignment')

@make_pipe({
    'columns': Par(str, None, 'The names of the different columns separated by commas, or an integer giving the number of columns.'),
    'alignments': Par(Multi(TABLE_ALIGN), Multi(TABLE_ALIGN)('l'), 'How the columns should be aligned: l/c/r separated by commas.'),
    'sep': Par(str, ' │ ', 'The column separator'),
    'code_block': Par(parse_bool, True, 'If the table should be wrapped in a Discord code block.')
})
@many_to_one
def table_pipe(input, columns, alignments, sep, code_block):
    ''' Formats data as a table. '''
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

    rows = [ input[i:i+colCount] for i in range(0, len(input), colCount) ]
    # Pad out the last row with empty strings
    rows[-1] += [''] * (colCount - len(rows[-1]))

    colWidths = [ max(len(row[i]) for row in rows) for i in range(colCount) ]
    if colNames:
        colWidths = [ max(w, len(name)) for (w, name) in zip(colWidths, colNames) ]

    def pad(text, width, where, what=' '):
        if where == TABLE_ALIGN.l: return text.ljust(width, what)
        if where == TABLE_ALIGN.c: return text.center(width, what)
        if where == TABLE_ALIGN.r: return text.rjust(width, what)

    rows = [ ' %s ' % sep.join([ pad(row[i], colWidths[i], alignments[i]) for i in range(colCount) ]) for row in rows ]
    if colNames:
        rows = [ '_%s_' % sep.replace(' ', '_').join([ pad(colNames[i], colWidths[i], alignments[i], '_') for i in range(colCount) ]) ] + rows

    return [ ('```\n%s\n```' if code_block else '%s') % '\n'.join(rows) ]

    

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

@make_pipe({})
@one_to_many
def split_sentences_pipe(input):
    ''' Splits text into individual sentences using the Natural Language Toolkit (NLTK). '''
    return nltk.sent_tokenize(line)


@make_pipe({
    'file': Par(str, None, 'The name of the file to be matched from. >files for a list of files'),
    'min':  Par(int, 0, 'Upper limit on minimum distance (e.g. 1 to never get the same word).')
}, command=True)
@one_to_one
def nearest_pipe(text, min, file):
    ''' Replaces each item with the nearest item (by edit distance) from the given file. '''
    file = uploads[file]
    return min_dist(text, min, file.get())


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

try:
    translate_client = translate.Client()
    # Wrap the API call in a LRU cache!
    _translate = lambda *a, **k : translate_client.translate(*a, **k, format_='text')
    _translate = lru_cache()(_translate)
except Exception as e:
    print(e)
    print('Failed to load google cloud translate services, translate will be unavailable!')
    _translate = None

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
    Translates text using the Google Translate.
    A list of languages can be browsed at https://cloud.google.com/translate/docs/languages
    '''
    if _translate is None: return text
    if text.isspace(): return text

    fro = argc['from'] # Can't have a variable named 'from' because it's a keyword
    if fro == 'auto': fro = ''
    if to == 'random': to = random.choice(translate_languages)

    result = _translate(text, source_language=fro, target_language=to)

    return result['translatedText']


@make_pipe({})
@one_to_one
def detect_language_pipe(text):
    '''
    Detects language of a given text using Google Translate.
    Returns "und" if it cannot be determined.
    The list of languages can be browsed at https://cloud.google.com/translate/docs/languages
    '''
    if _translate is None: return 'und'
    if text.strip() == '': return 'und'
    return translate_client.detect_language(text)['language']
    

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
    'exclude': Par(Multi(POS_TAG), Multi(POS_TAG)('PUNCT,SPACE,SYM,X'), 'Which POS tags not to replace, separated by commas. Ignored if `include` is given.')
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
    
    Note: For finding the min, max, sum or avg of an arbitrary number of arguments, use the respective min, max, sum and avg pipes
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