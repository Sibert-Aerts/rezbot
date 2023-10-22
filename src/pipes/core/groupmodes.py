import re
from typing import TypeVar
from random import choice
from pyparsing import ParseBaseException, ParseResults

from .logger import TerminalErrorLogException
from .conditions import Condition
from .context import Context, ItemScope
from . import grammar

# Pipe grouping syntax!

### Intro
# What happens here is how a pipe determines how different inputs are grouped when they are processed by pipes.
# In many pipes "grouping" makes no difference, pipes such as "convert" or "translate" simply act on each individual input regardless of how they are grouped.

# There are, however, some pipes where it does make a difference. Take for example the "join" pipe:

#   >> [alpha|beta|gamma|delta] -> join s=", "
# Output: alpha → alpha, beta, gamma, delta
#         beta
#         gamma
#         delta

#   >> [alpha|beta|gamma|delta] -> (2) join s=", "
# Output: alpha → alpha, beta
#         beta  → gamma, delta
#         gamma
#         delta

# The number of inputs it receives at once determine what its output looks like, and even how many outputs it produces!
# The other situation where group modes matter is when applying multiple pipes in parallel, like so:

#   >> [alpha|beta|gamma|delta] > (1) convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         ｂｅｔａ
#         𝔤𝔞𝔪𝔪𝔞
#         ｄｅｌｔａ

# The (1) tells the script to split the values into groups of 1 item each. Each of these groups of size 1 are then *alternately*
# fed into "convert fraktur" and "convert fullwidth", as you can see from the output. This should make the utility of grouping clear.
# Note: If we don't put the (1) there, it will assume the default group mode /1, which simply puts all values into one group and applies it
# to the first pipe of the parallel pipes, leaving the other pipe unused (e.g. in the example, all inputs would be converted to fraktur lettering.)


### Some quick syntax examples:

#   >> {foo} > (2) bar
# Means: Fetch output produced by the source named "foo" (which could be any number of strings) and feed it into the "bar" pipe in groups of 2.

# e.g. >> {words n=4} > (2) join s=" AND "
# Might produce the following 2 rows of output: "trousers AND presbyterian", "lettuce's AND africanism"

#   >> {foo} > (2) [bar|tox]
# Means: Fetch output from the source "foo", split it into groups of 2, feed the first group into "bar", the second into "tox", third into "bar", and so on.

# e.g. >> {words n=4} > (2) [join s=" AND " | join s=" OR "]
# Might produce the 2 rows of output: "derides AND clambered", "swatting OR quays"

#   >> {foo} > *(2) [bar|tox]
# Means: Fetch output from source "foo", split it in groups of 2, feed one copy of the first group into "bar" and another copy into "tox",
# feed one copy of the second group into "bar" and another copy into "tox", and so on.

# e.g. >> {words n=4} > *(2) [join s=" AND " | join s=" OR "]
# Might produce these 4 outputs: "horseflies AND retool", "horseflies OR retool", "possum AND ducts", "possum OR ducts"


### All syntax rules:

## Multiply option:
# Given by adding an asterisk* before the group mode:
#   >> {source} > * >>>> [pipe1|pipe2|...]
# (With >>>> representing a group mode)
# *Each* group of input is fed into *each* of the simultaneous pipes (pipe1, pipe2, etc)
# Resulting in (number of groups) × (number of simultaneous pipes) pipe applications total, which is usually a lot.

# Strict option:
# Given by adding an exclamation mark after the group mode!
#   >> {source} > >>>> ! [pipe1|pipe2|...]
# (With >>>> representing a group mode)
# This option tells the group mode to simply throw away input values that don't "fit" according to the group mode.
# What it specifically throws away (if anything) depends on both the type of group mode, and the number of values it's grouping.

# Very Strict option:
# Given by adding two exclamation marks after the group mode!!
#   >> {source} > >>>> !! [pipe1|pipe2|...]
# (With >>>> representing a group mode)
# The group mode raises a terminal error if the input values don't "fit" according to the group mode, cutting script execution short completely.
# This is useful if there is semantic significance to the structure of the values you are grouping on.


## Default grouping (Divide grouping special case):
#   >> {source} > [pipe1|pipe2|...|pipex]
# Feeds all input to pipe1 as a single group, ignoring pipe2 through pipex.
# Identical to Divide grouping with N as 1, i.e. "/1".
#   >> [alpha|beta|gamma|delta] > convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔟𝔢𝔱𝔞
#         𝔤𝔞𝔪𝔪𝔞
#         𝔡𝔢𝔩𝔱𝔞

## Row grouping:
#   >> {source} > (N) [pipe1|pipe2|...|pipeX]
# Groups the first N inputs and feeds them to pipe1, the second N inputs to pipe2, ..., the X+1th group of N inputs to pipe1 again, etc.
# If the number of inputs doesn't divide by N:
#   • If the strict option is given: It will throw away the remaining less-than-N items.
#   • If N starts with a '0': It will pad out the last group with empty strings to make N items.
#   • Otherwise: The last group will simply contain less than N items.
# If your inputs are a row-first matrix, and given N the size of a row (i.e. number of columns) in the matrix, this groups all the rows.
#   >> [alpha|beta|gamma|delta|epsilon|phi] > (3) convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔟𝔢𝔱𝔞
#         𝔤𝔞𝔪𝔪𝔞
#         ｄｅｌｔａ
#         ｅｐｓｉｌｏｎ
#         ｐｈｉ

## Divide grouping:
#   >> {source} > /N [pipe1|pipe2|...|pipex]
# Splits the input into N equally sized* groups of sequential inputs, and feeds the first group into pipe1, second into pipe2, etc.
# Call M the number of inputs to be grouped. In case M is not divisible by N:
#   • If the strict option is given: Input is split into groups of floor(M/N), throwing away extraneous items.
#   • If N starts with '0': Input is split into groups of ceil(M/N), and the last group is padded out with empty strings.
#   • If N doesn't start with '0': Input is split into groups of ceil(M/N), except the last groups which may contain less items or even be empty.
# If your inputs are a row-first matrix, and given N the size of a column (i.e. number of rows) in the matrix, this groups all the rows.
#   >> [alpha|beta|gamma|delta|epsilon|phi] > /3 convert [fraktur|fullwidth|smallcaps]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔟𝔢𝔱𝔞
#         ｇａｍｍａ
#         ｄｅｌｔａ
#         ᴇᴘsɪʟᴏɴ
#         ᴘʜɪ

