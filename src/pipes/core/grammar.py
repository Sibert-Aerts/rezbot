'''
This file defines a pyparsing grammar describing important parts of, but not all of, the Rezbot scripting language.
Not used directly, but internally used by various .from_string methods on classes representing Rezbot scripting structures.
'''
import re
from pyparsing import (
    Empty, alphas, alphanums, nums, Literal, Word, Char, ParserElement, Forward,
    Combine, OneOrMore, Group, Regex, ZeroOrMore, White, CaselessKeyword, Opt,
    Keyword, ParseResults, Suppress, FollowedBy, delimited_list,
)

ParserElement.enable_packrat()

# ============================================= Utility ============================================

def SuppKeyword(*args, **kwargs):
    return Suppress(Keyword(*args, **kwargs))

# ============================================ Terminals ===========================================

left_brace      = Suppress('{').leave_whitespace()
right_brace     = Suppress('}')
left_paren      = Suppress('(')
right_paren     = Suppress(')')
eq              = Suppress('=')
escaped_symbol  = Suppress('~') + Char('{}~"\'/')
question_mark   = Suppress('?')
colon           = Suppress(':')
backslash       = Suppress('\\')
chevron         = Suppress('>')
double_chevron  = Suppress('>>')

# Needed around elements where .leave_whitespace() has been used
optional_white  = Suppress(Opt(White()))

identifier      = Word(alphas + '_', alphanums + '_').set_name('identifier')
pos_integer     = Word(nums).set_name('positive integer')
integer         = Combine(Opt(Literal('-')) + Word(nums)).set_name('integer')
# TODO: Get rid of '..' as a range indicator
interval        = Group(Opt(integer)('start') + (colon | Suppress('..')) + Opt(integer)('end')).set_name('interval')

# ============================================= Grammar ============================================

# ======================== Forward definitions

simple_script: ParserElement = Forward().set_name('Simple Script')

templated_element: ParserElement = Forward().set_name('Templated Element')

condition: ParserElement = Forward().set_name('Condition')

# ======================== Templated Strings

def make_quoted_ts(q):
    q = Suppress(q)
    quoted_string_bit = Combine(OneOrMore( escaped_symbol | (~q + Regex('[^{}]', re.S)) ))('string_bit').leave_whitespace()
    quoted_string = q - (OneOrMore(templated_element | quoted_string_bit) | Empty())('value') + q
    return quoted_string.set_name('Quoted Templated String')

quoted_templated_string = (make_quoted_ts('"""') | make_quoted_ts('"') | make_quoted_ts("'") | make_quoted_ts('/')).set_name('Quoted Templated String')
'A templated string, wrapped in either triple quotes """, regular quotes ", single quotes \' or forward slashes /'

string_bit_no_space = Combine(OneOrMore(escaped_symbol | Regex('[^{}>\s]', re.S)))('string_bit').leave_whitespace()
unquoted_spaceless_templated_string = OneOrMore(templated_element | string_bit_no_space)('value').set_name('Inline Templated String')
'A nonempty templated string, without wrapping quotes, without any spaces or chevrons in the literal parts, (nb. containing sources and items may have spaces or chevrons)'

absolute_string_bit = Combine(OneOrMore(escaped_symbol | Regex('[^{}]', re.S)))('string_bit').leave_whitespace()
absolute_templated_string = (OneOrMore(templated_element | absolute_string_bit) | Empty())('value').set_name('Templated String')
'A templated string, parsed in a context where we are supposed to take the ENTIRE thing as the templated string, without enclosing quotes.'

origin_safe_string_bit = Combine(OneOrMore(escaped_symbol | Regex('[^{}>]', re.S)))('string_bit').leave_whitespace()
origin_safe_templated_string = (OneOrMore(templated_element | origin_safe_string_bit) | Empty())('value').set_name('Templated String')
'A templated string whose literal parts may contain anything but the > symbol.'


# ======================== Argument Assignments

