from .pipe_decorations import *

#####################################################
#                       Pipes                       #
#####################################################

@make_pipe( {'n': Sig(int, 2, 'Number of times repeated', lambda x: (x <= 10)),
}, expandable=False )
def repeat_pipe(input, n):
    '''Repeats the input, branching the resulting output.'''
    # Isn't decorated as_map so both input and output are expected to be arrays.
    return [i for i in input for _ in range(n)]


@make_pipe({}, expandable=False )
def print_pipe(input):
    '''Adds the series of inputs to the final output, without affecting them.'''
    # This function is never actually called since 'print' is a special case
    # It's in here to add print to the >pipes command info list
    return input

@make_pipe({
    'fro': Sig(str, None, 'Pattern to replace (regex)'),
    'to' : Sig(str, None, 'Replacement string'),
})
@as_map
def sub_pipe(text, fro, to):
    '''Substitutes patterns in the input.'''
    return re.sub(fro, to, text)

@make_pipe({
    'p': Sig(str, None, 'Case pattern to obey'),
})
@as_map
def case_pipe(text, p):
    '''Converts the input case to match the given pattern case.'''
    return ''.join([matchCase(text[i], p[i%len(p)]) for i in range(len(text))])


@make_pipe({
    'p' : Sig(float, 0.4, 'Character swap probability'),
    'dp': Sig(float, 0.0, 'Increase in p per row'),
})
@as_map
def vowelize_pipe(text, p, dp, mapIndex=0):
    '''Randomly replaces vowels.'''
    return vowelize(text, p + mapIndex * dp)


@make_pipe({
    'p' : Sig(float, 0.4, 'Character swap probability'),
    'dp': Sig(float, 0.0, 'Increase in p per row'),
})
@as_map
def consonize_pipe(text, p, dp, mapIndex=0):
    '''Randomly replaces consonants with funnier ones.'''
    return consonize(text, p + mapIndex * dp)


@make_pipe({
    'p' : Sig(float, 0.2, 'Character swap probability'),
    'dp': Sig(float, 0.0, 'Increase in p per row'),
})
@as_map
def letterize_pipe(text, p, dp, mapIndex=0):
    '''Both vowelizes and consonizes.'''
    return letterize(text, p + mapIndex * dp)


@make_pipe({
    'to' : Sig(str, None, 'Which conversion should be used, choose from: ' + ', '.join([t for t in converters]), lambda x: x in converters),
})
@as_map
def convert_pipe(text, to):
    '''Converts characters to different characters.'''
    return converters[to](text)


@make_pipe({})
@as_map
def katakana_pipe(text):
    '''Converts text to japanese phonetic characters using http://www.sljfaq.org/cgi/e2k.cgi.'''
    return katakana(text)


@make_pipe({
    'min': Sig(int, 0, 'Upper limit on minimum distance (e.g. 1 to never get the same word).'),})
@as_map
def min_dist_pipe(text, min):
    '''Replaces words with their nearest dictionary words.'''
    return ' '.join(min_dist(w, min) for w in text.split(' '))



randomLanguage = ['rand', 'random', '?']
@make_pipe({
    'fro': Sig(str, 'auto', None, lambda x: x in translateLanguages + ['auto']),
    'to' : Sig(str, 'random', None, lambda x: x in translateLanguages + randomLanguage),
})
@as_map
def translate_pipe(text, fro, to):
    '''Translates the input using the internet.'''
    if to in randomLanguage:
        return translate(text, fro, choose(translateLanguages))
    text = translate(text, fro, to)
    return text