## Modulo grouping:
#   >> {source} > %N [pipe1|pipe2|...|pipex]
# Splits the input into N equally sized* groups of inputs that have the same index modulo N. This changes the order of the values, even if the pipe is a NOP.
# Behaves identical to Divide grouping otherwise, including N starting with '0' to pad each group out to equal size, and strictness rules.
# If your inputs are a row-first matrix, and given N the size of a row (i.e. number of columns) in the matrix, this groups all the columns.
#   >> [alpha|beta|gamma|delta|epsilon|phi] > %3 convert [fraktur|fullwidth|smallcaps]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔡𝔢𝔩𝔱𝔞
#         ｂｅｔａ
#         ｅｐｓｉｌｏｎ
#         ɢᴀᴍᴍᴀ
#         ᴘʜɪ

## Column grouping:
#   >> {source} > \N [pipe1|pipe2|...|pipex]
# Splits the input into groups of size N* by applying Modulo(M/N) with M the number of items, and (/) rounding up or down depending on padding or strictness.
# There's no good intuitive explanation here, just the mathematical one:
# If your inputs are a row-first matrix, and given N the size of a column (i.e. number of rows) in the matrix, this groups all the columns.
#   >> [alpha|beta|gamma|delta|epsilon|phi] > \3 convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔤𝔞𝔪𝔪𝔞
#         𝔢𝔭𝔰𝔦𝔩𝔬𝔫
#         ｂｅｔａ
#         ｄｅｌｔａ
#         ｐｈｉ

## Intermission: Column and Modulo
# If your number of inputs is a multiple of N, then (%N NOP) and (\N NOP) act as inverse permutations on your inputs.
# This means applying a %N after a \N (or a \N after a %N) when you know the number of items is constant will restore the items to their "original order".
# This is because (%N NOP) is a matrix transpose on a row-first matrix with N columns, and (\N NOP) is a transpose of row-first a matrix with N rows.
#   >> [alpha|beta|gamma|delta|epsilon|phi] > \3 convert [fraktur|fullwidth] > %3
# Output: 𝔞𝔩𝔭𝔥𝔞
#         ｂｅｔａ
#         𝔤𝔞𝔪𝔪𝔞
#         ｄｅｌｔａ
#         𝔢𝔭𝔰𝔦𝔩𝔬𝔫
#         ｐｈｉ

## Interval grouping:
#   >> {source} > #A:B [pipe1|pipe2|...]
# Groups inputs from index A up to, but NOT including, index B as one group and applies them ONLY to pipe1, unless the multiply option
# is set, then it'll apply the selected range to all pipes.
# If the strict option is given, the items outside the selected range are thrown away, otherwise they are left in place, unaffected.
# A and B can be negative, and follows python's negative index logic. (i.e. a[-i] == a[len(a)-i])
# A and B may also use '-0' to indicate the end of the list of inputs.
# If A is left empty it is assumed to be 0  (i.e. :B is the same as 0:B)
# If B is left empty it is assumed to be -0 (i.e. A: is the same as A:-0)
# If both are left empty it gives a syntax error since it would imply a meaningless grouping.
#   >> [alpha|beta|gamma|delta] > #1:3 convert fullwidth
# Output: alpha
#         ｂｅｔａ
#         ｇａｍｍａ
#         delta

## Index grouping (Interval special case):
#   >> {source} > #A [pipe1|pipe2|...]
# Same behaviour as Interval grouping with B := A+1. (Except if A is -0 then B also is -0)
#   >> [alpha|beta|gamma|delta] > #2 convert fullwidth
# Output: alpha
#         beta
#         ｇａｍｍａ
#         delta

class GroupModeError(ValueError):
    '''Something went wrong while parsing or applying a GroupMode.'''
    pass

T = TypeVar('T')
P = TypeVar('P')

################ SPLITMODES ################

class SplitMode:
    '''An object representing a function that turns a list of item into smaller lists.'''
    def __init__(self, strictness: int):
        self.strictness = strictness

    @staticmethod
    def from_parsed(result: ParseResults):
        strictness = len(result.get('strictness', ''))
        match result._name:
            case 'split_row':
                return Row(strictness, int(result['size']), result['size'].startswith('0'))
            case 'split_modulo':
                return Modulo(strictness, int(result['modulo']), result['modulo'].startswith('0'))
            case 'split_divide':
                return Divide(strictness, int(result['count']), result['count'].startswith('0'))
            case 'split_column':
                return Column(strictness, int(result['size']), result['size'].startswith('0'))
            case 'split_interval':
                if 'interval' in result:
                    interval = result['interval']
                    start, end = interval.get('start', ''), interval.get('end', '')
                else:
                    start = result['index']
                    end = None
                return Interval(strictness, start, end)
            case bad_name:
                raise Exception()

    @staticmethod
    def from_string(string: str):
        return SplitMode.from_parsed(grammar.gm_single_split.parse_string(string, parse_all=True)[0])

    def __str__(self):
        if self.strictness == 0: return ''
        if self.strictness == 1: return 'STRICT '
        if self.strictness == 2: return 'VERY STRICT '

    def apply(self, items: list[P]) -> list[tuple[list[P], bool]]:
        raise NotImplementedError()


