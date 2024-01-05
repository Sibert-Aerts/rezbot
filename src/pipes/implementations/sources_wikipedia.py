import re
from functools import lru_cache

from .sources import source_from_func, set_category
from pipes.core.signature import Par, Option, Multi

from utils.rand import choose, sample, ordered_sample, choose_slice
from utils.texttools import *

from mediawikiapi import MediaWikiAPI, Config as MediaWikiConfig, Language as MediaWikiLanguage, PageError, WikipediaPage
import nltk


########################################################
# Wrappers/Utilities/Overrides of MediaWikiAPI package #
########################################################

class DisambiguationError(Exception):
    def __init__(self, page):
        self.page = page
    def __str__(self):
        return f'"{self.page.title}" may refer to:\n' + '\n'.join(self.page.disambiguate_pages)


WIKIPEDIA_LANGUAGES = ['aa', 'ab', 'abs', 'ace', 'acm', 'ady', 'ady-cyrl', 'aeb', 'aeb-arab',
'aeb-latn', 'af', 'ak', 'aln', 'als', 'alt', 'am', 'ami', 'an', 'ang', 'ann', 'anp', 'ar', 'arc',
'arn', 'arq', 'ary', 'arz', 'as', 'ase', 'ast', 'atj', 'av', 'avk', 'awa', 'ay', 'az', 'azb', 'ba',
'ban', 'ban-bali', 'bar', 'bat-smg', 'bbc', 'bbc-latn', 'bcc', 'bci', 'bcl', 'be', 'be-tarask',
'be-x-old', 'bew', 'bg', 'bgn', 'bh', 'bho', 'bi', 'bjn', 'blk', 'bm', 'bn', 'bo', 'bpy', 'bqi',
'br', 'brh', 'bs', 'btm', 'bto', 'bug', 'bxr', 'ca', 'cbk-zam', 'cdo', 'ce', 'ceb', 'ch', 'cho',
'chr', 'chy', 'ckb', 'co', 'cps', 'cr', 'crh', 'crh-cyrl', 'crh-latn', 'crh-ro', 'cs', 'csb', 'cu',
'cv', 'cy', 'da', 'dag', 'de', 'de-at', 'de-ch', 'de-formal', 'dga', 'din', 'diq', 'dsb', 'dtp',
'dty', 'dv', 'dz', 'ee', 'egl', 'el', 'eml', 'en', 'en-ca', 'en-gb', 'eo', 'es', 'es-419',
'es-formal', 'et', 'eu', 'ext', 'fa', 'fat', 'ff', 'fi', 'fit', 'fiu-vro', 'fj', 'fo', 'fon', 'fr',
'frc', 'frp', 'frr', 'fur', 'fy', 'ga', 'gaa', 'gag', 'gan', 'gan-hans', 'gan-hant', 'gcr', 'gd',
'gl', 'gld', 'glk', 'gn', 'gom', 'gom-deva', 'gom-latn', 'gor', 'got', 'gpe', 'grc', 'gsw', 'gu',
'guc', 'gur', 'guw', 'gv', 'ha', 'hak', 'haw', 'he', 'hi', 'hif', 'hif-latn', 'hil', 'hno', 'ho',
'hr', 'hrx', 'hsb', 'hsn', 'ht', 'hu', 'hu-formal', 'hy', 'hyw', 'hz', 'ia', 'id', 'ie', 'ig',
'igl', 'ii', 'ik', 'ike-cans', 'ike-latn', 'ilo', 'inh', 'io', 'is', 'it', 'iu', 'ja', 'jam', 'jbo',
'jut', 'jv', 'ka', 'kaa', 'kab', 'kbd', 'kbd-cyrl', 'kbp', 'kcg', 'kea', 'kg', 'khw', 'ki', 'kiu',
'kj', 'kjh', 'kjp', 'kk', 'kk-arab', 'kk-cn', 'kk-cyrl', 'kk-kz', 'kk-latn', 'kk-tr', 'kl', 'km',
'kn', 'ko', 'ko-kp', 'koi', 'kr', 'krc', 'kri', 'krj', 'krl', 'ks', 'ks-arab', 'ks-deva', 'ksh',
'ksw', 'ku', 'ku-arab', 'ku-latn', 'kum', 'kus', 'kv', 'kw', 'ky', 'la', 'lad', 'lb', 'lbe', 'lez',
'lfn', 'lg', 'li', 'lij', 'liv', 'lki', 'lld', 'lmo', 'ln', 'lo', 'loz', 'lrc', 'lt', 'ltg', 'lus',
'luz', 'lv', 'lzh', 'lzz', 'mad', 'mag', 'mai', 'map-bms', 'mdf', 'mg', 'mh', 'mhr', 'mi', 'min',
'mk', 'ml', 'mn', 'mni', 'mnw', 'mo', 'mos', 'mr', 'mrh', 'mrj', 'ms', 'ms-arab', 'mt', 'mus',
'mwl', 'my', 'myv', 'mzn', 'na', 'nah', 'nan', 'nap', 'nb', 'nds', 'nds-nl', 'ne', 'new', 'ng',
'nia', 'niu', 'nl', 'nl-informal', 'nmz', 'nn', 'no', 'nod', 'nog', 'nov', 'nqo', 'nrm', 'nso',
'nv', 'ny', 'nyn', 'nys', 'oc', 'ojb', 'olo', 'om', 'or', 'os', 'pa', 'pag', 'pam', 'pap', 'pcd',
'pcm', 'pdc', 'pdt', 'pfl', 'pi', 'pih', 'pl', 'pms', 'pnb', 'pnt', 'prg', 'ps', 'pt', 'pt-br',
'pwn', 'qu', 'qug', 'rgn', 'rif', 'rki', 'rm', 'rmc', 'rmy', 'rn', 'ro', 'roa-rup', 'roa-tara',
'rsk', 'ru', 'rue', 'rup', 'ruq', 'ruq-cyrl', 'ruq-latn', 'rw', 'ryu', 'sa', 'sah', 'sat', 'sc',
'scn', 'sco', 'sd', 'sdc', 'sdh', 'se', 'se-fi', 'se-no', 'se-se', 'sei', 'ses', 'sg', 'sgs', 'sh',
'sh-cyrl', 'sh-latn', 'shi', 'shi-latn', 'shi-tfng', 'shn', 'shy', 'shy-latn', 'si', 'simple',
'sjd', 'sje', 'sk', 'skr', 'skr-arab', 'sl', 'sli', 'sm', 'sma', 'smn', 'sms', 'sn', 'so', 'sq',
'sr', 'sr-ec', 'sr-el', 'srn', 'sro', 'ss', 'st', 'stq', 'sty', 'su', 'sv', 'sw', 'syl', 'szl',
'szy', 'ta', 'tay', 'tcy', 'tdd', 'te', 'tet', 'tg', 'tg-cyrl', 'tg-latn', 'th', 'ti', 'tk', 'tl',
'tly', 'tly-cyrl', 'tn', 'to', 'tok', 'tpi', 'tr', 'tru', 'trv', 'ts', 'tt', 'tt-cyrl', 'tt-latn',
'tum', 'tw', 'ty', 'tyv', 'tzm', 'udm', 'ug', 'ug-arab', 'ug-latn', 'uk', 'ur', 'uz', 'uz-cyrl',
'uz-latn', 've', 'vec', 'vep', 'vi', 'vls', 'vmf', 'vmw', 'vo', 'vot', 'vro', 'wa', 'wal', 'war',
'wls', 'wo', 'wuu', 'wuu-hans', 'wuu-hant', 'xal', 'xh', 'xmf', 'xsy', 'yi', 'yo', 'yrl', 'yue',
'yue-hans', 'yue-hant', 'za', 'zea', 'zgh', 'zh', 'zh-classical', 'zh-cn', 'zh-hans', 'zh-hant',
'zh-hk', 'zh-min-nan', 'zh-mo', 'zh-my', 'zh-sg', 'zh-tw', 'zh-yue', 'zu']

