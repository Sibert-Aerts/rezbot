'''
This file defines a pyparsing grammar describing important parts of, but not all of, the Rezbot scripting language.
Not used directly, but internally used by various .from_string methods on classes representing Rezbot scripting structures.
'''
import re
from pyparsing import (
    Empty, alphas, alphanums, nums, Literal, Word, Char, ParserElement, Forward,
    Combine, OneOrMore, Group, Regex, ZeroOrMore, White, CaselessKeyword, Opt,
    Keyword, ParseResults, Suppress, delimited_list,
)

ParserElement.enable_packrat()


# TODO: Every instance of Group(templated_element | string_bit) is a pointless layer of Grouping,
#   remove those AND fix it so the .from_parsed methods to match it

# TODO: use .set_name to give every grammar rule a decent name that gets shown in error output!!!

# ============================================ Terminals ===========================================

identifier      = Word(alphas + '_', alphanums + '_')
pos_integer     = Word(nums)
integer         = Combine(Opt(Literal('-')) + Word(nums))

left_brace      = Literal('{').suppress().leave_whitespace()
right_brace     = Literal('}').suppress()
left_paren      = Literal('(').suppress()
right_paren     = Literal(')').suppress()
eq              = Literal('=').suppress()
escaped_symbol  = Literal('~').suppress() + Char('{}~"\'/')
question_mark   = Literal('?').suppress()
backslash       = Literal('\\').suppress()

optional_white  = Opt(White()).suppress()

# ============================================= Grammar ============================================

# ======================== Forward definitions

templated_element: ParserElement = Forward()

condition: ParserElement = Forward()

# ======================== Templated Strings

def make_quoted(q):
    q = Literal(q).suppress()
    quoted_string_bit = Combine(OneOrMore( escaped_symbol | (~q + Regex('[^{}]', re.S)) ))('string_bit').leave_whitespace()
    quoted_string = q - (OneOrMore(Group(templated_element | quoted_string_bit)) | Empty())('value') + q
    return quoted_string

quoted_templated_string = (make_quoted('"""') | make_quoted('"') | make_quoted("'") | make_quoted('/'))
'A templated string, wrapped in either triple quotes """, regular quotes ", single quotes \' or forward slashes /'

string_bit_no_space = Combine(OneOrMore(escaped_symbol | Regex('[^{}\s]', re.S)))('string_bit').leave_whitespace()
unquoted_spaceless_templated_string = OneOrMore( Group(templated_element | string_bit_no_space) )('value')
'A nonempty templated string, without wrapping quotes, without any spaces in the literal parts, (nb. containing sources and items may have spaces)'

string_bit = Combine(OneOrMore(escaped_symbol | Regex('[^{}]', re.S)))('string_bit').leave_whitespace()
absolute_templated_string = (OneOrMore(Group(templated_element | string_bit)) | Empty())('value')
'A templated string, parsed in a context where we are supposed to take the ENTIRE thing as the templated string.'


# ======================== Argument Assignments

arg_value = (quoted_templated_string | unquoted_spaceless_templated_string).leave_whitespace()
explicit_arg = Group(identifier('param_name') + eq.leave_whitespace() - arg_value)
'An explicity param=<templated_string> assingment'

implicit_string_bit = Combine(ZeroOrMore(White()) + OneOrMore(escaped_symbol | Regex('[^{}\s]', re.S)) | OneOrMore(White()))('string_bit').leave_whitespace()
implicit_arg = Group( OneOrMore( ~explicit_arg + Group(templated_element | implicit_string_bit) )('implicit_arg') )
'Literally anything that is not an explicit argument assignment, but immediately parsed as a stripped templated string.'

argument_list = optional_white + ZeroOrMore(explicit_arg | implicit_arg)
'A free mixture of explicit and implicit argument assignments.'


# ======================== Templated Element: Items

item = Group( left_brace + Opt(Word('^'))('carrots') + Opt(integer)('index') + Opt('!')('bang') + right_brace )('item')

# ======================== Templated Element: Sources

source_amount = Word(nums) | CaselessKeyword('ALL')
source = Group( left_brace + Opt(source_amount)('amount') + identifier('source_name') + Opt(argument_list('args')) + right_brace )('source')

# ======================== Templated Element: Special Symbol

te_special = Group( left_brace + backslash - identifier('name') + right_brace )('te_special')


# ======================== Conditions

