import unicodedata2
import emoji
import utils.util as util
import random
import math
import textwrap
import re
from functools import wraps, lru_cache

from datamuse import datamuse
datamuse_api = datamuse.Datamuse()
from google.cloud import translate

from .signature import Sig
from .pipe import Pipe, Pipes

from .sources import SourceResources
from utils.texttools import vowelize, consonize, letterize, letterize2, converters, min_dist, case_pattern
from resource.upload import uploads

#######################################################
#                     Decorations                     #
#######################################################

def as_map(func):
    '''
    Decorate a function to accept an array of first arguments:

    f: (x, *args) -> y      becomes     f': ([x], args) -> [y]
    e.g.
    pow(3, 2) -> 9          becomes     pow'([3, 4, 5], 2) -> [9, 16, 25]
    '''
    @wraps(func)
    def _as_map(input, *args, **kwargs):
        return [func(i, *args, **kwargs) for i in input]
    return _as_map

_word_splitter = re.compile(r'([\w\'-]+)') # groups together words made out of letters or ' or -

def word_map(func):
    '''
    Decorator allowing a pipe to treat input on a word-by-word basis, with symbols etc. removed.
    '''
    @wraps(func)
    def _word_map(line, *args, **kwargs):
        split = re.split(_word_splitter, line)
        for i in range(1, len(split), 2):
            split[i] = func(split[i], *args, **kwargs)
        return ''.join(split)
    return as_map(_word_map)

pipes = Pipes()
pipes.command_pipes = []
_CATEGORY = 'NONE'

def make_pipe(signature, command=False):
    '''Makes a Pipe out of a function.'''
    def _make_pipe(func):
        global pipes, _CATEGORY
        pipe = Pipe(signature, func, _CATEGORY)
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
    'times': Sig(int, None, 'Number of times repeated'),
    'max'  : Sig(int, -1, 'Maximum number of outputs produced, -1 for unlimited.')
})
def repeat(input, times, max):
    '''Repeats each row a given number of times.'''
    # Isn't decorated as_map so both input and output are expected to be arrays.
    if max == -1:
        return input * times
    else:
        times = min(times, math.ceil(max/len(input))) # Limit how many unnecessary items the [:max] in the next line shaves off
        return (input*times)[:max]


delete_whats = ['a', 'e', 'w']
@make_pipe({ 'what': Sig(str, 'all', 'What to delete: all/empty/whitespace', lambda x: x[0].lower() in delete_whats) })
def delete(input, what):
    '''Deletes all inputs, or specific types of input.'''
    what = what[0].lower()
    if what == 'a': # all
        return []
    if what == 'w': # whitespace (and empty too)
        return [x for x in input if x.trim() != '']
    if what == 'e': # empty
        return [x for x in input if x != '']


@make_pipe({})
def sort(input):
    '''Sorts the input values lexicographically.'''
    # IMPORTANT: `input` is passed BY REFERENCE, so we are NOT supposed to mess with it!
    out = input[:]
    out.sort()
    return out


@make_pipe({})
def shuffle(input):
    '''Randomly shuffles input values.'''
    # IMPORTANT NOTE: `input` is passed BY REFERENCE, so we are NOT supposed to mess with it!
    out = input[:]
    random.shuffle(out)
    return out


@make_pipe({ 'amount' : Sig(int, 1, 'The amount of values to choose.', lambda x: x>=0) })
def choose(input, amount):
    '''Chooses random values with replacement (i.e. may return repeated values).'''
    return random.choices(input, k=amount)


@make_pipe({ 'amount' : Sig(int, 1, 'The amount of values to sample.', lambda x: x>=0) })
def sample(input, amount):
    '''Chooses random values without replacement. Never produces more values than the number it receives.'''
    return random.sample(input, min(len(input), amount))


@make_pipe({})
def unique(input):
    '''Returns the first unique occurence of each value.'''
    return [*{*input}]


@make_pipe({})
def reverse(input):
    '''Reverses the order of the input values.'''
    return input[::-1]


@make_pipe({})
def count(input):
    '''Counts the number of input values it receives.'''
    return [str(len(input))]


#####################################################
#                  Pipes : STRING                   #
#####################################################
_CATEGORY = 'STRING'

