from pyparsing import (
    Empty, alphas, alphanums, nums, Literal, Word, Char, ParserElement, Forward,
    Combine, OneOrMore, Group, Regex, ZeroOrMore, White, CaselessKeyword, Optional
)
import re


## TERMINALS
identifier = Word(alphas + '_', alphanums + '_')

lBrace = Literal('{').suppress()
rBrace = Literal('}').suppress()
eq = Literal('=').suppress()
escapedSymbol = Literal('~').suppress() + Char('{}~"\'/')

## GRAMMAR
source: ParserElement = Forward()
item: ParserElement = Forward()

#### ARGS
##### ARGVALUES
def Quote(q):
    q = Literal(q).suppress()
    quotedStringBit = Combine(OneOrMore( escapedSymbol | (~q + Regex('[^{}]', re.S)) ))('stringBit').leaveWhitespace()
    quotedString = q + ( OneOrMore( Group(item.leaveWhitespace() | source.leaveWhitespace() | quotedStringBit) ) | Empty() )('value') + q
    return quotedString

argValueQuotes = (Quote('"""') | Quote('"') | Quote("'") | Quote('/'))

stringBitNoSpaces = Combine(OneOrMore(escapedSymbol | Regex('[^{}\s]', re.S)))('stringBit').leaveWhitespace()
argValueNoSpace = OneOrMore( Group(item.leaveWhitespace() | source.leaveWhitespace() | stringBitNoSpaces) )('value')

argValue = argValueQuotes | argValueNoSpace

###### ARG ASSIGNMENTS
explicitArg = Group(identifier('paramName') + eq.leaveWhitespace() + argValue.leaveWhitespace() )

implicitStringBit = Combine(ZeroOrMore(White()) + OneOrMore(escapedSymbol | Regex('[^{}\s]', re.S)) | OneOrMore(White()))('stringBit').leaveWhitespace()
implicitArg = Group( OneOrMore( ~explicitArg + Group(item.leaveWhitespace() | source.leaveWhitespace() | implicitStringBit) )('implicitArg') )

argumentList = ZeroOrMore(explicitArg | implicitArg)

#### ITEM
item <<= Group( lBrace + Optional(Word('^'))('carrots') + Optional( Regex('-?\d+') )('index') + Optional('!')('bang') + rBrace )('item')

#### SOURCE
amount = Word(nums) | CaselessKeyword('ALL')
source <<= Group( lBrace +  Optional(amount)('amount') + identifier('sourceName') + argumentList('args') + rBrace )('source')

#### PIPE
pipe = Group( identifier('sourceName') + argumentList('args') )('pipe')

#### STRING
stringBit = Combine(OneOrMore(escapedSymbol | Regex('[^{}]', re.S)))('stringBit').leaveWhitespace()
templatedString = OneOrMore( Group(item.leaveWhitespace() | source.leaveWhitespace() | stringBit) ) | Empty()

