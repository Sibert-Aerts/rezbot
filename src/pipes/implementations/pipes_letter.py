import utils.util as util

from .pipes import make_pipe, one_to_one, set_category
from ..signature import Par, Option
from utils.texttools import vowelize, consonize, letterize, letterize2, converters


#####################################################
#                  Pipes : LETTER                   #
#####################################################
set_category('LETTER')

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