# Assign this ahead of time to save a (somehow) very slow fetch of all of wikipedia's languages.
MediaWikiLanguage.predefined_languages = {l: l for l in WIKIPEDIA_LANGUAGES}


# Keep a different MediaWikiAPI entry per wikipedia language to account for a caching bug
WIKIPEDIAS: dict[str, MediaWikiAPI] = {}
USER_AGENT = 'Rezbot Discord Bot (https://github.com/sibert-aerts/Rezbot/)'

def get_wikipedia(lang: str):
    if lang not in WIKIPEDIAS:
        WIKIPEDIAS[lang] = MediaWikiAPI(MediaWikiConfig(language=lang, user_agent=USER_AGENT, timeout=15))
    return WIKIPEDIAS[lang]


# Cache the most recent Wikipedia pages based on (name, language)
@lru_cache(maxsize=20)
def get_wikipedia_page(page, language):
    # Either find an exact page title match (results[0]) or Wikipedia's top suggestion
    results, suggestion = get_wikipedia(language).search(page, results=1, suggestion=True)
    if not results and not suggestion:
        raise PageError(title=page)

    # Fetch the page
    page = get_wikipedia(language).page(results[0] if results else suggestion, auto_suggest=False)

    # Disambiguation pages raise an error
    if page.disambiguate_pages:
        raise DisambiguationError(page)
    return page


