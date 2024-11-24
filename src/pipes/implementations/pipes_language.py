import random
import re
from decimal import InvalidOperation
from functools import lru_cache

from google.cloud import translate_v2 as translate
import nltk
import spacy
spacy.LOADED_NLP = None
import num2words

from .pipes import pipe_from_func, one_to_one, one_to_many, set_category, with_signature
from pipes.core.signature import Par, Option, ListOf
from utils.util import parse_bool, format_doc
from utils.google_translate_languages import LANGUAGES_BY_CODE_LOWER, ALL_LANGUAGE_KEYS, get_language
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

@lru_cache(100)
def translate_func(text, fro, to):
    response = translate_client.translate(text, source_language=fro, target_language=to, format_="text")
    return response['translatedText']


LANGUAGE = Option(*ALL_LANGUAGE_KEYS, name='language', stringy=True)

@pipe_from_func({
    'from': Par(LANGUAGE + ['auto'], 'auto', 'The language to translate from, "auto" to automatically detect the language.'),
    'to':   Par(LANGUAGE + ['random'], 'en', 'The language to translate to, "random" for a random language.'),
}, command=True)
@one_to_one
def translate_pipe(text, to, **kwargs):
    '''
    Translates text using Google Translate.
    A list of languages can be browsed at https://cloud.google.com/translate/docs/languages
    or https://github.com/Sibert-Aerts/rezbot/blob/master/src/utils/google_translate_languages.py
    '''
    # Trivial cases
    if translate_client is None: return text
    if not text.strip(): return text

    # kwarg 'from' is not allowed since it's a keyword
    fro = kwargs['from']

    # Ensure fro and to are language codes
    if fro == 'auto':
        fro = ''
    else:
        fro = get_language(fro)['language']
    if to == 'random':
        to = random.choice(list(LANGUAGES_BY_CODE_LOWER))
    else:
        to = get_language(to)['language']

    return translate_func(text, fro, to)


@pipe_from_func
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


@pipe_from_func
@one_to_many
def split_sentences_pipe(line):
    ''' Splits text into individual sentences using the Natural Language Toolkit (NLTK). '''
    return nltk.sent_tokenize(line)


NUM2WORDS_LANG = Option(*num2words.CONVERTER_CLASSES, name='Language', stringy=True)
NUM2WORDS_TYPE = Option(*num2words.CONVERTES_TYPES, name='Type', stringy=True)

@pipe_from_func(aliases=['num2word'], command=True)
@with_signature(
    lang = Par(NUM2WORDS_LANG, 'en', 'The language'),
    type = Par(NUM2WORDS_TYPE, 'cardinal', '/'.join(NUM2WORDS_TYPE)),
)
@one_to_one
@format_doc(langs=', '.join(NUM2WORDS_LANG))
def num2words_pipe(item, lang, type):
    '''
    Turns numbers into words.

    Languages to choose from: {langs}
    '''
    # Correct for these being normalized to lowercase (nl_be) but num2words wants (nl_BE)
    if '_' in lang:
        lang = lang[:3] + lang[3:].upper()
    try:
        return num2words.num2words(item, lang=lang, to=type)
    except InvalidOperation:
        raise ValueError(f'Cannot interpret value "{item}" as a decimal.')


@pipe_from_func({
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

@pipe_from_func({
    'include': Par(ListOf(POS_TAG), None, 'Which POS tags to replace, separated by commas. If blank, uses the `exclude` list instead.', required=False),
    'exclude': Par(ListOf(POS_TAG), 'PUNCT,SPACE,SYM,X', 'Which POS tags not to replace, separated by commas. Ignored if `include` is given.')
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


@pipe_from_func
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