# ======== Root Conditions: Comparison

comp_op_eq   = Literal('==') | Literal('!=')
comp_op_num  = Literal('<=') | Literal('>=') | Literal('<') | Literal('>')
comp_op_like = Combine(Opt(Keyword('NOT')) + (Keyword('LIKE')), adjacent=False)
comp_op = comp_op_eq | comp_op_num | comp_op_like

string_bit_cond_safe = Combine(OneOrMore(escaped_symbol | ~(comp_op_eq | comp_op_num) + Regex('[^{}()\s]', re.S)))('string_bit').leave_whitespace()
unquoted_spaceless_compless_templated_string = OneOrMore( Group(templated_element | string_bit_cond_safe) )('value')
'A nonempty templated string, without wrapping quotes, without any spaces in the literal parts, (nb. containing sources and items may have spaces)'

comparison_safe_templated_string = optional_white + Group(quoted_templated_string | unquoted_spaceless_compless_templated_string) + optional_white
comparison = Group(comparison_safe_templated_string + comp_op - comparison_safe_templated_string)('comparison')

# ======== Root Conditions: Predicate

pred_category = (Keyword('WHITE') | Keyword('EMPTY') | Keyword('TRUE') | Keyword('FALSE') | Keyword('BOOL') | Keyword('INT') | Keyword('FLOAT'))('pred_category')
pred_is_category = Combine(Keyword('IS') - Opt(Keyword('NOT'))('not') + pred_category, adjacent=False)
predicate = Group(comparison_safe_templated_string + pred_is_category)('predicate')

# ======== Composite Conditions

kw_and = Keyword('and', caseless=True).suppress()
kw_or  = Keyword('or', caseless=True).suppress()
kw_not = Keyword('not', caseless=True)

root_condition = (left_paren + condition + right_paren) | predicate | comparison
cond_negation = Group(OneOrMore(kw_not) + root_condition)('negation') | root_condition
cond_conjunction = Group(cond_negation + OneOrMore(kw_and + cond_negation))('conjunction') | cond_negation
condition <<= Group(cond_conjunction + OneOrMore(kw_or + cond_conjunction))('disjunction') | cond_conjunction


# ======================== Templated Element: Conditionals

kw_if   = Keyword('if', caseless=True).suppress()
kw_else = Keyword('else', caseless=True).suppress()

conditional_expr = comparison_safe_templated_string('case_if') + kw_if + condition('condition') + kw_else + comparison_safe_templated_string('case_else')
conditional = Group( left_brace + question_mark - conditional_expr + right_brace )('conditional')

# ======================== Templated Element

templated_element <<= te_special | item | conditional | source


# ======================== Group Mode

gm_multiply_flag = Opt(Literal('*')('multiply_flag'))
gm_strictness_flag = Combine(ZeroOrMore('!'))('strictness_flag')
def may_be_parenthesized(expr):
    # Utility to catch old IF(()) and SWITCH(()) syntax
    return (left_paren + expr + right_paren) | expr

# ======== Group Mode: Split Mode

gm_split_row = Group( left_paren + pos_integer('size') - right_paren + gm_strictness_flag )('split_row')
gm_split_divide = Group( Suppress('/')  - pos_integer('count') + gm_strictness_flag )('split_divide')
gm_split_modulo = Group( Suppress('%')  - pos_integer('modulo') + gm_strictness_flag )('split_modulo')
gm_split_column = Group( Suppress('\\') - pos_integer('size') + gm_strictness_flag )('split_column')
gm_split_interval = Group( Suppress('#') - Opt(integer)('start') + Opt(Literal(':')('colon') + Opt(integer)('end') + gm_strictness_flag ) )('split_interval')

gm_single_split = gm_split_row | gm_split_divide | gm_split_modulo | gm_split_column | gm_split_interval
gm_split = ZeroOrMore(gm_split_row | gm_split_divide | gm_split_modulo | gm_split_column | gm_split_interval)('split')

# ======== Group Mode: Mid Mode

gm_mid_if       = Group( Keyword('IF').suppress() - left_paren + may_be_parenthesized(condition) + right_paren + gm_strictness_flag )('mid_if')
gm_mid_sort_by  = Group( Keyword('SORT BY').suppress() - Group(delimited_list(Combine(Opt('+') + pos_integer)))('indices') )('mid_sort_by')
gm_mid_group_by = Group( (Keyword('GROUP') | Keyword('COLLECT') | Keyword('EXTRACT'))('mode') - Keyword('BY').suppress() + Group(delimited_list(pos_integer))('indices') )('mid_group_by')

