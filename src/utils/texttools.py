from Levenshtein import distance
import re
import utils.util as util
from .rand import *

###
### Smelly old file where I implemented a bunch of text tools and toys...
### A number of classic Pipes are implemented here
###

abc = 'abcdefghijklmnopqrstuvwxyz'
vowels = 'aeiouy'
consonants = 'bcdfghjklmnpqrstvwxz'
digs = '0123456789'
ABCabc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

# words
allWords = open('resource/words.txt', encoding='utf-8').read().split()
# remove proper nouns
allWords = [w for w in allWords if not w[:1].isupper() and not w[-2:] == "'s"]


def block_format(s):
    ''' Format text into a code block. '''
    # put a zero-width space in there to prevent it from breaking our block
    return '```\n{0}\n```'.format(s.replace('```','`­``'))

# ======== Chunking/blocking text for outputting as Discord messages

def line_chunk_list(list, maxlength=100):
    ''' Turn a list of strings into a list of lines of ", "-separated strings. '''
    out = []
    grab = ''
    for name in list:
        if not grab: grab = name; continue
        if len(grab) + 2 + len(name) > maxlength:
            out.append(grab + ',')
            grab = name
        else:
            grab += ', ' + name
    if grab:
        out.append(grab)

    return out


def block_chunk_lines(lines):
    ''' Turn a list of lines into a list of <2000 character code blocks safe to send over discord.'''
    blocks = []
    block = []
    block_length = 0

    for line in lines:
        # The new line would be too long to fit in the block (anymore).
        if block_length + len(line) > 1900:
            # Move on to the next block.
            if block:
                blocks.append(block)
                block = []
                block_length = 0
            # Special case: The single line is too big to even fit in a block at all, spread it over multiple.
            if len(line) > 1900:
                chunks = chunk_text(line, 1900)
                for chunk in chunks[:-1]:
                    blocks.append([chunk])
                line = chunks[-1]

        block.append(line)
        block_length += len(line) + 2
    
    blocks.append(block)    
    return [ block_format('\n'.join(block)) for block in blocks ]


def split_once_within_length(text: str, splitter: str, max_length: int):
    '''
    Greedily splits `text` on the last occurence of `max_length` which starts at index `<= max_length`.
    If there is no such occurence, returns `('', text)`.

    Example:
    >>> split_once_within_length('AA-BB-CC-DD', '-', 8)
    ('AA-BB-CC', 'DD')
    '''
    # Test if it is possible at all:
    i = text.find(splitter)
    if i > max_length:
        return '', text

    text_lines = text.split(splitter)
    chunk_lines = []
    chunk_length = 0
    while True:
        line = text_lines[0]
        if chunk_length + len(splitter) + len(line) > max_length:
            break
        text_lines.pop(0)
        chunk_lines.append(line)
        chunk_length += len(splitter) + len(line)

    return splitter.join(chunk_lines), splitter.join(text_lines)


def chunk_text(text: str, chunk_size=2000):
    ''' Smartly splits a string into a list of strings under a given size. '''
    chunks = []

    while True:
        # Best case: Entire (remaining) text fits.
        if len(text) <= chunk_size:
            chunks.append(text)
            break

        # OK case: Try to split on newlines to squeeze within chunk_size.
        chunk, text = split_once_within_length(text, '\n', chunk_size)
        if chunk:
            chunks.append(chunk)
            continue

        # Bad case: Try to split on spaces to squeeze within chunk_size.
        chunk, text = split_once_within_length(text, ' ', chunk_size)
        if chunk:
            chunks.append(chunk)
            continue

        # Worst case: No spaces or newlines within chunk_size; just slice off chunk_size chars and continue.
        chunks.append(text[:chunk_size])
        text = text[chunk_size:]

    return chunks


def matchCase(char, case):
    return char.upper() if case.isupper() else char.lower()


def pSub(fro, to):
    def func(str, p):
        return re.sub(fro, lambda c: c.group(0) if not chance(p) else matchCase(choose(to), c.group(0)), str)
    return func


vowelize = pSub('(?i)[aeiou]', 'aeiou')
consonize = pSub('(?i)[bcdfgjklmnpqrstvwxz]', 'bbbddnnmmlgh')

def letterize(str, p):
    return vowelize(consonize(str, p), p*2/3)

letterize2Dict = {
    'a': 'eiou',
    'e': 'aiou',
    'i': 'aaeeoouuy',
    'o': 'aeu',
    'u': 'aaaeeeoooy',
    'y': 'iu',

    'b': 'p',
    'p': 'b',

    'c': 'gk',
    'g': 'kkkhhhj',
    'h': 'gggj',
    'j': 'hj',
    'k': 'cccgggq',
    'q': 'cgk',

    'm': 'n',
    'n': 'm',

    'd': 't',
    't': 'd',

    'f': 'v',
    'v': 'fw',
    'w': 'vvvw',

    'l': 'llrw', # These two maps to themselves since they're kinda special...
    'r': 'lrrgw', # They also map to chars that don't map back to them... they're special....

    's': 'xzzzzzz',
    'x': 'sz',
    'z': 'ssssssx',
}