class Row(SplitMode):
    def __init__(self, strictness: int, size: int, padding: bool):
        super().__init__(strictness)
        if size < 1: raise GroupModeError('Row size must be at least 1.')
        self.size = size
        self.padding = padding

    def __str__(self):
        return '{}ROWS SIZE {}{}'.format(super().__str__(), self.size, ' WITH PADDING' if self.padding else '')

    def apply(self, items: list[P]) -> list[tuple[list[P], bool]]:
        length = len(items)     # The number of items we want to split
        size = self.size        # The size of each group (GIVEN)
        count= length //size    # The minimal number of groups we have to split it into
        rest = length % size    # The number of leftover items if we were to split into the minimal number of groups

        ## Handle the fact that our last group does not contain the number of items we wanted:
        if rest:
            ## Very strict: Raise an error
            if self.strictness == 2:
                raise GroupModeError('Could not strictly group into rows size %d!' % size)
            ## Strict: Throw away the last group
            elif self.strictness == 1:
                length = count*size
                items = items[:length]
            ## Padding: The last group is padded out with (size-rest) default P's (i.e. empty strings or lists).
            elif self.padding:
                items += [ type(items[0])() ] * (size - rest)
                count += 1
                length = count*size
                rest = 0
            ## Default: The last group only contains (rest) items.
            # NOTE: Padding fills up the "empty spots" from the Default behaviour.

        ## Special case: Items is an empty list.
        if length == 0:
            ## Very strict: Get angry
            if self.strictness == 2: raise GroupModeError('No items to strictly group!')
            ## Strict: Do nothing.
            if self.strictness == 1: return []
            ## Non-strict: Assume the empty list as our only group.
            return [([], False)]

        ## Slice our input into groups of the desired size.
        return [(items[i: i+size], False) for i in range(0, length, size)]

class Divide(SplitMode):
    def __init__(self, strictness, count, padding):
        super().__init__(strictness)
        if count < 1: raise GroupModeError('Divide count must be at least 1.')
        self.count = count
        self.padding = padding

    def __str__(self):
        return '{}DIVIDE INTO {}{}'.format(super().__str__(), self.count, ' WITH PADDING' if self.padding else '')

    def apply(self, items: list[P]) -> list[tuple[list[P], bool]]:
        length = len(items)     # The number of items we want to split
        count = self.count      # The number of groups we want to split it into (GIVEN)
        size = length //count   # The minimal size of each group
        rest = length % count   # The number of leftover items if we were to split into groups of minimal size

        ## Deal with the fact that we can't split the items into equal sizes.
        if rest:
            ## Very strict: Raise an error
            if self.strictness == 2:
                raise GroupModeError('Could not strictly divide into %d rows!' % count)
            ## Strict: Throw away the tail end to make the length fit
            elif self.strictness == 1:
                length = size*count
                items = items[:length]
                rest = 0
            ## Padding: The last group is padded out.
            elif self.padding:
                items += [ type(items[0])() ] * (count - rest)
                size += 1
                length = size*count
                rest = 0
            ## Default: The first (rest) groups contain 1 more item than the remaining (count-rest) groups.
            # NOTE: This means padding does NOT fill in the "empty spots" from the default behaviour!
            # The significance of this is negligible though since any scenario where rest>0 is probably
            # a scenario where the specific alignment/grouping of items is meaningless, so we can just do what's easiest for us.

        ## Special case: Empty list of items.
        if length == 0:
            ## Very strict: Get angry
            if self.strictness == 2: raise GroupModeError('No items to strictly group!')
            ## Strict: Do nothing.
            if self.strictness == 1: return []
            ## Default: Split the empty list into (count) empty lists
            return [([], False) for i in range(count)]

        out = []
        ## Slice our inputs into the desired number of groups
        for i in range(self.count):
            # The min(rest, i) and min(rest, i+1) ensure that the first (rest) slices get 1 extra value.
            left =    i   * size + min(rest, i)
            right = (i+1) * size + min(rest, i+1)
            out.append( (items[left:right], False) )
        return out

class Modulo(SplitMode):
    def __init__(self, strictness, modulo, padding):
        super().__init__(strictness)
        if modulo < 1: raise GroupModeError('Modulo value must be at least 1.')
        self.modulo = modulo
        self.padding = padding

    def __str__(self):
        return '{}MODULO {}{}'.format(super().__str__(), self.modulo, ' WITH PADDING' if self.padding else '')

    def apply(self, items: list[P]) -> list[tuple[list[P], bool]]:
        length = len(items)    # The number of items we want to split
        count = self.modulo     # The number of groups we want to split it into (GIVEN)
        size = length //count   # The minimal size of each group
        rest = length % count   # The number of leftover items if we were to split into groups of minimal size

        ## Deal with the fact that we can't split the items into equal sizes.
        if rest:
            ## Very strict: Raise an error
            if self.strictness == 2:
                raise GroupModeError('Could not strictly group into %d columns!' % count)
            ## Strict: Throw away the tail end to make the length fit
            elif self.strictness == 1:
                length = size*count
                items = items[:length]
                rest = 0
            ## Padding: The last (count-rest) groups are padded out with one empty string.
            if self.padding:
                items += [ type(items[0])() ] * (count - rest)
                size += 1
                length = size*count
                rest = 0
            ## Default: The first (rest) groups contain 1 item more than the others.
            # NOTE: Padding and Default behaviour are "equivalent" here.

        ## Special case: Empty list of items; identical to Divide
        if length == 0:
            if self.strictness == 2: raise GroupModeError('No items to strictly group!')
            if self.strictness == 1: return []
            return [([], False) for i in range(count)]

        out = []
        ## Slice into groups of items whose indices are x+i where x is a multiple of (count)
        for i in range(0, count):
            vals = [items[x+i] for x in range(0, length, count) if x+i < length]
            out.append((vals, False))
        return out

class Column(SplitMode):
    def __init__(self, strictness, size, padding):
        super().__init__(strictness)
        if size < 1: raise GroupModeError('Column size must be at least 1.')
        self.size = size
        self.padding = padding

    def __str__(self):
        return '{}COLUMNS SIZE {}{}'.format(super().__str__(), self.size, ' WITH PADDING' if self.padding else '')

    def apply(self, items: list[P]) -> list[tuple[list[P], bool]]:
        length = len(items)     # The number of items we want to split
        size = self.size        # The size of each group (GIVEN)
        count= length //size    # The minimal number of groups we have to split it into
        rest = length % size    # The number of leftover items if we were to split into the minimal number of groups

        ## Deal with the fact that we can't split the items into equal sizes.
        if rest:
            ## Very strict: Raise an error
            if self.strictness == 2:
                raise GroupModeError('Could not strictly group into columns size %d!' % size)
            ## Strict: Throw away the tail end to make the length fit
            elif self.strictness == 1:
                length = size*count
                items = items[:length]
                rest = 0
            ## Padding: Pad out the tail so the last (size-rest) groups contain one empty string.
            if self.padding:
                items += [ type(items[0])() ] * (size - rest)
                count += 1
                length = size*count
                rest = 0
            ## Default: The last (size-rest) groups contain 1 less item.
            # NOTE: Padding fills up the "empty spots" from the Default behaviour.

        ## Special case: Empty list of items; identical to Row
        if length == 0:
            if self.strictness == 2: raise GroupModeError('No items to strictly group!')
            if self.strictness == 1: return []
            else: return [([], False)]

        out = []
        ## Slice into groups of items whose indices are x+i where x is a multiple of (count)
        for i in range(0, count):
            vals = [items[x+i] for x in range(0, length, count) if x+i < length]
            out.append((vals, False))
        return out

