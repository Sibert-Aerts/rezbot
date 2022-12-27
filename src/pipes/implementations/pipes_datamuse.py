import random
from functools import lru_cache

from datamuse import datamuse

from .pipes import pipe_from_func, word_to_word, set_category


#####################################################
#                  Pipes : DATAMUSE                 #
#####################################################
set_category('DATAMUSE')

# TODO: 'n' parameter for all of these!!!!!!!!!!!!!

# Wrap the API in a LRU cache
datamuse_api = datamuse.Datamuse()
_datamuse = lru_cache()(datamuse_api.words)

@pipe_from_func(command=True)
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


@pipe_from_func(command=True)
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


@pipe_from_func(command=True)
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


@pipe_from_func(command=True)
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


@pipe_from_func(command=True)
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


@pipe_from_func(command=True)
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
