from pyparsing import (
    Empty, alphas, alphanums, nums, Literal, Word, Char, ParserElement, Forward,
    Combine, OneOrMore, Group, Regex, ZeroOrMore, White, CaselessKeyword, Optional
)
import re

'''
This file defines pyparsing grammar comprising important parts of, but not all of, the Rezbot scripting language grammar.
'''

## TERMINALS
identifier = Word(alphas + '_', alphanums + '_')
left_brace = Literal('{').suppress()
right_brace = Literal('}').suppress()
eq = Literal('=').suppress()
escaped_symbol = Literal('~').suppress() + Char('{}~"\'/')

## GRAMMAR
source: ParserElement = Forward()
item: ParserElement = Forward()

#### ARGS
##### ARGVALUES
def make_quoted(q):
    q = Literal(q).suppress()
    quoted_string_bit = Combine(OneOrMore( escaped_symbol | (~q + Regex('[^{}]', re.S)) ))('string_bit').leave_whitespace()
    quoted_string = q + ( OneOrMore( Group(item.leave_whitespace() | source.leave_whitespace() | quoted_string_bit) ) | Empty() )('value') + q
    return quoted_string

arg_value_quoted = (make_quoted('"""') | make_quoted('"') | make_quoted("'") | make_quoted('/'))

string_bit_no_space = Combine(OneOrMore(escaped_symbol | Regex('[^{}\s]', re.S)))('string_bit').leave_whitespace()
arg_value_no_space = OneOrMore( Group(item.leave_whitespace() | source.leave_whitespace() | string_bit_no_space) )('value')

argValue = arg_value_quoted | arg_value_no_space

###### ARG ASSIGNMENTS
explicit_arg = Group(identifier('paramName') + eq.leave_whitespace() + argValue.leave_whitespace() )

implicit_string_bit = Combine(ZeroOrMore(White()) + OneOrMore(escaped_symbol | Regex('[^{}\s]', re.S)) | OneOrMore(White()))('string_bit').leave_whitespace()
implicit_arg = Group( OneOrMore( ~explicit_arg + Group(item.leave_whitespace() | source.leave_whitespace() | implicit_string_bit) )('implicit_arg') )

argument_list = Optional(White()).suppress() + ZeroOrMore(explicit_arg | implicit_arg)

#### ITEM
item <<= Group( left_brace + Optional(Word('^'))('carrots') + Optional( Regex('-?\d+') )('index') + Optional('!')('bang') + right_brace )('item')

#### SOURCE
amount = Word(nums) | CaselessKeyword('ALL')
source <<= Group( left_brace +  Optional(amount)('amount') + identifier('source_name') + Optional(argument_list('args')) + right_brace )('source')

#### PIPE
pipe = Group( identifier('source_name') + argument_list('args') )('pipe')

#### STRING
string_bit = Combine(OneOrMore(escaped_symbol | Regex('[^{}]', re.S)))('string_bit').leave_whitespace()
templated_string = OneOrMore( Group(item.leave_whitespace() | source.leave_whitespace() | string_bit) ) | Empty()