gm_mid = Opt(gm_mid_if) + Opt(gm_mid_sort_by) + Opt(gm_mid_group_by)

# ======== Group Mode: Assign Mode

gm_assign_random = Group( gm_multiply_flag + question_mark )('assign_random')
gm_assign_switch_body = may_be_parenthesized( Group(delimited_list(condition, '|'))('conditions') )
gm_assign_switch = Group( gm_multiply_flag + Keyword('SWITCH').suppress() - left_paren + gm_assign_switch_body + right_paren + gm_strictness_flag )('assign_switch')
gm_assign_default = Group( gm_multiply_flag )('assign_default')

# NOTE: `gm_assign_default` may match an empty string, so this may also
gm_assign = (gm_assign_random | gm_assign_switch | gm_assign_default)('assign')

# ======== Group Mode

groupmode = Group(gm_split + gm_mid + gm_assign)('groupmode')
groupmode_and_remainder = groupmode + Regex('.*', flags=re.S)('remainder')


'''
Note to self about Rezbot Script's grammar and the current model:

The above grammar is currently used via three entry points:
    Given a string, interpret the entire thing as a TemplatedString
    Given a string, interpret the entire thing as an Arguments object
    Given a string, interpret the entire thing as a Condition

That does not however cover the entire grammar.
There's places that can still be grammaticised, e.g. a grammar for GroupModes could be defined,
    which would replace the third use case by "Given a string, consume the leading GroupMode".

At that point however, things get more complicated, as any attempt at grammaticising higher up
    the scripting language's structure hits the wall of ChoiceTree expansions being wielded.

ANALYSIS OF THE CURRENT NON-PYPARSING GRAMMARS RESPONSIBLE FOR PARSING A SCRIPT:
    1. The "butcher grammar", which does not care about the finer aspects of the script, merely cares about chopping it into [origin, pipe_chunk, pipe_chunk, ...]
        This is implemented via extremely simple state machines in PipelineWithOrigin.split and Pipeline.split_into_segments.
        Currently, essentially, these very naively consider quotation marks and nested parentheses to determine "legit, top level >'s" to split on.
    2. Consume each "pipe chunk"'s leading GroupMode (grammaticizable!)
    3. Then, for each "pipe chunk":
        1. Use FOUL TRICKERY to temporarily evacuate all triple-quoted and parenthesized substrings
        2. ChoiceTree expand
        3. Put triple-quoted and parenthesized substrings back
        Effectively, this is like a variant ChoiceTree grammar that acknowledges "ChoiceTree-invariant substrings",
    4. Then a simple manual parse job followed by a grammar parse turns each one into a (pipe_name, Arguments)

Points 1, 2 and 3 can each individually be improved by making a real grammar out of what is currently a more manual ordeal.
For step 2 (GroupModes) this obviously contributes to the larger project of pyparsing entire scripts.

For step 1 and 3, these would be grammars acting independently of the main grammar, and would not simply slot into the current grammar.
So to speak, they would not be scaffolding, but bandaids that we'd have to peel off later.
Better than not doing anything, but not part of an ideal solution.

It's clear that to make a full grammar to parse entire scripts, the power currently permitted by ChoiceTree needs to be weakened
in order to make it fit in with the other grammar.
At the same time, existing grammar needs to be made more complex to replace the powers currently granted by ChoiceTree wizardy.

e.g. Make it so the Origin can only have full sources inside of a single ChoiceTree segment, so "{foo [}|bar}]" is super illegal,
    and maybe "{[foo|bar]}" is too, but then "{foo [bar|baz]}" should probably be allowed.
'''


# ======== Utility

def print_parse_result(result: ParseResults, indent=0, name=''):
    '''Prints a ParseResults as a tree, using sub-results' names. Little hackish but works.'''
    if isinstance(result, ParseResults):
        if result._name:
            print('    '*indent, result._name)
        # Hack to associate names to str items that don't have a _name field
        names_by_item = {id(v): k for k, v in result.as_dict().items()}
        for item in result:
            print_parse_result(item, indent+1, name=names_by_item.get(id(item), ''))
    else:
        if name:
            print('    '*indent, name, repr(result))
        else:
            print('    '*indent, repr(result))