arg_value = (quoted_templated_string | unquoted_spaceless_templated_string).leave_whitespace().set_name('Argument Value')
explicit_arg = Group(identifier('param_name') + eq.leave_whitespace() - arg_value + optional_white).set_name('Argument Assignment')
'An explicity "param=<templated_string>" assignment'

implicit_string_bit = Combine(ZeroOrMore(White()) + OneOrMore(escaped_symbol | Regex('[^{}\s>]', re.S)) | OneOrMore(White()))('string_bit').leave_whitespace()
implicit_arg = Group( OneOrMore( ~explicit_arg + (templated_element | implicit_string_bit) )('implicit_arg') ).set_name('Implicit Argument')
'Literally anything that is not an explicit argument assignment, but immediately parsed as a stripped templated string.'
quoted_implicit_arg = Group(quoted_templated_string)('quoted_implicit_arg')

argument_list = optional_white + ZeroOrMore(explicit_arg | quoted_implicit_arg | implicit_arg).set_name('Argument List')
'A free mixture of explicit and implicit argument assignments.'


# ======================== Templated Element: Items

item_index = Group(Opt(Word('^'))('carrots') + (interval('interval') | integer('index')) + Opt('!')('bang'))('item_index').set_name('Item Index')

# TODO: Deprecate carrots, and maybe even bang from implicit_item
implicit_item = Group(left_brace + Opt(Word('^'))('carrots') + Opt('!')('bang') + right_brace)('implicit_item')
explicit_item = Group(left_brace + Group(delimited_list(item_index, ','))('indices') + right_brace)('explicit_item')

item = (implicit_item | explicit_item).set_name('Templated Item')

# ======================== Templated Element: Sources

source_amount = Word(nums) | CaselessKeyword('ALL')
source = Group( left_brace + Opt(source_amount)('amount') + identifier('source_name') + Opt(argument_list('args')) + right_brace )('source').set_name('Templated Source')

# ======================== Templated Element: Inline script

te_script = Group( left_brace + Suppress('>>') + Group(simple_script)('inline_script') + right_brace)('te_script').set_name('Templated Inline Script')

# ======================== Templated Element: Special Symbol

te_special = Group( left_brace + backslash - identifier('name') + right_brace )('te_special').set_name('Templated Special Symbol')


# ======================== Conditions

# ======== Root Conditions: Comparison

comp_op_eq   = Literal('==') | Literal('!=')
comp_op_num  = Literal('<=') | Literal('>=') | Literal('<') | Literal('>')
comp_op_like = Combine(Opt(Keyword('NOT')) + (Keyword('LIKE')), adjacent=False)
comp_op = (comp_op_eq | comp_op_num | comp_op_like).set_name('Comparison Operator')

string_bit_cond_safe = Combine(OneOrMore(escaped_symbol | ~(comp_op_eq | comp_op_num) + Regex('[^{}=|()<>\s]', re.S)))('string_bit').leave_whitespace()
unquoted_spaceless_cond_safe_templated_string = OneOrMore(templated_element | string_bit_cond_safe)('value').set_name('Inline Templated String')
'A nonempty templated string, without wrapping quotes, without any spaces in the literal parts, (nb. containing sources and items may have spaces)'

cond_safe_templated_string = optional_white + Group((quoted_templated_string | unquoted_spaceless_cond_safe_templated_string).set_name('Templated String')) + optional_white
comparison = Group(cond_safe_templated_string + comp_op - cond_safe_templated_string)('comparison').set_name('Comparison')

# ======== Root Conditions: Predicate

pred_category = (Keyword('WHITE') | Keyword('EMPTY') | Keyword('TRUE') | Keyword('FALSE') | Keyword('BOOL') | Keyword('INT') | Keyword('FLOAT'))('pred_category').set_name('Predicate Category')
pred_is_category = Combine(Keyword('IS') - Opt(Keyword('NOT'))('not') + pred_category, adjacent=False)
predicate = Group(cond_safe_templated_string + pred_is_category)('predicate').set_name('Predicate')