class Interval(SplitMode):
    # Magic object
    END = 'END'

    def __init__(self, strictness: int, start: str, end: str):
        super().__init__(strictness)
        ## start is empty: START
        ## start is -0:    END
        self.start = 0 if not start else Interval.END if start == '-0' else int(start)

        ## end is None: (start+1) (indicated as keeping it None)
        ## end is empty or -0: END
        self.end = None if end is None else Interval.END if end in ['-0', ''] else int(end)

    def __str__(self):
        if self.end is None: return '{}INDEX AT {}'.format(super().__str__(), self.start)
        return '{}INTERVAL FROM {} TO {}'.format(super().__str__(), self.start, self.end)

    def apply(self, items: list[P]) -> list[tuple[list[P], bool]]:
        length = len(items)

        if length == 0: return [(items, False)]

        ## Determine the effective start
        start = self.start if self.start != Interval.END else length

        ## Determine the effective end
        if self.end is Interval.END:
            end = length
        elif self.end is None:
            if self.start == -1:             # Writing #-1 is equivalent to #-1:-0 i.e. The last element
                end = length
            elif self.start is Interval.END: # Writing #-0 is equivalent to #-0:-0 i.e. The empty tail
                end = length
            else: end = start + 1
        else:
            end = self.end

        ## Manually adjust the indices to be non-negative (may be larger than length)
        while start < 0: start += length
        while end < 0: end += length
        ## Special case: If we're targeting a negative range, simply target the empty range [start:start]
        if end < start: end = start

        ## Non-strict: Ignore the items outside of the selected range.
        if not self.strictness:
            return [
                (items[0: start], True),
                (items[start: end], False),
                (items[end: length], True),
            ]
        ## Very strict: Get angry when our range does not exactly cover the list of items
        elif self.strictness == 2 and (start > 0 or end != length):
            raise GroupModeError('The range does not strictly fit the set of items!')
        ## Strict: Throw away the items outside of the selected range.
        return [(items[start: end], False)]

################ ASSIGNMODES ################

class AssignMode:
    '''An object representing a function that takes lists of items and assigns them to pipes picked from a list.'''
    def __init__(self, multiply):
        self.multiply = multiply

    @staticmethod
    def from_parsed(result: ParseResults):
        multiply = bool(result.get('multiply_flag'))
        match result._name:
            case 'assign_random':
                return Random(multiply)
            case 'assign_default':
                return DefaultAssign(multiply)
            case 'assign_switch':
                strictness = len(result.get('strictness', ''))
                # TODO: Handle/repackage/distinguish Condition parse errors?
                conditions = [Condition.from_parsed(cond) for cond in result['conditions']]
                return Switch(multiply, strictness, conditions)
            case bad_name:
                raise Exception()

    @staticmethod
    def from_string(string: str):
        return AssignMode.from_parsed(grammar.gm_assign.parse_string(string, parse_all=True)[0])


    def __str__(self):
        return 'MULTIPLY ' if self.multiply else ''

    def is_trivial(self):
        ''' A method that returns False unless the AssignMode is DefaultAssign(multiply=False) '''
        return False

    async def apply(self, tuples: list[tuple[T, bool]], pipes: list[P], context: Context, scope: ItemScope) -> list[tuple[T, P]]:
        raise NotImplementedError()


class DefaultAssign(AssignMode):
    '''Assign mode that sends the n'th group to the (n%P)'th pipe with P the number of pipes.'''
    def __str__(self):
        return super().__str__() + 'DEFAULT'

    def is_trivial(self):
        return not self.multiply

    async def apply(self, tuples: list[tuple[T, bool]], pipes: list[P], *args) -> list[tuple[T, P | None]]:
        out = []
        i = 0
        l = len(pipes)
        for items, ignore in tuples:
            if ignore:
                out.append((items, None))
            elif self.multiply:
                out += [(items, pipe) for pipe in pipes]
            else:
                out.append((items, pipes[i%l]))
                i += 1
        return out