#####################################################
#               Sources : WIKIPEDIA                 #
#####################################################
set_category('WIKI')


WIKIPEDIA_WHAT = Option('title', 'url', 'summary', 'content', 'images', 'videos', 'audio', 'links', 'infobox')
_img_re = re.compile(r'(?i)(png|jpe?g|gif|webp)$')
_banned_imgs = [
    'https://upload.wikimedia.org/wikipedia/commons/7/74/Red_Pencil_Icon.png',
    'https://upload.wikimedia.org/wikipedia/commons/f/f9/Double-dagger-14-plain.png'
]
_vid_re = re.compile(r'(?i)(webm|gif|mp4|ogv)$')
_aud_re = re.compile(r'(?i)(mp3|ogg|wav)$')
_svg_re = re.compile(r'(?i)(svg)$')

def _wikipedia_get_what(page: WikipediaPage, what, n):
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
    elif what == WIKIPEDIA_WHAT.infobox:
        info_tuples = list(page.infobox.items())
        selected = ordered_sample(info_tuples, n)
        return [x for tuple in selected for x in tuple]


@source_from_func({
    'what': Par(Multi(WIKIPEDIA_WHAT), 'summary', 'Which part(s) of the pages you want: ' + '/'.join(WIKIPEDIA_WHAT)),
    'language': Par(str, 'en', 'Which language Wikipedia you want to use. (list: https://meta.wikimedia.org/wiki/List_of_Wikipedias)'),
    'lines': Par(int, 1, 'The number of (what) you want ,for summary/content this means number of sentences.'),
    'n' : Par(int, 1, 'The number of random pages to fetch')
})
async def wikipedia_random_source(ctx, what, language, lines, n):
    '''
    Fetches information from one or more random Wikipedia pages.
    '''
    pages = []
    for _ in range(n):
        while True:
            ## Despite the module/API's insistence, wikipedia.random() may return an ambiguous page title
            ## and EVEN when you then pick a random disambiguated one, it may still be ambiguous (or invalid) anyway???
            ## So JUST KEEP freaking trying, it only fails like 1% of the time anyway
            page = get_wikipedia(language).random()
            try:
                pages.append(get_wikipedia_page(page, language))
                break
            except DisambiguationError as e:
                try:
                    page = choose(e.page.disambiguate_pages)
                    pages.append(get_wikipedia_page(page, language))
                    break
                except:
                    pass
            except:
                pass

    return [ s for page in pages for wh in what for s in _wikipedia_get_what(page, wh, lines) ]


@source_from_func({
    'page': Par(str, None, 'The page you want information from. (For a random page, use wikipedia_random.)', lambda s: s),
    'what': Par(Multi(WIKIPEDIA_WHAT), 'summary', 'Which part(s) of the pages you want: ' + '/'.join(WIKIPEDIA_WHAT)),
    'language': Par(str, 'en', 'Which language Wikipedia you want to use. (list: https://meta.wikimedia.org/wiki/List_of_Wikipedias)'),
    'n'   : Par(int, 1, 'The number of (what) you want, for summary/content this means number of sentences.')
}, depletable=True)
async def wikipedia_source(ctx, page, what, language, n):
    '''
    Fetches various information from a Wikipedia page.

    Donate to wikimedia: https://donate.wikimedia.org/
    '''
    page = get_wikipedia_page(page, language)
    return [ s for wh in what for s in _wikipedia_get_what(page, wh, n) ]


@source_from_func({
    'query': Par(str, None, 'The search query'),
    'language': Par(str, 'en', 'Which language Wikipedia you want to use. (list: https://meta.wikimedia.org/wiki/List_of_Wikipedias)'),
})
async def wikipedia_search_source(ctx, query, language):
    '''Returns the top Wikipedia search results for the query.'''
    return get_wikipedia(language).search(query)
