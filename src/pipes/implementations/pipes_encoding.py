import unicodedata2
import urllib.parse
import emoji
import hashlib

from .pipes import make_pipe, many_to_one, one_to_one, one_to_many, set_category
from ..signature import Par, Option

#####################################################
#                  Pipes : ENCODING                 #
#####################################################
set_category('ENCODING')

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
