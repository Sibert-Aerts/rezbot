import unicodedata2
import emoji
import utils.util as util

from .pipe_decorations import *

#####################################################
#                       Pipes                       #
#####################################################

@make_pipe( {
    'n'  : Sig(int, 2, 'Number of times repeated', lambda x: (x <= 100)),
    'lim': Sig(int, -1, 'Limit to total number of resulting rows, -1 for no limit.'),
})
def repeat_pipe(input, n, lim, how):
    '''Repeats each row a given number of times.'''
    # Isn't decorated as_map so both input and output are expected to be arrays.
    if lim == -1: lim = n*len(input)
    return [i for _ in range(n) for i in input][:lim]


@make_pipe({})
def delete_pipe(input):
    '''Deletes its input.'''
    return []


@make_pipe({})
def print_pipe(input):
    '''Adds the series of inputs to the final output, without affecting them.'''
    # This function is never actually called since 'print' is a special case
    # It's in here to add print to the >pipes command info list
    return input


@make_pipe({
    'on' : Sig(str, r'\s*\n+\s*', 'Pattern to split on (regex)'),
    'lim': Sig(int, 0, 'Maximum number of splits. (0 for no limit)'),
    'keep_whitespace': Sig(util.parse_bool, False, 'Whether or not to remove empty/whitespace items')
})
def split_pipe(inputs, on, lim, keep_whitespace):
    '''Split the input into multiple outputs.'''
    return [x for y in inputs for x in re.split(on, y, maxsplit=lim) if keep_whitespace or x.strip() != '']


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
    'to' : Sig(str, None, 'Which conversion should be used.', lambda x: x in converters),
}, command=True)
@as_map
@util.format_doc(convs=', '.join([c for c in converters]))
def convert_pipe(text, to):
    '''
    Convert text using a variety of settings.
    Valid conversions: {convs}
    '''
    return converters[to](text)


@make_pipe({}, command=True)
@as_map
def katakana_pipe(text):
    '''Converts English to Japanese phonetic characters using http://www.sljfaq.org/cgi/e2k.cgi.'''
    return katakana(text)


@make_pipe({}, command=True)
@as_map
def romaji_pipe(text):
    '''Converts Japanese kana to English phonetics using http://www.sljfaq.org/cgi/kana-romaji.cgi.'''
    return romaji(text)


@make_pipe({
    'min': Sig(int, 0, 'Upper limit on minimum distance (e.g. 1 to never get the same word).')
}, command=True)
@as_map
def min_dist_pipe(text, min):
    '''Replaces words with their nearest dictionary words.'''
    return ' '.join(min_dist(w, min) for w in text.split(' '))


@make_pipe({}, command=True)
@as_map
def demoji_pipe(text):
    '''Replaces emojis with their official description.'''
    return ' '.join([unicodedata2.name(c) if c in emoji.UNICODE_EMOJI else c for c in text])


@make_pipe({}, command=True)
@as_map
def unicode_pipe(text):
    '''Replaces unicode characters with their official description.'''
    return ', '.join([unicodedata2.name(c) for c in text])


@make_pipe({
    'f' : Sig(str, '{0}', 'The format string')
})
def format_pipe(input, f):
    '''Format one or more rows into a single row according to a format string.'''
    return [f.format(*input)]


@make_pipe({
    's' : Sig(str, '', 'The separator inserted between two items.')
})
def join_pipe(input, s):
    '''Join rows into a single row.'''
    return [s.join(input)]


randomLanguage = ['rand', 'random', '?']
@make_pipe({
    'from': Sig(str, 'auto', None, lambda x: x in translateLanguages + ['auto']),
    'to' : Sig(str, 'random', None, lambda x: x in translateLanguages + randomLanguage),
}, command=True)
@as_map
def translate_pipe(text, to, **argc):
    '''Translates the input using the internet.'''
    if to in randomLanguage:
        return translate(text, argc['from'], choose(translateLanguages))
    text = translate(text, argc['from'], to)
    return text