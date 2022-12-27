import re
from functools import lru_cache

from .sources import source_from_func, set_category
from ..signature import Par, Option, Multi

from utils.rand import choose, sample, choose_slice 
from utils.texttools import *
import resource.wikipedia as wikipedia

import nltk


#####################################################
#               Sources : WIKIPEDIA                 #
#####################################################
set_category('WIKI')

# Cache the most recent Wikipedia pages based on (name, language)
@lru_cache(maxsize=20)
def _wikipedia_page(page, language):
    wikipedia.set_lang(language)
    return wikipedia.page(page)
    
WIKIPEDIA_WHAT = Option('title', 'url', 'summary', 'content', 'images', 'videos', 'audio', 'links')
_img_re = re.compile(r'(?i)(png|jpe?g|gif|webp)$')
_banned_imgs = ['https://upload.wikimedia.org/wikipedia/commons/7/74/Red_Pencil_Icon.png', 'https://upload.wikimedia.org/wikipedia/commons/f/f9/Double-dagger-14-plain.png']
_vid_re = re.compile(r'(?i)(webm|gif|mp4|ogv)$')
_aud_re = re.compile(r'(?i)(mp3|ogg|wav)$')
_svg_re = re.compile(r'(?i)(svg)$')

def _wikipedia_get_what(page, what, n):
    if what == WIKIPEDIA_WHAT.title:
        return [page.title]
    elif what == WIKIPEDIA_WHAT.url:
        return [page.url]
    elif what == WIKIPEDIA_WHAT.summary:
        if not hasattr(page, 'summary_sentences'):
            sentences = nltk.sent_tokenize(page.summary)
            sentences = [ re.sub(r'\n[\n\s]*', ' ', s) for s in sentences ]
            page.summary_sentences = sentences
        return choose_slice( page.summary_sentences, n )
    elif what == WIKIPEDIA_WHAT.content:
        if not hasattr(page, 'content_sentences'):
            # Get rid of section titles before parsing sentences
            content = re.sub(r'^==+ .+ ==+\s*$', '', page.content, flags=re.M)
            sentences = nltk.sent_tokenize(content)
            sentences = [ re.sub(r'\n[\n\s]*', ' ', s) for s in sentences ]
            page.content_sentences = sentences
        return choose_slice( page.content_sentences, n )
    elif what == WIKIPEDIA_WHAT.images:
        return sample( [img for img in page.images if _img_re.search(img) and img not in _banned_imgs], n )
    elif what == WIKIPEDIA_WHAT.videos:
        return sample( list(filter(_vid_re.search, page.images)), n )
    elif what == WIKIPEDIA_WHAT.audio:
        return sample( list(filter(_aud_re.search, page.images)), n )
    elif what == WIKIPEDIA_WHAT.links:
        return sample( page.links, n )

@source_from_func({
    'language': Par(str, 'en', 'Which language Wikipedia you want to use. (list: https://meta.wikimedia.org/wiki/List_of_Wikipedias)'),
    'lines': Par(int, 1, 'The number of (what) you want ,for summary/content this means number of sentences.'),
    'what': Par(Multi(WIKIPEDIA_WHAT), 'summary', 'Which part(s) of the pages you want: ' + '/'.join(WIKIPEDIA_WHAT)),
    'n' : Par(int, 1, 'The number of random pages to fetch')
})
async def wikipedia_random_source(what, language, lines, n):
    '''
    Fetches information from one or more random Wikipedia pages.
    '''
    pages = []
    for _ in range(n):
        while True:
            ## Despite the module/API's insistence, wikipedia.random() may return an ambiguous page title
            ## and EVEN when you then pick a random disambiguated one, it may still be ambiguous (or invalid) anyway???
            ## So JUST KEEP freaking trying, it only fails like 1% of the time anyway
            page = wikipedia.random()
            try:
                pages.append( _wikipedia_page(page, language) )
                break
            except wikipedia.DisambiguationError as e:
                try:
                    page = choose(e.options)
                    pages.append( _wikipedia_page(page, language) )
                    break
                except:
                    pass
            except:
                pass
    
    return [ s for page in pages for wh in what for s in _wikipedia_get_what(page, wh, lines) ]


@source_from_func({
    'page': Par(str, None, 'The page you want information from. (For a random page, use wikipedia_random.)', lambda s: s),
    'language': Par(str, 'en', 'Which language Wikipedia you want to use. (list: https://meta.wikimedia.org/wiki/List_of_Wikipedias)'),
    'what': Par(Multi(WIKIPEDIA_WHAT), 'summary', 'Which part(s) of the pages you want: ' + '/'.join(WIKIPEDIA_WHAT)),
    'n'   : Par(int, 1, 'The number of (what) you want, for summary/content this means number of sentences.')
}, depletable=True)
async def wikipedia_source(page, what, language, n):
    '''
    Fetches various information from a Wikipedia page.
    
    Donate to wikimedia: https://donate.wikimedia.org/
    '''
    page = _wikipedia_page(page, language)
    return [ s for wh in what for s in _wikipedia_get_what(page, wh, n) ]


@source_from_func({
    'query': Par(str, None, 'The search query')
})
async def wikipedia_search_source(query):
    '''Returns the top Wikipedia search results for the query.'''
    return wikipedia.search(query)
