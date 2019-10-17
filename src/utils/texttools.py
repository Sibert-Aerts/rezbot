import editdistance
import re
import requests

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
    return '```\n{0}```'.format(s.replace('```','`­``'))

def matchCase(char, case):
    return char.upper() if case.isupper() else char.lower()

def pSub(fro, to):
    def func(str, p):
        return re.sub(fro, lambda c: c.group(0) if not chance(p) else matchCase(choose(to), c.group(0)), str)
    return func

def camel_case(s):
    return ''.join(s.title().split())

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


def alpha_sub(fro, to, text, ignoreCase=False):
    '''Performs alphabetic substitution, so a character from `fro` is replaced with the equivalent in `to`.'''
    w = len(to) / len(fro)
    if w != int(w): print('ERROR: MISMATCHED ALPHABET LENGTHS: ' + to)
    w = int(w)
    def _sub(t):
        i = fro.find(t.lower() if ignoreCase else t)
        return t if i < 0 else to[i*w:i*w+w]
    return ''.join([_sub(t) for t in text])

# A couple of fun alphabetic substitutions
smallcaps = lambda x : alpha_sub(abc, 'ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ', x, ignoreCase=True)
squared   = lambda x : alpha_sub(abc, '🇦­🇧­🇨­🇩­🇪­🇫­🇬­🇭­🇮­🇯­🇰­🇱­🇲­🇳­🇴­🇵­🇶­🇷­🇸­🇹­🇺­🇻­🇼­🇽­🇾­🇿­', alpha_sub(digs, '0⃣1⃣2⃣3⃣4⃣5⃣6⃣7⃣8⃣9⃣', x), ignoreCase=True) # Warning: There's an &shy; between each character!
circled   = lambda x : alpha_sub(ABCabc + digs, 'ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ' '0①②③④⑤⑥⑦⑧⑨', x)
flip      = lambda x : alpha_sub(ABCabc, '∀qƆpƎℲפHIſʞ˥WNOԀQɹS┴∩ΛMX⅄Zɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz', x[::-1])
mirror    = lambda x : alpha_sub(ABCabc, 'AdↃbƎꟻGHIJK⅃MᴎOꟼpᴙꙄTUVWXYZAdↄbɘꟻgHijklmᴎoqpᴙꙅTUvwxYz', x[::-1])
fullwidth = lambda x : alpha_sub(ABCabc + digs + '!\"#$%&\'()*+,-./:;<=>?@[\]^_`{|}~ ', 'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ' '０１２３４５６７８９' '！＂＃＄％＆＇（）＊＋，－．／：；＜＝＞？＠［＼］＾＿｀｛｜｝～　', x)
script    = lambda x : alpha_sub(ABCabc, '𝒜ℬ𝒞𝒟ℰℱ𝒢ℋℐ𝒥𝒦ℒℳ𝒩𝒪𝒫𝒬ℛ𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵𝒶𝒷𝒸𝒹ℯ𝒻ℊ𝒽𝒾𝒿𝓀𝓁𝓂𝓃ℴ𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏', x)
monospace = lambda x : alpha_sub(ABCabc + digs, '𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣' '𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿', x)
fraktur   = lambda x : alpha_sub(ABCabc, '𝔄𝔅ℭ𝔇𝔈𝔉𝔊ℌℑ𝔍𝔎𝔏𝔐𝔑𝔒𝔓𝔔ℜ𝔖𝔗𝔘𝔙𝔚𝔛𝔜ℨ𝔞𝔟𝔠𝔡𝔢𝔣𝔤𝔥𝔦𝔧𝔨𝔩𝔪𝔫𝔬𝔭𝔮𝔯𝔰𝔱𝔲𝔳𝔴𝔵𝔶𝔷', x)
struck    = lambda x : alpha_sub(ABCabc + digs, '𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫' '𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡', x)
sans      = lambda x : alpha_sub(ABCabc + digs, '𝖠𝖡𝖢𝖣𝖤𝖥𝖦𝖧𝖨𝖩𝖪𝖫𝖬𝖭𝖮𝖯𝖰𝖱𝖲𝖳𝖴𝖵𝖶𝖷𝖸𝖹𝖺𝖻𝖼𝖽𝖾𝖿𝗀𝗁𝗂𝗃𝗄𝗅𝗆𝗇𝗈𝗉𝗊𝗋𝗌𝗍𝗎𝗏𝗐𝗑𝗒𝗓' '𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫', x) # these look normal but they aren't
superscript=lambda x : alpha_sub(ABCabc + digs + '()', 'ᴬᴮᶜᴰᴱᶠᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᑫᴿˢᵀᵁⱽᵂˣʸᶻᵃᵇᶜᵈᵉᶠᵍʰᶦʲᵏᶫᵐᶰᵒᵖᑫʳˢᵗᵘᵛʷˣʸᶻ' '⁰¹²³⁴⁵⁶⁷⁸⁹' '⁽⁾', x)

converters = {
    'smallcaps' : smallcaps,
    'flip' : flip,
    'mirror' : mirror,
    'squared' : squared,
    'circled' : circled,
    'fullwidth' : fullwidth,
    'script' : script,
    'monospace' : monospace,
    'fraktur' : fraktur,
    'struck' : struck,
    'sans' : sans,
    'superscript' : superscript,
}

# Edit distance
def ed(x, y):
    return editdistance.eval(x.lower(), y.lower())

def min_dist(w, maxMin=0, corpus=None):
    if corpus is None: corpus = allWords
    return choose(util.mins(corpus, key=lambda x:ed(x, w), maxMin=maxMin))

def avg_dist(w1, w2, p=0.5):
    q = 1-p
    squares = [(ed(w, w1)**2)*q + (ed(w, w2)**2)*p for w in allWords]
    mini, mins = choose(util.mins(enumerate(squares), key=lambda x:x[1]))
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
        A(-)A   Turns the first upper, the last lower
        ^(Aa)^  Reverses the first and last characters, AnD DoEs tHiS To tHe oNeS BeTwEeN
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