def letterize2(s, p):
    out = ''
    pv = p * 2/3
    for c in s:
        cl = c.lower()
        if cl in vowels:
            if chance(pv):
                out += matchCase(random.choice(letterize2Dict[cl]), c)
            else:
                out += c
        elif cl in consonants:
            if chance(p):
                out += matchCase(random.choice(letterize2Dict[cl]), c)
            else:
                out += c
        else:
            out += c
    return out


class AlphaSub:
    '''Class for making reusable alphabetic substitutions'''
    def __init__(self, fro, to, ignoreCase=False, reverse=False):
        self.ignoreCase = ignoreCase
        self.reverse = reverse

        w = len(to) / len(fro)
        if w != int(w): raise ValueError('MISMATCHED ALPHABET LENGTHS: ' + to)
        w = int(w)
        # Split the "to" string into strings of length w
        to = [ to[i*w:i*w+w] for i in range(len(fro)) ]

        self.charmap = { c:t for (c,t) in zip(fro, to) }

    def __call__(self, text):
        '''Performs the alphabetic substitution on the given string'''
        charmap = self.charmap
        if not self.ignoreCase:
            chars = [charmap[t] if t in charmap else t for t in text]
        else:
            chars = [charmap[t.lower()] if t.lower() in charmap else t for t in text]
        return ''.join(chars if not self.reverse else reversed(chars))


# A couple of fun alphabetic substitutions
smallcaps  = AlphaSub(abc, 'ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ', ignoreCase=True)
squared_d  = AlphaSub(digs, '0⃣1⃣2⃣3⃣4⃣5⃣6⃣7⃣8⃣9⃣')
squared_l  = AlphaSub(abc, '🇦­🇧­🇨­🇩­🇪­🇫­🇬­🇭­🇮­🇯­🇰­🇱­🇲­🇳­🇴­🇵­🇶­🇷­🇸­🇹­🇺­🇻­🇼­🇽­🇾­🇿­', ignoreCase=True) # Warning: There's an &shy; between each of these!
squared_l2 = AlphaSub(abc, '🇦🇧🇨🇩🇪🇫🇬🇭🇮🇯🇰🇱🇲🇳🇴🇵🇶🇷🇸🇹🇺🇻🇼🇽🇾🇿', ignoreCase=True) # There are no &shy;'s between these ones!
squared    = lambda x: squared_l(squared_d(x))
squared2   = lambda x: squared_l2(squared_d(x))
circled    = AlphaSub(ABCabc + digs, 'ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ' '0①②③④⑤⑥⑦⑧⑨')
flip       = AlphaSub(ABCabc, '∀qƆpƎℲפHIſʞ˥WNOԀQɹS┴∩ΛMX⅄Zɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz', reverse=True)
mirror     = AlphaSub(ABCabc, 'AdↃbƎꟻGHIJK⅃MᴎOꟼpᴙꙄTUVWXYZAdↄbɘꟻgHijklmᴎoqpᴙꙅTUvwxYz', reverse=True)
fullwidth  = AlphaSub(ABCabc + digs + '!\"#$%&\'()*+,-./:;<=>?@[\]^_`{|}~ ', 'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ' '０１２３４５６７８９' '！＂＃＄％＆＇（）＊＋，－．／：；＜＝＞？＠［＼］＾＿｀｛｜｝～　')
script     = AlphaSub(ABCabc, '𝒜ℬ𝒞𝒟ℰℱ𝒢ℋℐ𝒥𝒦ℒℳ𝒩𝒪𝒫𝒬ℛ𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵𝒶𝒷𝒸𝒹ℯ𝒻ℊ𝒽𝒾𝒿𝓀𝓁𝓂𝓃ℴ𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏')
monospace  = AlphaSub(ABCabc + digs, '𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣' '𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿')
fraktur    = AlphaSub(ABCabc, '𝔄𝔅ℭ𝔇𝔈𝔉𝔊ℌℑ𝔍𝔎𝔏𝔐𝔑𝔒𝔓𝔔ℜ𝔖𝔗𝔘𝔙𝔚𝔛𝔜ℨ𝔞𝔟𝔠𝔡𝔢𝔣𝔤𝔥𝔦𝔧𝔨𝔩𝔪𝔫𝔬𝔭𝔮𝔯𝔰𝔱𝔲𝔳𝔴𝔵𝔶𝔷')
struck     = AlphaSub(ABCabc + digs, '𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫' '𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡')
sans       = AlphaSub(ABCabc + digs, '𝖠𝖡𝖢𝖣𝖤𝖥𝖦𝖧𝖨𝖩𝖪𝖫𝖬𝖭𝖮𝖯𝖰𝖱𝖲𝖳𝖴𝖵𝖶𝖷𝖸𝖹𝖺𝖻𝖼𝖽𝖾𝖿𝗀𝗁𝗂𝗃𝗄𝗅𝗆𝗇𝗈𝗉𝗊𝗋𝗌𝗍𝗎𝗏𝗐𝗑𝗒𝗓' '𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫') # these look normal but they aren't
superscript= AlphaSub(ABCabc + digs + '()', 'ᴬᴮᶜᴰᴱᶠᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᑫᴿˢᵀᵁⱽᵂˣʸᶻᵃᵇᶜᵈᵉᶠᵍʰᶦʲᵏᶫᵐᶰᵒᵖᑫʳˢᵗᵘᵛʷˣʸᶻ' '⁰¹²³⁴⁵⁶⁷⁸⁹' '⁽⁾')
bold       = AlphaSub(ABCabc, '𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳')