class LegacySwitch(AssignMode):
    '''Assign mode that assigns groups to pipes based on logical conditions that each group meets. Crappy legacy parsing.'''

    class RootCondition():
        type1 = re.compile(r'^(-?\d+)\s*(!)?=\s*(-?\d+)$')                # <index> = <index>
        type2 = re.compile(r'^(-?\d+)\s*(!)?=\s*"([^"]*)"$')              # <index> = "<literal>"
        type3 = re.compile(r'^(-?\d+)\s+(NOT )?LIKE\s+/([^/]*)/$', re.I)  # <index> [NOT] LIKE /<regex>/
        type4 = re.compile(r'^((NO|SOME|ANY)THING)$', re.I)               # NOTHING or SOMETHING or ANYTHING
        def __init__(self, cond: str):
            m = re.match(self.type1, cond)
            if m is not None:
                self.type = 1
                l, i, r = m.groups()
                self.left = int(l)
                self.inverse = (i == '!')
                self.right = int(r)
                return
            m = re.match(self.type2, cond)
            if m is not None:
                self.type = 2
                l, i, r = m.groups()
                self.left = int(l)
                self.inverse = (i == '!')
                self.right = r
                return
            m = re.match(self.type3, cond)
            if m is not None:
                self.type = 3
                l, i, r = m.groups()
                self.left = int(l)
                self.inverse = (i == 'NOT ')
                self.re_str = r
                self.re = re.compile(r)
                return
            m = re.match(self.type4, cond)
            if m is not None:
                self.type = 4
                self.inverse = (m.group()[:2] == 'NO ')
                return
            if cond:
                raise GroupModeError('Invalid condition `{}`'.format(cond))
            raise GroupModeError('Empty condition.')

        def __str__(self):
            if self.type == 1: return '{} {}= {}'.format(self.left, '!' if self.inverse else '', self.right)
            if self.type == 2: return '{} {}= "{}"'.format(self.left, '!' if self.inverse else '', self.right)
            if self.type == 3: return '{} {}LIKE /{}/'.format(self.left, 'NOT ' if self.inverse else '', self.re_str)
            if self.type == 4: return '{}THING'.format('NO' if self.inverse else 'ANY')

        def check(self, values: list[str]) -> bool:
            try:
                if self.type == 1:
                    return self.inverse ^ (values[self.left] == values[self.right])
                if self.type == 2:
                    return self.inverse ^ (values[self.left] == self.right)
                if self.type == 3:
                    return self.inverse ^ (re.search(self.re, values[self.left]) is not None)
                if self.type == 4:
                    return self.inverse ^ (len(values) > 0)
            except IndexError:
                raise GroupModeError('Index out of range in condition `{}`'.format(self))

    class Condition():
        def __init__(self, cond):
            # This is bad, bad parsing, which is limited in complexity and totally ignores quotation marks and such
            disj = cond.split(' OR ')
            conjs = [conj.split(' AND ') for conj in disj]
            self.conds = [[LegacySwitch.RootCondition(cond.strip()) for cond in conj] for conj in conjs]

        def __str__(self):
            return ' OR '.join(' AND '.join(str(cond) for cond in conj) for conj in self.conds)

        def check(self, values):
            return any(all(cond.check(values) for cond in conj) for conj in self.conds)

    def __init__(self, multiply, strictness, conditions):
        super().__init__(multiply)
        self.strictness = strictness
        # TODO: Parse these more smartly
        self.conditions = [self.Condition(c.strip()) for c in conditions.split('|')]

    def __str__(self):
        return '{}SWITCH {{ {} }}'.format(super().__str__(), ' | '.join(str(c) for c in self.conditions))

    async def apply(self, tuples: list[tuple[T, bool]], pipes: list[P], *args) -> list[tuple[T, P | None]]:
        #### Sends ALL VALUES as a single group to the FIRST pipe whose corresponding condition succeeds
        ## Multiply:    Send all values to EACH pipe whose condition succeeds
        ## Non-strict:  If all conditions fail, either pass to the (n+1)th pipe or leave values unaffected if it is not present
        ## Strict:      If all conditions fail, destroy the values. Raise an error if an (n+1)th pipe was given.
        ## Very strict: If all conditions fail, raise an error. No (n+1)th pipe allowed either.

        c = len(self.conditions)
        p = len(pipes)
        if p != c:
            if self.strictness:
                raise GroupModeError('Strict condition error: Unmatched number of cases and parallel pipes; should be equal.')
            elif p != c+1:
                raise GroupModeError('Unmatched number of cases and parallel pipes; number of pipes should be equal or one more.')

        overflow_pipe_given = (p == c+1)
        # c is the number of conditions, p is the number of pipes to sort it in (either c or c+1)

        conditions_and_pipes = tuple(zip(self.conditions, pipes))

        if not self.multiply:
            out = []
            for values, ignore in tuples:
                if ignore:
                    out.append((values, None)); continue

                ## Run over all the conditions to see which one hits first and go with that pipe
                for condition, pipe in conditions_and_pipes:
                    if condition.check(values):
                        out.append((values, pipe))
                        break
                else:
                ## None of the conditions matched: Pick a "default" case
                    if overflow_pipe_given:
                        out.append((values, pipes[-1]))
                    elif not self.strictness:
                        out.append((values, None))
                    elif self.strictness == 1:
                        pass # Throw this list of values away!
                    elif self.strictness == 2:
                        print('VERY STRICT SWITCH ERROR:')
                        print('VALUES: ', values)
                        print('CASES: ' + str(self))
                        raise GroupModeError('Very strict switch error: Default case was reached!')
            return out

        else: ## Multiply
            out = []
            for values, ignore in tuples:
                if ignore:
                    out.append((values, None)); continue

                out += [ (values, pipe) for (condition, pipe) in conditions_and_pipes if condition.check(values) ]
                if overflow_pipe_given: out.append( (values, pipes[-1]) )
            return out

