import re
import random

from .sources import make_source, set_category
from ..signature import Par

import utils.util as util
from utils.texttools import *
from resource.upload import uploads

# So the typename correctly shows up as "regex"
def regex(*args, **kwargs): return re.compile(*args, **kwargs)

#####################################################
#                  Sources : FILE                   #
#####################################################
set_category('FILE')
# NOTE: the category can't be called "FILE" if I rename "txt" to "file", also the "file" source can't be a command then!

def bool_or_none(val):
    if val is None or val == 'None': return None
    return(util.parse_bool(val))

@make_source({
    'file' : Par(str, None, 'The file name, "random" for a random file'),
    'n'    : Par(int, 1, 'The number of lines'),
    'sequential': Par(bool_or_none, None, 'If the multiple lines should be sequential as opposed to random, "None" for file-dependent.', required=False),
    'sentences' : Par(bool_or_none, None, 'If the file should be split on sentences as opposed to on dividing characters, "None" for file-dependent.', required=False),
    'query'     : Par(str, '', 'Optional search query'),
    'pattern'   : Par(regex, None, 'Optional search regex', required=False),
}, command=True, depletable=True)
async def txt_source(file, n, sequential, sentences, query, pattern):
    '''Lines from an uploaded text file. Check >files for a list of files.'''
    if file == 'random':
        file = random.choice(list(uploads.files.keys()))
    file = uploads[file]

    if sequential is None: sequential = file.info.sequential
    if sentences is None: sentences = file.info.sentences

    if sequential:
        return file.get_sequential(n, sentences, query=query, regex=pattern)
    else:
        return file.get_random(n, sentences, query=query, regex=pattern)


@make_source({
    'file'  : Par(str, None, 'The file name'),
    'n'     : Par(int, 1, 'The amount of lines'),
    'length': Par(int, 0, 'The maximum length of the generated sentence (0 for unlimited)'),
    'start' : Par(str, None, 'One or two starting words to continue a sentence from (NOTE: EXTREMELY FINNICKY)', required=False)
}, command=True)
async def markov_source(file, n, length, start):
    '''Randomly generated markov chains based on an uploaded file. Check >files for a list of files.'''
    file = uploads[file]
    return file.get_markov_lines(n, length, start)


@make_source({
    'file'   : Par(str, None, 'The file name'),
    'tag'    : Par(str, None, 'The POS tag'),
    'uniform': Par(util.parse_bool, False, 'Whether to pick pieces uniformly or based on their frequency'),
    'n'      : Par(int, 1, 'The amount of pieces')
}, depletable=True, plural='pos')
async def pos_source(file, tag, uniform, n):
    '''
        Returns a Piece Of Sentence from a given text file that match a given grammatical POS tag.

        See >files for a list of uploaded files.
        List of POS tags: https://universaldependencies.org/docs/u/pos/
        See also the `POS_fill` pipe.
    '''
    file = uploads[file]
    pos_buckets = file.get_pos_buckets()
    
    tag = tag.upper()
    if tag in pos_buckets:
        # Slightly inconsistent behaviour: "ALL" gives all unique words, but the normal case may give repeats
        # Also, "ALL" returns each word once, regardless of the word's weight ?
        if n == -1:
            return list(pos_buckets[tag].words)
        if uniform:
            return random.choices( pos_buckets[tag].words, k=n )
        return random.choices( pos_buckets[tag].words, cum_weights=pos_buckets[tag].cum_weights, k=n)
    else: # Sad fallback: just return the tag n times
        return [tag] * n if n > 0 else []
