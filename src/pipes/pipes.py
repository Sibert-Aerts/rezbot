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
from utils.texttools import *

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
def repeat_pipe(input, times, max):
    '''Repeats each row a given number of times.'''
    # Isn't decorated as_map so both input and output are expected to be arrays.
    if max == -1:
        return input * times
    else:
        times = min(times, math.ceil(max/len(input))) # Limit how many unnecessary items the [:max] in the next line shaves off
        return (input*times)[:max]

delete_whats = ['a', 'e', 'w']
@make_pipe({
    'what': Sig(str, 'all', 'What to delete: all/empty/whitespace', lambda x: x[0].lower() in delete_whats)
})
def delete_pipe(input, what):
    '''Deletes all inputs, or specific types of input.'''
    what = what[0].lower()
    if what == 'a': # all
        return []
    if what == 'w': # whitespace (and empty too)
        return [x for x in input if x.trim() != '']
    if what == 'e': # empty
        return [x for x in input if x != '']


@make_pipe({
    'w' : Sig(int, -1, 'Width of the matrix.'),
    'h' : Sig(int, -1, 'Height of the matrix.'),
})
def tr_pipe(input, w, h):
    '''Transpose the input as if it were a matrix'''
    if w == h == -1:
        return input

    if w != -1:
        h = int(len(input) / w)
    else:
        w = int(len(input) / h)

    if w == 0 or h == 0:
        return input

    # I figured this line out by trial-and-error :)
    return [input[i*w + j] for j in range(w) for i in range(h)]


@make_pipe({})
def shuffle_pipe(input):
    '''Randomly shuffles grouped input values.'''
    # IMPORTANT NOTE: `input` is passed BY REFERENCE, so we are NOT supposed to mess with it!
    out = input[:]
    random.shuffle(out)
    return out


@make_pipe({})
def reverse_pipe(input):
    '''Reverses the order of grouped input values.'''
    return input[::-1]


@make_pipe({})
def count_pipe(input):
    '''Counts the number of input values it receives.'''
    return [str(len(input))]


#####################################################
#                  Pipes : OUTPUT                   #
#####################################################
_CATEGORY = 'OUTPUT'

@make_pipe({'name' : Sig(str, None, 'The variable name')})
def set_pipe(input, name):
    '''Temporarily stores the input as a variable with the given name.'''
    SourceResources.var_dict[name] = input
    return input


@make_pipe({})
def print_pipe(input):
    '''Appends the input to the output message, without affecting it.'''
    # This function is never actually called since 'print' is a special case
    # It's in here to add print to the >pipes command info list
    return input


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
def split_pipe(inputs, on, lim, keep_whitespace, keep_empty):
    '''Split the input into multiple outputs.'''
    return [x for y in inputs for x in re.split(on, y, maxsplit=lim) if x.strip() != '' or (keep_whitespace and x != '') or (keep_empty and x == '')]


pad_modes = ['l', 'c', 'r']

@make_pipe({
    'where': Sig(str, 'right', 'Which side to pad on: left/center/right', lambda x: x[0].lower() in pad_modes),
    'width': Sig(int, 0, 'The minimum width to pad to.'),
    'fill' : Sig(str, ' ', 'The character used to pad out the string.'),
})
@as_map
def pad_pipe(text, where, width, fill):
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
def wrap_pipe(inputs, mode, width):
    '''Wrap the input to a certain width.'''
    mode = mode[0].lower()
    if mode == 'd':
        return [text[i:i+width] for text in inputs for i in range(0, len(text), width)]
    if mode == 's':
        return [wrapped for text in inputs for wrapped in textwrap.wrap(text, width)]


@make_pipe({
    'from': Sig(str, None, 'Pattern to replace (regex)'),
    'to' : Sig(str, None, 'Replacement string'),
})
@as_map
def sub_pipe(text, to, **argc):
    '''Substitutes patterns in the input.'''
    return re.sub(argc['from'], to, text)


@make_pipe({
    'p': Sig(str, None, 'Case pattern to obey'),
})
@as_map
def case_pipe(text, p):
    '''Converts the input case to match the given pattern case.'''
    return ''.join([matchCase(text[i], p[i%len(p)]) for i in range(len(text))])


@make_pipe({
    'f' : Sig(str, None, 'The format string, for syntax info: https://pyformat.info/')
})
def format_pipe(input, f):
    '''Format one or more rows into a single row according to a format string.'''
    return [f.format(*input)]


@make_pipe({
    's' : Sig(str, '', 'The separator inserted between two items.')
})
def join_pipe(input, s):
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
def vowelize_pipe(text, p):
    '''Randomly replaces vowels.'''
    return vowelize(text, p)


@make_pipe({
    'p' : Sig(float, 0.4, 'Character swap probability'),
}, command=True)
@as_map
def consonize_pipe(text, p):
    '''Randomly replaces consonants with funnier ones.'''
    return consonize(text, p)


@make_pipe({
    'p' : Sig(float, 0.2, 'Character swap probability'),
}, command=True)
@as_map
def letterize_pipe(text, p):
    '''Both vowelizes and consonizes.'''
    return letterize(text, p)


@make_pipe({
    'p' : Sig(float, 0.4, 'Character swap probability'),
}, command=True)
@as_map
def letterize2_pipe(text, p):
    '''Letterize, but smarter™.'''
    return letterize2(text, p)


@make_pipe({
    'to' : Sig(str, None, 'Which conversion should be used.', lambda x: x in converters),
}, command=True)
@as_map
@util.format_doc(convs=', '.join([c for c in converters]))
def convert_pipe(text, to):
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
    'min': Sig(int, 0, 'Upper limit on minimum distance (e.g. 1 to never get the same word).')
}, command=True)
@as_map
def min_dist_pipe(text, min):
    '''Replaces words with their nearest dictionary words.'''
    return ' '.join(min_dist(w, min) for w in text.split(' '))


@make_pipe({}, command=True)
@word_map
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
@word_map
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
@word_map
def synonym_pipe(word):
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
@word_map
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
@word_map
def comprises_pipe(word):
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

translate_languages = '''af ar az be bg bn ca cs cy da de el en eo es et eu fa fi fr ga gl
gu hi hr ht hu id is it iw ja ka kn ko la lt lv mk ms mt nl no pl pt ro ru sk sl sq sr sv
sw ta te th tl tr uk ur vi yi zh-CN zh-TW'''.split()
random_language = ['rand', 'random', '?']


@make_pipe({
    'from': Sig(str, 'auto', None, lambda x: x in translate_languages + ['auto']),
    'to' : Sig(str, 'random', None, lambda x: x in translate_languages + random_language),
}, command=True)
@as_map
@util.format_doc(langs=' '.join([c for c in translate_languages]))
def translate_pipe(text, to, **argc):
    '''
    Translates the input using the internet.
    
    Options: {langs}
    '''
    if _translate is None: return text
    fro = argc['from']
    if fro == 'auto': fro = ''
    if to in random_language: to = choose(translate_languages)
    if text.strip() == '': return text
    result = _translate(text, source_language=fro, target_language=to)
    return result['translatedText']


#####################################################
#                  Pipes : ENCODING                 #
#####################################################
_CATEGORY = 'ENCODING'

@make_pipe({}, command=True)
@as_map
def demoji_pipe(text):
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
def unicode_pipe(text):
    '''Replaces unicode characters with their official names.'''
    out = []
    for c in text:
        try: out.append(unicodedata2.name(c))
        except: out.append('UNKNOWN CHARACTER (%s)' % c)
    return ', '.join(out)