class Switch(AssignMode):
    '''Assign mode that assigns groups to pipes based on logical conditions that each group meets.'''

    def __init__(self, multiply: bool, strictness: int, conditions: list[Condition]):
        super().__init__(multiply)
        self.strictness = strictness
        self.conditions = conditions

    @staticmethod
    def from_regex_groups(multiply, strictness, conditions_str: str):
        conditions = []
        for cond_str in conditions_str.split('|'):
            try:
                conditions.append(Condition.from_string(cond_str.strip()))
            except ParseBaseException as e:
                raise GroupModeError(f'ParseBaseException while parsing condition `{cond_str}`.')
            except TerminalErrorLogException as e:
                # TODO: Carry errors along here?
                errors = e.errors
                raise GroupModeError(f'Some errors while parsing condition `{cond_str}`.')
        return Switch(multiply, strictness, conditions)

    def __str__(self):
        return '{}SWITCH ({})'.format(super().__str__(), ' | '.join(str(c) for c in self.conditions))

    async def apply(self, tuples: list[tuple[T, bool]], pipes: list[P], context: Context, parent_scope: ItemScope) -> list[tuple[T, P | None]]:
        #### Sends ALL VALUES as a single group to the FIRST pipe whose corresponding condition succeeds
        ## Multiply:    Send all values to EACH pipe whose condition succeeds
        ## Non-strict:  If all conditions fail, either pass to the (n+1)th pipe or leave values unaffected if it is not present
        ## Strict:      If all conditions fail, destroy the values. Raise an error if an (n+1)th pipe was given.
        ## Very strict: If all conditions fail, raise an error. No (n+1)th pipe allowed either.

        c = len(self.conditions)
        p = len(pipes)
        if p != c:
            if self.strictness:
                raise GroupModeError('Strict condition error: Unmatched number of cases and parallel pipes; should be equal.')
            elif p != c+1:
                raise GroupModeError('Unmatched number of cases and parallel pipes; number of pipes should be equal or one more.')

        overflow_pipe_given = (p == c+1)
        # c is the number of conditions, p is the number of pipes to sort it in (either c or c+1)

        if not self.multiply:
            out = []
            for items, ignore in tuples:
                if ignore:
                    out.append((items, None))
                    continue

                ## Run over all the conditions to see which one hits first and go with that pipe
                for condition, pipe in zip(self.conditions, pipes):
                    scope = ItemScope(parent_scope, items)
                    try:
                        if await condition.evaluate(context, scope):
                            out.append((items, pipe))
                            break
                    except TerminalErrorLogException as e:
                        # TODO: Carry errors along there
                        errors = e.errors
                        raise GroupModeError(f'Error while evaluating condition `{condition}`.')
                else:
                ## None of the conditions matched: Pick a "default" case
                    if overflow_pipe_given:
                        out.append((items, pipes[-1]))
                    elif not self.strictness:
                        out.append((items, None))
                    elif self.strictness == 1:
                        pass # Throw this list of values away!
                    elif self.strictness == 2:
                        print('VERY STRICT SWITCH ERROR:')
                        print('VALUES: ', items)
                        print('CASES: ' + str(self))
                        raise GroupModeError('Very strict switch error: Default case was reached!')
            return out

        else: ## Multiply
            out = []
            for items, ignore in tuples:
                if ignore:
                    out.append((items, None))
                    continue
                scope = ItemScope(parent_scope, items)
                for (condition, pipe) in zip(self.conditions, pipes):
                    try:
                        if await condition.evaluate(context, scope):
                            out.append((items, pipe))
                    except TerminalErrorLogException as e:
                        # TODO: Carry errors along there
                        errors = e.errors
                        raise GroupModeError(f'Error while evaluating condition `{condition}`.')
                if overflow_pipe_given:
                    out.append((items, pipes[-1]))
            return out

class Random(AssignMode):
    '''Assign mode that sends each group to a random pipe.'''
    def __str__(self):
        return 'RANDOM'

    async def apply(self, tuples: list[tuple[T, bool]], pipes: list[P], *args) -> list[tuple[T, P | None]]:
        return [ (items, None if ignore else choice(pipes)) for (items, ignore) in tuples ]


################ MIDMODES ################

class LegacyIfMode:
    def __init__(self, cond: str, bangs: str):
        self.strict = bool(bangs)
        self.cond = LegacySwitch.Condition(cond.strip())

    def __str__(self):
        return 'IF ((' + str(self.cond) + '))' + ('!' if self.strict else '')

    def apply(self, tuples: list[tuple[T, bool]]) -> list[tuple[T, bool]]:
        out = []
        for (items, ignore) in tuples:
            if ignore:
                out.append((items, True))

            elif self.cond.check(items):
                out.append((items, False))

            elif not self.strict:
                out.append((items, True))

        return out

class IfMode:
    def __init__(self, condition: Condition, strictness: int):
        self.condition = condition
        self.strictness = strictness

    @staticmethod
    def from_parsed(result: ParseResults):
        condition = Condition.from_parsed(result[0])
        strictness = len(result.get('strictness'))
        return IfMode(condition, strictness)

    @staticmethod
    def from_string(string: str):
        return IfMode.from_parsed(grammar.gm_mid_if.parse_string(string, parse_all=True)[0])

    def __str__(self):
        return 'IF (' + str(self.condition) + ')' + '!' * self.strictness

    async def apply(self, tuples: list[tuple[T, bool]], context: Context, parent_scope: ItemScope) -> list[tuple[T, bool]]:
        out = []
        for (items, ignore) in tuples:
            if ignore:
                out.append((items, True))
                continue

            scope = ItemScope(parent_scope, items)
            if await self.condition.evaluate(context, scope):
                out.append((items, False))

            elif not self.strictness:
                out.append((items, True))

        return out

class GroupBy:
    # Stringy enum
    GROUP = 'GROUP'
    COLLECT = 'COLLECT'
    EXTRACT = 'EXTRACT'

    def __init__(self, mode: str, indices: str | list[int]):
        self.mode = GroupBy.GROUP if mode == 'GROUP' else GroupBy.COLLECT if mode == 'COLLECT' else GroupBy.EXTRACT

        # The set of indices
        if isinstance(indices, str):
            self.indices = [ int(i) for i in re.split(r'\s*,\s*', indices) ]
        else:
            self.indices = indices
        # The highest referenced index
        self.max_index = max(self.indices)
        # is_key[i] == True  ⇐⇒ i in indices
        self.is_key = [ (i in self.indices) for i in range(self.max_index + 1) ]

    @staticmethod
    def from_parsed(result: ParseResults):
        return GroupBy(result['mode'], [int(k) for k in result.get('indices')])

    @staticmethod
    def from_string(string: str):
        return GroupBy.from_parsed(grammar.gm_mid_group_by.parse_string(string, parse_all=True)[0])

    def __str__(self):
        return self.mode + ' BY ' + ', '.join(str(i) for i in self.indices)

    async def apply(self, tuples: list[tuple[T, bool]], context: Context, parent_scope: ItemScope) -> list[tuple[T, bool]]:
        out = []
        known_keys = {}

        for (items, ignore) in tuples:
            if ignore:
                out.append((items, True))
                continue

            n = len(items)
            if self.max_index >= n:
                raise GroupModeError('GROUP BY index out of range.')
            key = tuple(items[i] for i in self.indices)

            if key not in known_keys:
                ## COLLECT mode tells us to float the keys to the front
                ## EXTRACT mode tells us to get rid of the keys entirely
                if self.mode == GroupBy.GROUP:
                    values = items
                elif self.mode == GroupBy.COLLECT:
                    values = list(key) + [ items[i] for i in range(n) if i > self.max_index or not self.is_key[i] ]
                else:
                    values = [ items[i] for i in range(n) if i > self.max_index or not self.is_key[i] ]
                known_keys[key] = values
                out.append((values, False))

            else:
                ## COLLECT and EXTRACT modes tell us to filter out the keys on repeat items
                if self.mode == GroupBy.GROUP:
                    values = items
                else:
                    values = [ items[i] for i in range(n) if i > self.max_index or not self.is_key[i] ]
                known_keys[key].extend(values)

        return out