@make_pipe({
    'on' : Sig(str, r'\s*\n+\s*', 'Pattern to split on (regex)'),
    'lim': Sig(int, 0, 'Maximum number of splits. (0 for no limit)'),
    'keep_whitespace': Sig(util.parse_bool, False, 'Whether or not to remove whitespace items'),
    'keep_empty': Sig(util.parse_bool, False, 'Whether or not to remove empty items')
})
def split(inputs, on, lim, keep_whitespace, keep_empty):
    '''Split the input into multiple outputs.'''
    return [x for y in inputs for x in re.split(on, y, maxsplit=lim) if x.strip() != '' or (keep_whitespace and x != '') or (keep_empty and x == '')]


pad_modes = ['l', 'c', 'r']

@make_pipe({
    'where': Sig(str, 'right', 'Which side to pad on: left/center/right', lambda x: x[0].lower() in pad_modes),
    'width': Sig(int, 0, 'The minimum width to pad to.'),
    'fill' : Sig(str, ' ', 'The character used to pad out the string.'),
})
@as_map
def pad(text, where, width, fill):
    '''Pad the input to a certain width.'''
    where = where[0].lower()
    if where == 'l':
        return text.rjust(width, fill)
    if where == 'r':
        return text.ljust(width, fill)
    if where == 'c':
        return text.center(width, fill)


wrap_modes = ['d', 's']

@make_pipe({
    'mode' : Sig(str, 'smart', 'How to wrap: Dumb (char-by-char) or smart (on spaces).', lambda x: x[0].lower() in wrap_modes),
    'width': Sig(int, 40, 'The minimum width to pad to.')
})
def wrap(inputs, mode, width):
    '''Wrap the input to a certain width.'''
    mode = mode[0].lower()
    if mode == 'd':
        return [text[i:i+width] for text in inputs for i in range(0, len(text), width)]
    if mode == 's':
        return [wrapped for text in inputs for wrapped in textwrap.wrap(text, width)]


@make_pipe({})
@as_map
def strip(value):
    '''Strips whitespace from the starts and ends of each input.'''
    return value.strip()


@make_pipe({
    'from': Sig(str, None, 'Pattern to replace (regex)'),
    'to' : Sig(str, None, 'Replacement string'),
})
@as_map
def sub(text, to, **argc):
    '''Substitutes patterns in the input.'''
    return re.sub(argc['from'], to, text)


@make_pipe({
    'pattern': Sig(str, None, 'Case pattern to obey'),
})
def case(text, pattern):
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
    return case_pattern(pattern, *text)


@make_pipe({
    'f' : Sig(str, None, 'The format string, for syntax info: https://pyformat.info/')
})
def format(input, f):
    '''Format one or more rows into a single row according to a format string.'''
    return [f.format(*input)]


@make_pipe({
    's' : Sig(str, '', 'The separator inserted between two items.')
})
def join(input, s):
    '''Joins rows into a single row, separated by the given separator.'''
    return [s.join(input)]


#####################################################
#                  Pipes : LETTER                   #
#####################################################
_CATEGORY = 'LETTER'

@make_pipe({
    'p' : Sig(float, 0.4, 'Character swap probability'),
}, command=True)
@as_map
def vowelize(text, p):
    '''Randomly replaces vowels.'''
    return vowelize(text, p)


@make_pipe({
    'p' : Sig(float, 0.4, 'Character swap probability'),
}, command=True)
@as_map
def consonize(text, p):
    '''Randomly replaces consonants with funnier ones.'''
    return consonize(text, p)


@make_pipe({
    'p' : Sig(float, 0.2, 'Character swap probability'),
}, command=True)
@as_map
def letterize(text, p):
    '''Both vowelizes and consonizes.'''
    return letterize(text, p)


@make_pipe({
    'p' : Sig(float, 0.4, 'Character swap probability'),
}, command=True)
@as_map
def letterize2(text, p):
    '''Letterize, but smarter™.'''
    return letterize2(text, p)