# ======== Root Conditions: Aggregate predicate

simple_agg_predicate = Group(Opt(Keyword('NOT'))('not') + (Keyword('ANYTHING') | Keyword('NOTHING'))('type'))('simple_agg_predicate')
agg_predicate = Group(simple_agg_predicate)('agg_predicate').set_name('Aggregate Predicate')

# ======== Composite Conditions

kw_and = SuppKeyword('and', caseless=True)
kw_or  = SuppKeyword('or', caseless=True)
kw_not = Keyword('not', caseless=True)

root_condition      = (left_paren + condition + right_paren).set_name('Nested Condition') | (agg_predicate | predicate | comparison).set_name('Root Condition')
cond_negation       = (Group(OneOrMore(kw_not) - root_condition)('negation') | root_condition).set_name('Condition')
cond_conjunction    = (Group(cond_negation + OneOrMore(kw_and - cond_negation))('conjunction') | cond_negation).set_name('Condition')
condition         <<= (Group(cond_conjunction + OneOrMore(kw_or - cond_conjunction))('disjunction') | cond_conjunction).set_name('Condition')


# ======================== Templated Element: Conditionals

kw_if   = SuppKeyword('if', caseless=True)
kw_else = SuppKeyword('else', caseless=True)

conditional_body = cond_safe_templated_string('case_if') + kw_if + condition('condition') + kw_else + cond_safe_templated_string('case_else')
conditional = Group( left_brace + question_mark - conditional_body + right_brace )('conditional').set_name('Templated Conditional')

# ======================== Templated Element

templated_element <<= FollowedBy(left_brace) - (te_special | te_script | conditional | item | source)


# ======================== Group Mode

gm_multiply_flag = Opt(Literal('*')('multiply_flag'))
gm_strictness = Combine(ZeroOrMore('!'))('strictness')
def may_be_parenthesized(expr: ParserElement):
    # Utility to catch old IF(()) and SWITCH(()) syntax
    return ((left_paren + expr + right_paren) | expr).set_name(expr.customName)

# ======== Group Mode: Split Mode

gm_split_row = Group( left_paren + pos_integer('size') - right_paren + gm_strictness )('split_row').set_name('Splitmode Row')
gm_split_divide = Group( Suppress('/') - pos_integer('count') + gm_strictness )('split_divide').set_name('Splitmode Divide')
gm_split_modulo = Group( Suppress('%') - pos_integer('modulo') + gm_strictness )('split_modulo').set_name('Splitmode Modulo')
gm_split_column = Group( Suppress('\\') - pos_integer('size') + gm_strictness )('split_column').set_name('Splitmode Column')
gm_split_interval = Group( Suppress('#') - (interval('interval') | integer('index')) + gm_strictness )('split_interval').set_name('Splitmode Interval')
gm_split_one = Group( Suppress('.') + gm_strictness )('split_one').set_name('Splitmode One')
gm_split_head = Group( Suppress('^') + gm_strictness )('split_head').set_name('Splitmode Head')
gm_split_tail = Group( Suppress('$') + gm_strictness )('split_tail').set_name('Splitmode Tail')

gm_single_split = (gm_split_one | gm_split_row | gm_split_divide | gm_split_modulo | gm_split_column | gm_split_interval | gm_split_head | gm_split_tail).set_name('Splitmode')
gm_split = ZeroOrMore(gm_single_split)('split')

# ======== Group Mode: Mid Mode

gm_mid_if       = Group( SuppKeyword('IF') - left_paren + may_be_parenthesized(condition) + right_paren + gm_strictness )('mid_if').set_name('Midmode IF')
gm_mid_sort_by  = Group( SuppKeyword('SORT BY') - may_be_parenthesized(Group(delimited_list(Combine(Opt('+') + pos_integer)))('indices')) )('mid_sort_by').set_name('Midmode SORT BY')