class SortBy:
    def __init__(self, indices: str | list[str]):
        # The set of indices
        self.indices = []
        nums = []
        if isinstance(indices, str):
            indices = re.split(r'\s*,\s*', indices)
        for index in indices:
            if index[0] == '+':
                i = int(index[1:])
                self.indices.append(i)
                nums.append(i)
            else:
                self.indices.append(int(index))

        self.max_index = max(self.indices)
        self.is_numeric = [(i in nums) for i in range(self.max_index+1)]

    @staticmethod
    def from_parsed(result: ParseResults):
        return SortBy(list(result.get('indices')))

    @staticmethod
    def from_string(string: str):
        return SortBy.from_parsed(grammar.gm_mid_sort_by.parse_string(string, parse_all=True)[0])

    def __str__(self):
        return 'SORT BY ' + ', '.join(('+'+str(i) if self.is_numeric[i] else str(i)) for i in self.indices)

    async def apply(self, tuples: list[tuple[T, bool]], context: Context, parent_scope: ItemScope) -> list[tuple[T, bool]]:
        head = []
        to_sort = []
        tail = []

        # Deal with ignored items: Float them all to before/after the sorted block of items
        #   depending on if they appear before/after the first non-ignored item.
        for (items, ignore) in tuples:
            if ignore: (head if not to_sort else tail).append((items, True))
            else: to_sort.append(items)

        def make_key(items):
            return tuple( items[i] if (i>self.max_index or not self.is_numeric[i]) else float(items[i]) for i in self.indices )
        to_sort.sort(key=make_key)

        return head + [(items, False) for items in to_sort] + tail


################ GROUPMODE ################

class GroupMode:
    '''A class that combines multiple SplitModes, MidModes and an AssignMode'''
    def __init__(self, split_modes: list[SplitMode], mid_modes: list[LegacyIfMode | IfMode | SortBy | GroupBy], assign_mode: AssignMode):
        self.split_modes= split_modes
        self.mid_modes = mid_modes
        self.assign_mode = assign_mode

    @staticmethod
    def from_parsed(result: ParseResults):
        ### Split modes
        split_modes = [SplitMode.from_parsed(split) for split in result.get('split')]
        mid_modes = []
        ### Mid modes
        if 'mid_if' in result:
            mid_modes.append(IfMode.from_parsed(result['mid_if']))
        if 'mid_sort_by' in result:
            mid_modes.append(SortBy.from_parsed(result['mid_sort_by']))
        if 'mid_group_by' in result:
            mid_modes.append(GroupBy.from_parsed(result['mid_group_by']))
        ### Assign modes
        assign_mode = AssignMode.from_parsed(result['assign'][0])
        return GroupMode(split_modes, mid_modes, assign_mode)

    @staticmethod
    def from_string_with_remainder(string: str) -> tuple['GroupMode', str]:
        result = grammar.groupmode_and_remainder.parse_string(string, parse_all=True)
        groupmode = GroupMode.from_parsed(result[0])
        remainder = result[1]
        return groupmode, remainder

    def __str__(self):
        if self.splits_trivially() and self.assign_mode.is_trivial():
            return 'TRIVIAL'
        split_modes = ' > '.join(str(s) for s in self.split_modes)
        mid_modes = (' × ' + ' > '.join(str(s) for s in self.mid_modes))
        assign_mode = ' × ' + str(self.assign_mode)
        return split_modes + mid_modes + assign_mode

    def splits_trivially(self):
        return not self.split_modes

    def is_singular(self):
        return not self.split_modes and not self.assign_mode.multiply

    async def apply(self, items: list[T], pipes: list[P], context: Context, scope: ItemScope) -> list[tuple[ list[T], P|None ]]:
        groups = [(items, False)]

        ## Apply the SplitModes
        for group_mode in self.split_modes:
            new_group = []
            for items, ignore in groups:
                if ignore: new_group.append( (items, True, None) )
                else: new_group.extend( group_mode.apply(items) )
            groups = new_group

        ## Apply the MidModes
        for mid_mode in self.mid_modes:
            groups = await mid_mode.apply(groups, context, scope)

        ## Apply the AssignMode
        return await self.assign_mode.apply(groups, pipes, context, scope)



# ================================ LEGACY PARSING CODE ================================
# The rest of this file is legacy parsing code, to be deleted as soon as the
#   replacement PyParsing-parsing has been demonstrated to encompass all nuances.

# pattern:
# optionally starting with a Multiply Flag: *
# then 0 or more instances of SplitModes:
#   (N)  |  %N  |  \N  |  /N  |  #N  |  #N:M
# each optionally followed by a Strictness flag: ! | !!

# optionally followed by an IfMode:
#   IF (( COND ))
# optionally followed by a strictness flag: !

# optionally followed by a SortBy:
#   SORT BY I, J, K, ...

# optionally followed by a GroupBy:
#   (GROUP|COLLECT|EXTRACT) BY I, J, K, ...

# optionally followed by a Multiply flag: *
# optionally followed by an AssignMode:
#   SWITCH(( COND1 | COND2 | COND3 | ... ))  |  ?
# each optionally followed by a Strictness flag: ! | !!

mul_pattern = re.compile(r'\s*(\*?)\s*')
#                              ^^^

row_pattern = re.compile(r'\(\s*(\d+)?\s*\)')
#                                ^^^
op_pattern = re.compile(r'(/|%|\\)\s*(\d+)?')
#                          ^^^^^^     ^^^
int_pattern = re.compile(r'#(-?\d*)(?:(?::|\.\.+)(-?\d*))?')
#                            ^^^^^                ^^^^^