@make_pipe({
    'to' : Sig(str, None, 'Which conversion should be used.', lambda x: x in converters),
}, command=True)
@as_map
@util.format_doc(convs=', '.join([c for c in converters]))
def convert(text, to):
    '''\
    Convert text using a variety of settings.

    Valid conversions: {convs}
    '''
    return converters[to](text)


#####################################################
#                  Pipes : LANGUAGE                 #
#####################################################
_CATEGORY = 'LANGUAGE'

# Wrap the API in a LRU cache
_datamuse = lru_cache()(datamuse_api.words)

@make_pipe({
    'min': Sig(int, 0, 'Upper limit on minimum distance (e.g. 1 to never get the same word).'),
    'file': Sig(str, 'words.txt', 'The uploaded file to be matched from.')
}, command=True)
@as_map
def nearest(text, min, file):
    '''Replaces text with the nearest item (by edit distance) in a given file.'''
    # TODO? MORE FILE LOGIC EQUIVALENT TO {TXT} SOURCE
    if file not in uploads:
        raise KeyError('No file "%s" loaded! Check >files for a list of files.' % file)
    file = uploads[file]
    return min_dist(text, min, file.get())


@make_pipe({}, command=True)
@word_map
def rhyme(word):
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
@word_map
def homophone(word):
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
@word_map
def synonym(word):
    '''
    Replaces words with random antonyms.
    Thanks to datamuse.com
    '''
    res = _datamuse(rel_syn=word, max=5)
    if res:
        return random.choice(res)['word']
    else:
        return word


@make_pipe({}, command=True)
@word_map
def antonym(word):
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
@word_map
def part(word):
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
@word_map
def comprises(word):
    '''
    Replaces words with things considered "its parts", inverse of "part" pipe.
    Thanks to datamuse.com
    '''
    res = _datamuse(rel_com=word, max=10)
    if res:
        return random.choice(res)['word']
    else:
        return word


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
translate_languages = '''af sq am ar hy az eu be bn bs bg ca ceb ny zh zh-TW co
hr cs da nl en eo et tl fi fr fy gl ka de el gu ht ha haw iw hi hmn hu is ig id
ga it ja jw kn kk km ko ku ky lo la lv lt lb mk mg ms ml mt mi mr mn my ne no ps
fa pl pt pa ro ru sm gd sr st sn sd si sk sl so es su sw sv tg ta te th tr uk ur
uz vi cy xh yi yo zu'''.split()
random_language = ['rand', 'random', '?']


@make_pipe({
    'from': Sig(str, 'auto', 'The language to translate from, "auto" to automatically detect the language.', lambda x: x in translate_languages or x == 'auto'),
    'to' : Sig(str, 'en', 'The language to translate to, "random" for a random language.', lambda x: x in translate_languages or x in random_language),
}, command=True)
@as_map
@util.format_doc(langs=' '.join(c for c in translate_languages))
def translate(text, to, **argc):
    '''
    Translates the input using the Google Cloud Translate API.
    The list of languages can be browsed at https://cloud.google.com/translate/docs/languages
    '''
    if _translate is None: return text
    if text.strip() == '': return text

    fro = argc['from'] # because `from` is a keyword
    if fro == 'auto': fro = ''
    if to in random_language: to = choose(translate_languages)

    result = _translate(text, source_language=fro, target_language=to)

    return result['translatedText']


#####################################################
#                  Pipes : ENCODING                 #
#####################################################
_CATEGORY = 'ENCODING'

@make_pipe({}, command=True)
@as_map
def demoji(text):
    '''Replaces emoji in text with their official names.'''
    out = ''
    for c in text:
        if c in emoji.UNICODE_EMOJI:
            try:
                out += unicodedata2.name(c) + ' '
            except:
                out += 'UNKNOWN '
        else:
            out += c
    return out


@make_pipe({}, command=True)
@as_map
def unicode(text):
    '''Replaces unicode characters with their official names.'''
    out = []
    for c in text:
        try: out.append(unicodedata2.name(c))
        except: out.append('UNKNOWN CHARACTER (%s)' % c)
    return ', '.join(out)


@make_pipe({
    'by': Sig(int, 13, 'The number of places to rotate the letters by.', lambda x: x in translate_languages or x == 'auto'),
}, command=True)
@as_map
def rot(text, by):
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