converters = {
    'smallcaps' : smallcaps,
    'flip' : flip,
    'mirror' : mirror,
    'squared' : squared,
    'true_squared' : squared2,
    'circled' : circled,
    'fullwidth' : fullwidth,
    'script' : script,
    'monospace' : monospace,
    'fraktur' : fraktur,
    'struck' : struck,
    'sans' : sans,
    'superscript' : superscript,
    'bold': bold,
    'none': lambda x: x
}


# Edit distance
def ed(x, y):
    return distance(x.lower(), y.lower())


def min_dist(w, min_min=0, corpus=None):
    if corpus is None: corpus = allWords
    w = w.lower()
    key = lambda x: distance(x.lower(), w)
    return choose(util.minima(corpus, key=key, min_min=min_min))


def avg_dist(w1, w2, p=0.5):
    q = 1-p
    squares = [(ed(w, w1)**2)*q + (ed(w, w2)**2)*p for w in allWords]
    mini, mins = choose(util.minima(enumerate(squares), key=lambda x:x[1]))
    return allWords[mini]


def dist_gradient(w1, w2, num=1):
    words = []
    fromWord = w1
    for n in range(num):
        p = (n+1)/(num+1)
        w = avg_dist(fromWord, w2, p)
        fromWord = w
        words.append(w)
    return words


#####################################################
#                   case_pattern                    #
#####################################################
#      I may have gone too far in a few places

CASE_RE = re.compile(r'^([^()]*)(?:\(([^()]+)\)([^()]*))?$')

CASE_UPP = object()
CASE_LOW = object()
CASE_XOR = object()
CASE_NOP = object()


def case_parse(s):
    out = []
    for c in s:
        if c.isupper(): out.append(CASE_UPP)
        elif c.islower(): out.append(CASE_LOW)
        elif c == '^': out.append(CASE_XOR)
        else: out.append(CASE_NOP)
    return out


def apply_case(c, i):
    if c is CASE_UPP: return i.upper()
    if c is CASE_LOW: return i.lower()
    if c is CASE_XOR: return i.upper() if i.islower() else i.lower()
    if c is CASE_NOP: return i


def case_pattern(pattern, *inputs):
    '''
    Converts the case of each input string according to a pattern string.

    A pattern is parsed as a sequence 4 types of actions:
    • Upper/lowercase characters (A/a) enforce upper/lowercase
    • Neutral characters (?!_-,.etc.) leave case unchanged
    • Carrot (^) swaps upper to lowercase and the other way around

    Furthermore, parentheseses will repeat that part to stretch the pattern to fit the entire input.

    Examples:
        A       Just turns the first character uppercase
        Aa      Turns the first character upper, the second lower
        A(a)    Turns the first character upper, all others lower
        A(-)A   Turns the first and last characters upper
        ^(Aa)^  Reverses case on the first and last characters, AnD DoEs tHiS To tHe oNeS BeTwEeN
    '''
    m = re.match(CASE_RE, pattern)
    if m is None:
        raise ValueError('Invalid case pattern "%s"' % pattern)
    
    head, body, tail = m.groups()
    outputs = []
    
    if body is None:
        ## Simplest case: only a head was given
        for input in inputs:
            output = []
            for i, c in zip(input, case_parse(head)):
                output.append(apply_case(c, i))
            output.append(input[len(head):])
            outputs.append(''.join(output))

    else:
        lh, lb, lt = len(head), len(body), len(tail)
        head, body, tail = case_parse(head), case_parse(body), case_parse(tail)

        for input in inputs:
            output = []
            li = len(input)

            for i, c in zip(input, head):
                output.append(apply_case(c, i))

            if li > lh:
                ## There are characters left after applying the head
                if li - lh < lt:
                    ## The Tail is too long to fit in the remaining characters
                    for i, c in zip(input[lh:], tail[-(li-lh):]):
                        output.append(apply_case(c, i))

                else:
                    ## the Tail fits; fill the space between the Head and Tail with the Body looped
                    for i in range(li - lh - lt): # Repeat the Body as many times as needed (possibly 0)
                        output.append(apply_case(body[i%lb], input[lh+i]))
                    if lt:
                        for i, c in zip(input[-lt:], tail):
                            output.append(apply_case(c, i))
            outputs.append(''.join(output))

    return outputs