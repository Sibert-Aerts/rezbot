import random
import re
from functools import lru_cache

from google.cloud import translate_v2 as translate
import nltk
import spacy
spacy.LOADED_NLP = None

from .pipes import make_pipe, one_to_one, one_to_many, set_category
from ..signature import Par, Option, Multi
from utils.util import parse_bool
from resource.upload import uploads


#####################################################
#                  Pipes : LANGUAGE                 #
#####################################################
set_category('LANGUAGE')
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