gm_mid_group_by_mode = (Keyword('GROUP') | Keyword('COLLECT') | Keyword('EXTRACT'))('mode')
gm_mid_group_by = Group( gm_mid_group_by_mode - SuppKeyword('BY') + may_be_parenthesized(Group(delimited_list(pos_integer))('indices')) )('mid_group_by').set_name('Midmode GROUP BY')

gm_mid = Opt(gm_mid_if) + Opt(gm_mid_sort_by) + Opt(gm_mid_group_by)

# ======== Group Mode: Assign Mode

gm_assign_random = Group( gm_multiply_flag + question_mark )('assign_random').set_name('Assignmode Random')
gm_assign_switch_body = may_be_parenthesized( Group(delimited_list(condition, '|'))('conditions').set_name('Sequence of Conditions') )
gm_assign_switch = Group( gm_multiply_flag + SuppKeyword('SWITCH') - left_paren + gm_assign_switch_body + right_paren + gm_strictness )('assign_switch').set_name('Assignmode SWITCH')
gm_assign_default = Group( gm_multiply_flag )('assign_default').set_name('Assignmode Default')

# NOTE: `gm_assign_default` may match an empty string, so this may also
gm_assign = (gm_assign_random | gm_assign_switch | gm_assign_default)('assign').set_name('Assignmode')

# ======== Group Mode

groupmode = Group(gm_split + gm_mid + gm_assign)('groupmode').set_name('Groupmode')
groupmode_and_remainder = groupmode + Regex('.*', flags=re.S)('remainder')


# ======================== Scripts

simple_origin = Group(Group(quoted_templated_string)('quoted_simple_origin') | origin_safe_templated_string)('simple_origin').set_name('Simple Origin')
simple_pipe = Group(Opt(groupmode('groupmode')) + identifier('pipe_name') + Opt(argument_list('args')))('simple_pipe').set_name('Simple Pipe')
simple_segment = Group((double_chevron - simple_origin) | (chevron - (simple_pipe | Group(Empty())('nop'))))
simple_script <<= (simple_origin + Group(ZeroOrMore(simple_segment))('simple_segments')).set_name('Simple Script')



'''
Note to self about Rezbot Script's grammar and the current model:

The above grammar is currently used via three entry points:
    Given a string, interpret the entire thing as a TemplatedString
    Given a string, interpret the leading part as a GroupMode
    Given a string, interpret the entire thing as an Arguments object

That does not however cover the entire grammar.
There's places in code where some form of manual parsing is done, often in a naive way that does not
    account for recursion, escaping, grammar errors, or other conveniences that a precisely defined grammar gives.

At that point however, things get more complicated, as any attempt at grammaticising higher up
    the scripting language's structure hits the wall of ChoiceTree expansions being wielded.

ANALYSIS OF THE CURRENT NON-PYPARSING GRAMMARS RESPONSIBLE FOR PARSING A SCRIPT:
    1. The "butcher grammar", which does not care about the finer aspects of the script, merely cares about chopping it into [origin, pipe_chunk, pipe_chunk, ...]
        This is implemented via a manually written state machine parser in Pipeline.split_into_segments.
    2. Parse each "pipe chunk"'s leading GroupMode
    3. Then, for each "pipe chunk":
        1. Use FOUL TRICKERY to temporarily evacuate all triple-quoted and parenthesized substrings
        2. ChoiceTree expand
        3. Put triple-quoted and parenthesized substrings back
        Effectively, this is like a variant ChoiceTree grammar that acknowledges "ChoiceTree-invariant substrings"(!)
    4. Then a really simple .split() followed by a grammar parse turns each one into a (pipe_name, Arguments),
        or a recursive parse for parenthesized sub-pipelines.

Points 1 and 3 can each individually be improved by making a real grammar out of what is currently a manual ordeal.
Hpwever, these would be grammars acting independently of the main grammar, and would not simply slot into the current grammar.
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
