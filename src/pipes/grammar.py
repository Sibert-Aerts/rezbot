'''
This file defines pyparsing grammar comprising important parts of, but not all of, the Rezbot scripting language grammar.
'''

from pyparsing import (
    Empty, alphas, alphanums, nums, Literal, Word, Char, ParserElement, Forward,
    Combine, OneOrMore, Group, Regex, ZeroOrMore, White, CaselessKeyword, Optional,
    Keyword, ParseResults
)
import re

ParserElement.enable_packrat()

# ============================================ Terminals ===========================================

identifier      = Word(alphas + '_', alphanums + '_')
left_brace      = Literal('{').suppress()
right_brace     = Literal('}').suppress()
left_paren      = Literal('(').suppress()
right_paren     = Literal(')').suppress()
eq              = Literal('=').suppress()
escaped_symbol  = Literal('~').suppress() + Char('{}~"\'/')
optional_white  = Optional(White()).suppress()

# ============================================= Grammar ============================================

source: ParserElement = Forward()
item: ParserElement = Forward()


# ======================== Templated Strings

def make_quoted(q):
    q = Literal(q).suppress()
    quoted_string_bit = Combine(OneOrMore( escaped_symbol | (~q + Regex('[^{}]', re.S)) ))('string_bit').leave_whitespace()
    quoted_string = q + (OneOrMore(Group(item | source | quoted_string_bit)) | Empty())('value') + q
    return quoted_string

quoted_templated_string = (make_quoted('"""') | make_quoted('"') | make_quoted("'") | make_quoted('/'))
'A templated string, wrapped in either triple quotes """, regular quotes ", single quotes \' or forward slashes /'

string_bit_no_space = Combine(OneOrMore(escaped_symbol | Regex('[^{}\s]', re.S)))('string_bit').leave_whitespace()
unquoted_spaceless_templated_string = OneOrMore( Group(item | source | string_bit_no_space) )('value')
'A nonempty templated string, without wrapping quotes, without any spaces in the literal parts, (nb. containing sources and items may have spaces)'

string_bit = Combine(OneOrMore(escaped_symbol | Regex('[^{}]', re.S)))('string_bit').leave_whitespace()
absolute_templated_string = (OneOrMore(Group(item | source | string_bit)) | Empty())('value')
'A templated string, parsed in a context where we are supposed to take the ENTIRE thing as the templated string.'


# ======================== Argument Assignments

arg_value = (quoted_templated_string | unquoted_spaceless_templated_string).leave_whitespace()
explicit_arg = Group(identifier('param_name') + eq.leave_whitespace() + arg_value)
'An explicity param=<templated_string> assingment'

implicit_string_bit = Combine(ZeroOrMore(White()) + OneOrMore(escaped_symbol | Regex('[^{}\s]', re.S)) | OneOrMore(White()))('string_bit').leave_whitespace()
implicit_arg = Group( OneOrMore( ~explicit_arg + Group(item | source | implicit_string_bit) )('implicit_arg') )
'Literally anything that is not an explicit argument assignment, but immediately parsed as a stripped templated string.'

argument_list = optional_white + ZeroOrMore(explicit_arg | implicit_arg)
'A free mixture of explicit and implicit argument assignments.'


# ======================== Items

item <<= Group( left_brace + Optional(Word('^'))('carrots') + Optional( Regex('-?\d+') )('index') + Optional('!')('bang') + right_brace )('item')
item.leave_whitespace()


# ======================== Sources

amount = Word(nums) | CaselessKeyword('ALL')
source <<= Group( left_brace +  Optional(amount)('amount') + identifier('source_name') + Optional(argument_list('args')) + right_brace )('source')
source.leave_whitespace()


# ======================== Conditions

# ======== Root Conditions

str_comp_op  = (Literal('==') | Literal('!='))('str_comp_op')
num_comp_op  = (Literal('<=') | Literal('>=') | Literal('<') | Literal('>'))('num_comp_op')
like_comp_op = Combine(Optional(Keyword('NOT')) + (Keyword('LIKE')), adjacent=False)('like_comp_op')
comp_op = str_comp_op | num_comp_op | like_comp_op

string_bit_cond_safe = Combine(OneOrMore(escaped_symbol | ~(str_comp_op | num_comp_op) + Regex('[^{}()\s]', re.S)))('string_bit').leave_whitespace()
unquoted_spaceless_compless_templated_string = OneOrMore( Group(item | source | string_bit_cond_safe) )('value')
'A nonempty templated string, without wrapping quotes, without any spaces in the literal parts, (nb. containing sources and items may have spaces)'

comparison_templated_string = optional_white + Group(quoted_templated_string | unquoted_spaceless_compless_templated_string) + optional_white
comparison = Group(comparison_templated_string + comp_op + comparison_templated_string)('comparison')


# ======== Composite Conditions

kw_and = Keyword('and', caseless=True).suppress()
kw_or  = Keyword('or', caseless=True).suppress()
kw_not = Keyword('not', caseless=True)

condition: ParserElement = Forward()
root_condition = (left_paren + condition + right_paren) | comparison
cond_negation = Group(OneOrMore(kw_not) + root_condition)('negation') | root_condition
cond_conjunction = Group(cond_negation + OneOrMore(kw_and + cond_negation))('conjunction') | cond_negation
condition <<= Group(cond_conjunction + OneOrMore(kw_or + cond_conjunction))('disjunction') | cond_conjunction


# ======== Utility

def print_parse_result(result, indent=0):
    if isinstance(result, ParseResults):
        if result._name:
            print('   '*indent, result._name)
        for item in result:
            print_parse_result(item, indent+1)
    else:
        print('   '*indent, repr(result))


# import time
# start = time.time()
# result = condition.parse_string("{0}=={1}! and 0==1 or 1==2", True)
# print('TIME', time.time()-start)
# print(len(result[0]))
# print_parse_result(result[0])