if_pattern = re.compile(r'IF\s*\(\((.*?)\)\)\s*(!?)\s*', re.S)
#                                   ^^^        ^^

group_by_pattern = re.compile(r'\s*(GROUP|COLLECT|EXTRACT) BY\s*(\d+(?:\s*,\s*\d+)*)\s*')
#                                   ^^^^^^^^^^^^^^^^^^^^^        ^^^^^^^^^^^^^^^^^^
sort_by_pattern = re.compile(r'\s*SORT BY\s*(\+?\d+(?:\s*,\s*\+?\d+)*)\s*')
#                                            ^^^^^^^^^^^^^^^^^^^^^^^^

switch_pattern_DEPREC = re.compile(r'{(.*?)}\s*(!?!?)\s*', re.S)
#                                      ^^^      ^^^^
switch_pattern = re.compile(r'SWITCH\s*\(\((.*?)\)\)\s*(!?!?)\s*', re.S)
#                                           ^^^         ^^^^
rand_pattern = re.compile(r'\?')

strict_pattern = re.compile(r'\s*(!?!?)\s*')
#                                 ^^^^

op_dict = {'/': Divide, '\\': Column, '%': Modulo}

def legacy_parse(big_pipe: str) -> tuple[str, GroupMode]:
    '''Consumes the GroupMode from the start of a string and returns the GroupMode and remainder.'''
    ### HEAD MULTIPLY FLAG (for backwards compatibility)
    m = mul_pattern.match(big_pipe)
    multiply = (m[1] == '*')
    cropped = big_pipe[m.end():]

    split_modes: list[SplitMode] = []
    ### SPLITMODES (multiple consecutive ones!)
    while(True):
        ### MODE
        if (m := row_pattern.match(cropped)) is not None:
            split_mode = Row
            value = m[1]
        elif (m := op_pattern.match(cropped)) is not None:
            split_mode = op_dict[m[1]]
            value = m[2]
        elif (m := int_pattern.match(cropped)) is not None:
            split_mode = Interval
            start, end = m.groups()
        else:
            ## No (more) SplitMode found; Stop the loop!
            break

        ## One of the three regexes matched
        flag = m.group()
        cropped = cropped[m.end():]

        ### STRICTNESS (always matches)
        m = strict_pattern.match(cropped)
        # Strictness is given by the number of exclamation marks
        strictness = len(m.group(1))
        cropped = cropped[m.end():]

        ## Instantiate our SplitMode (this can raise GroupModeErrors)
        try:
            if split_mode in [Row, Column, Divide, Modulo]:
                if value is None: raise GroupModeError('Missing number.')
                padding = (value[0]=='0')
                value = int(value)
                split_mode = split_mode(strictness, value, padding)

            elif split_mode is Interval:
                split_mode = Interval(strictness, start, end)

        except GroupModeError as e:
            raise GroupModeError( 'In split mode `%s`: %s' % (flag, e) )

        split_modes.append(split_mode)

    mid_modes = []

    ### IFMODE (optional)
    m = if_pattern.match(cropped)
    if m is not None:
        mid_modes.append(LegacyIfMode(m[1], m[2]))
        cropped = cropped[m.end():]

    ### SORTBY MODE (optional)
    m = sort_by_pattern.match(cropped)
    if m is not None:
        mid_modes.append(SortBy(m[1]))
        cropped = cropped[m.end():]

    ### GROUPBY MODE (optional)
    m = group_by_pattern.match(cropped)
    if m is not None:
        mid_modes.append(GroupBy(m[1], m[2]))
        cropped = cropped[m.end():]

    ### ASSIGNMODE MULTIPLY FLAG (preferred syntax)
    m = mul_pattern.match(cropped)
    multiply |= (m[1] == '*')
    cropped = cropped[m.end():]

    ### ASSIGNMODE
    m = switch_pattern.match(cropped) or switch_pattern_DEPREC.match(cropped)
    if m is not None:
        try:
            assign_mode = LegacySwitch(multiply, len(m[2]), m[1])
        except:
            assign_mode = Switch.from_regex_groups(multiply, len(m[2]), m[1])
        cropped = cropped[m.end():]
    elif (m := rand_pattern.match(cropped)) is not None:
        assign_mode = Random(multiply)
        cropped = cropped[m.end():]
    else:
        assign_mode = DefaultAssign(multiply)

    ### GROUPMODE
    group_mode = GroupMode(split_modes, mid_modes, assign_mode)
    return cropped, group_mode


# "Tests"
if __name__ == '__main__':
    tests = ['foo', '* foo', '10', '%4', '(20)', '/10', '#7', '#14..20', '/',
        '()', '(0)', '#', '*% 2', '*(07)', '/010', '(', '(8', '#0..2!', '\\7', '\\0',
        '\\1!', '\\1!!', '(2)!!', '*!', '!!']
    tests2 = ['{0=1}', '{0="foo"}!', '{0="yes"|0 != "no" | 1 LIKE /foo/ | 2 NOT LIKE /bar/ }']
    print('TESTS:')
    for test in tests:
        try:
            out, mode = legacy_parse(test)
            print(test + ((' → "' + out + '"') if out else '') + ' : ' + str(mode))
        except Exception as e:
            print(test + ' : ' + 'ERROR! ' + str(e))
        print()

    print()
    _, mode = legacy_parse('{ 0 = "bar" | 0 = "foo" }')
    print( mode )
    print( mode.apply( ['bar'] , ['one', 'two', 'three'], None, None ) )
    print( mode.apply( ['bar'] , ['one', 'two'], None, None ) )
    print( mode.apply( ['foo'] , ['one', 'two', 'three'], None, None ) )
    print( mode.apply( ['xyz'] , ['one', 'two', 'three'], None, None ) )
    print( mode.apply( ['xyz'] , ['one', 'two'], None, None ) )

    print()
    _, mode = legacy_parse('{ 0 = 1 }')
    print( mode )
    print( mode.apply( ['bar', 'xyz'] , ['one', 'two'], None, None ) )
    print( mode.apply( ['bar', 'bar'] , ['one', 'two'], None, None ) )
    print( mode.apply( ['bar', 'xyz'] , ['one'], None, None ) )