import re
import math
from typing import List, Tuple, Optional, Any, TypeVar
from random import choice

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
    pass

T = TypeVar('T')
P = TypeVar('P')

################ SPLITMODES ################

class SplitMode:
    '''An object representing a function that turns a list of item into smaller lists.'''
    def __init__(self, strictness: int):
        self.strictness = strictness

    def __str__(self):
        if self.strictness == 0: return ''
        if self.strictness == 1: return 'STRICT '
        if self.strictness == 2: return 'VERY STRICT '

    def isDefault(self):
        '''Whether or not this SplitMode is the default groupmode DIVIDE BY 1.'''
        return False

    def apply(self, items: List[P]) -> List[Tuple[List[P], bool]]:
        raise NotImplementedError()

class Row(SplitMode):
    def __init__(self, strictness, size, padding):
        super().__init__(strictness)
        if size < 1: raise GroupModeError('Row size must be at least 1.')
        self.size = size
        self.padding = padding

    def __str__(self):
        return '{}ROWS SIZE {}{}'.format(super().__str__(), self.size, ' WITH PADDING' if self.padding else '')

    def apply(self, items: List[P]) -> List[Tuple[List[P], bool]]:
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

    def apply(self, items: List[P]) -> List[Tuple[List[P], bool]]:
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

    def isDefault(self):
        return self.count == 1

class Modulo(SplitMode):
    def __init__(self, strictness, modulo, padding):
        super().__init__(strictness)
        if modulo < 1: raise GroupModeError('Modulo value must be at least 1.')
        self.modulo = modulo
        self.padding = padding

    def __str__(self):
        return '{}MODULO {}{}'.format(super().__str__(), self.modulo, ' WITH PADDING' if self.padding else '')

    def apply(self, items: List[P]) -> List[Tuple[List[P], bool]]:
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

    def apply(self, items: List[P]) -> List[Tuple[List[P], bool]]:
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

    def __init__(self, strictness, lval, rval):
        super().__init__(strictness)
        # Should this be an error or should it just parse as a trivial group mode?
        if not lval and not rval: raise GroupModeError('No indices.')

        ## lval is empty: START
        ## lval is -0:    END
        self.lval = 0 if lval == '' else Interval.END if lval == '-0' else int(lval)

        ## rval is None: (lval+1) (indicated as keeping it None)
        ## rval is empty or -0: END
        self.rval = None if rval is None else Interval.END if rval in ['-0', ''] else int(rval)

    def __str__(self):
        if self.rval is None: return '{}INDEX AT {}'.format(super().__str__(), self.lval)
        return '{}INTERVAL FROM {} TO {}'.format(super().__str__(), self.lval, self.rval)

    def apply(self, items: List[P]) -> List[Tuple[List[P], bool]]:
        length = len(items)

        if length == 0: return [(items, False)]

        ## Determine the effective lval
        lval = self.lval if self.lval != Interval.END else length

        ## Determine the effective rval
        if self.rval is Interval.END:
            rval = length
        elif self.rval is None:
            if self.lval == -1:             # Writing #-1 is equivalent to #-1:-0 i.e. The last element
                rval = length
            elif self.lval is Interval.END: # Writing #-0 is equivalent to #-0:-0 i.e. The empty tail
                rval = length
            else: rval = lval + 1
        else:
            rval = self.rval

        ## Manually adjust the indices to be non-negative (may be larger than length)
        while lval < 0: lval += length
        while rval < 0: rval += length
        ## Special case: If we're targeting a negative range, simply target the empty range [lval:lval]
        if rval < lval: rval = lval

        ## Non-strict: Ignore the items outside of the selected range.
        if not self.strictness:
            return [
                (items[0: lval], True),
                (items[lval: rval], False),
                (items[rval: length], True),
            ]
        ## Very strict: Get angry when our range does not exactly cover the list of items
        elif self.strictness == 2 and (lval > 0 or rval != length):
            raise GroupModeError('The range does not strictly fit the set of items!')
        ## Strict: Throw away the items outside of the selected range.
        return [(items[lval: rval], False)]

################ ASSIGNMODES ################

class AssignMode:
    '''An object representing a function that takes lists of items and assigns them to pipes picked from a list.'''
    def __init__(self, multiply):
        self.multiply = multiply

    def __str__(self):
        return 'MULTIPLY ' if self.multiply else ''

    def is_trivial(self):
        ''' A method that returns False unless the AssignMode is DefaultAssign(multiply=False) '''
        return False

    def apply(self, tuples: List[Tuple[T, bool]], pipes: List[P]) -> List[Tuple[T, P]]:
        raise NotImplementedError()

class DefaultAssign(AssignMode):
    '''Assign mode that sends the n'th group to the (n%P)'th pipe with P the number of pipes.'''
    def __init__(self, multiply):
        self.multiply = multiply

    def __str__(self): return super().__str__() + 'DEFAULT'

    def is_trivial(self):
        return not self.multiply

    def apply(self, tuples: List[Tuple[T, bool]], pipes: List[P]) -> List[Tuple[T, Optional[P]]]:
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

class Conditional(AssignMode):
    '''Assign mode that assigns groups to pipes based on logical conditions that each group meets.'''

    class RootCondition():
        type1 = re.compile(r'(-?\d+)\s*(!)?=\s*(-?\d+)')                # <index> = <index>
        type2 = re.compile(r'(-?\d+)\s*(!)?=\s*"([^"]*)"')              # <index> = "<literal>"
        type3 = re.compile(r'(-?\d+)\s+(NOT )?LIKE\s+/([^/]*)/', re.I)  # <index> [NOT] LIKE /<regex>/
        type4 = re.compile(r'((NO|SOME|ANY)THING)', re.I)               # NOTHING or SOMETHING or ANYTHING
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

        def check(self, values: List[str]) -> bool:
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
            self.conds = [[Conditional.RootCondition(cond) for cond in conj] for conj in conjs]
            
        def __str__(self):
            return ' OR '.join(' AND '.join(str(cond) for cond in conj) for conj in self.conds)

        def check(self, values):
            return any(all(cond.check(values) for cond in conj) for conj in self.conds)

    def __init__(self, multiply, strictness, conditions):
        self.multiply = multiply
        self.strictness = strictness
        # TODO: Parse these more smartly
        self.conditions = [self.Condition(c.strip()) for c in conditions.split('|')]

    def __str__(self):
        return '{}CONDITIONAL {{ {} }}'.format(super().__str__(), ' | '.join(str(c) for c in self.conditions))

    def apply(self, tuples: List[Tuple[T, bool]], pipes: List[P]) -> List[Tuple[T, Optional[P]]]:
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
                        out.append((values, pipe)); break
                else:
                ## None of the conditions matched: Pick a "default" case
                    if overflow_pipe_given:
                        out.append((values, pipes[-1]))
                    elif not self.strictness:
                        out.append((values, None))
                    elif self.strictness == 1:
                        pass # Throw this list of values away!
                    elif self.strictness == 2:
                        print('VERY STRICT CONDITION ERROR:')
                        print('VALUES: ', values)
                        print('CONDITIONS: ' + str(self))
                        raise GroupModeError('Very strict condition error: Default case was reached!')
            return out

        else: ## Multiply
            out = []
            for values, ignore in tuples:
                if ignore:
                    out.append((values, None)); continue

                out += [ (values, pipe) for (condition, pipe) in conditions_and_pipes if condition.check(values) ]
                if overflow_pipe_given: out.append( (values, pipes[-1]) )
            return out

class Random(AssignMode):
    '''Assign mode that sends each group to a random pipe.'''
    def __str__(self):
        return super().__str__() + 'RANDOM'

    def apply(self, tuples: List[Tuple[T, bool]], pipes: List[P]) -> List[Tuple[T, Optional[P]]]:
        return [ (items, None if ignore else choice(pipes)) for (items, ignore) in tuples ]


################ PROTOMODES ################

class GroupBy:
    # Stringy enum
    GROUP = 'GROUP'
    COLLECT = 'COLLECT'
    EXTRACT = 'EXTRACT'

    def __init__(self, mode: str, keys: str):
        self.mode = GroupBy.GROUP if mode == 'GROUP' else GroupBy.COLLECT if mode == 'COLLECT' else GroupBy.EXTRACT

        # The set of indices
        self.keys = [ int(i) for i in re.split(r'\s*,\s*', keys) ]
        # The highest referenced index
        self.maxIndex = max(self.keys)
        # isKey[i] == True  ⇐⇒ i in indices
        self.isKey = [ (i in self.keys) for i in range(self.maxIndex+1) ]

    def __str__(self):
        return self.mode + ' BY ' + ', '.join( (str(i)+'!' if self.hasBang[i] else str(i)) for i in self.keys )

    def apply(self, tuples: List[Tuple[T, bool]]) -> List[Tuple[T, bool]]:
        out = []
        known = {}

        for (items, ignore) in tuples:
            if ignore:
                out.append((items, True))
                continue

            n = len(items)
            if self.maxIndex >= n:
                raise GroupModeError('GROUP BY index out of range.')
            keys = tuple( items[i] for i in self.keys )

            if keys not in known:
                ## COLLECT mode tells us to float the keys to the front
                ## EXTRACT mode tells us to get rid of the keys entirely
                if self.mode == GroupBy.GROUP:
                    values = items
                elif self.mode == GroupBy.COLLECT:
                    values = list(keys) + [ items[i] for i in range(n) if i > self.maxIndex or not self.isKey[i] ]
                else:
                    values = [ items[i] for i in range(n) if i > self.maxIndex or not self.isKey[i] ]
                known[keys] = values
                out.append((values, False))

            else:
                ## COLLECT and EXTRACT modes tell us to filter out the keys on repeat items
                if self.mode == GroupBy.GROUP:
                    values = items
                else:
                    values = [ items[i] for i in range(n) if i > self.maxIndex or not self.isKey[i] ]
                known[keys].extend(values)

        return out

################ GROUPMODE ################

class GroupMode:
    '''A class that combines multiple SplitModes and an AssignMode'''
    def __init__(self, splitModes: List[SplitMode], groupBy: GroupBy, assignMode: AssignMode):
        self.splitModes: List[SplitMode] = splitModes
        self.groupBy: GroupBy = groupBy
        self.assignMode: AssignMode = assignMode

    def __str__(self):
        if self.splits_trivially() and self.assignMode.is_trivial():
            return 'TRIVIAL'
        return ' > '.join(str(s) for s in self.splitModes) + ' × ' + str(self.assignMode)

    def splits_trivially(self):
        return not self.splitModes

    def apply(self, all_items: List[T], pipes: List[P]) -> List[ Tuple[List[T], Optional[P]] ]:
        groups: List[Tuple[List[T], bool]] = [(all_items, False)]

        ## Apply all the SplitModes
        for groupmode in self.splitModes:
            newGroups = []
            for items, ignore in groups:
                if ignore: newGroups.append( (items, True, None) )
                else: newGroups.extend( groupmode.apply(items) )
            groups = newGroups

        ## Apply the GroupBy (if any)
        if self.groupBy:
            groups = self.groupBy.apply(groups)

        ## Apply the AssignMode
        return self.assignMode.apply( groups, pipes )


# pattern:
# optionally starting with a Multiply Flag: *
# then 0 or more instances of SplitModes:
#   (N)  |  %N  |  \N  |  /N  |  #N  |  #N:M
# each optionally followed by a Strictness flag: ! | !!

# optionally followed by a GroupBy mode:
#   (GROUP|COLLECT|EXTRACT) BY I, J, K, ...

# optionally followed by a Multiply flag: *
# optionally followed by an AssignMode:
#   { COND1 | COND2 | COND3 | ... }  |  ?
# each optionally followed by a Strictness flag: ! | !!

mul_pattern = re.compile(r'\s*(\*?)\s*')
#                              ^^^

row_pattern = re.compile(r'\(\s*(\d+)?\s*\)')
#                                ^^^
op_pattern = re.compile(r'(/|%|\\)\s*(\d+)?')
#                          ^^^^^^     ^^^
int_pattern = re.compile(r'#(-?\d*)(?:(?::|\.\.+)(-?\d*))?')
#                            ^^^^^                ^^^^^

group_by_pattern = re.compile(r'\s*(GROUP|COLLECT|EXTRACT) BY\s*(\d+(?:\s*,\s*\d+)*)\s*')
#                                   ^^^^^^^^^^^^^^^^^^^^^        ^^^^^^^^^^^^^^^^^^

cond_pattern = re.compile(r'{(.*?)}\s*(!?!?)\s*', re.S)
#                             ^^^      ^^^^
rand_pattern = re.compile(r'\?')

strict_pattern = re.compile(r'\s*(!?!?)\s*')
#                                 ^^^^

op_dict = {'/': Divide, '\\': Column, '%': Modulo}

def parse(bigPipe):
    ### HEAD MULTIPLY FLAG (for backwards compatibility)
    m = mul_pattern.match(bigPipe)
    multiply = (m[1] == '*')
    cropped = bigPipe[m.end():]

    splitModes: List[SplitMode] = []
    ### SPLITMODES (multiple consecutive ones!)
    while(True):
        ### MODE
        m = row_pattern.match(cropped)
        if m is not None:
            splitMode = Row
            value = m[1]
        else:
            m = op_pattern.match(cropped)
            if m is not None:
                splitMode = op_dict[m[1]]
                value = m[2]
            else:
                m = int_pattern.match(cropped)
                if m is not None:
                    splitMode = Interval
                    lval, rval = m.groups()
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
            if splitMode in [Row, Column, Divide, Modulo]:
                if value is None: raise GroupModeError('Missing number.')
                padding = (value[0]=='0')
                value = int(value)
                splitMode = splitMode(strictness, value, padding)

            elif splitMode is Interval:
                splitMode = Interval(strictness, lval, rval)

        except GroupModeError as e:
            raise GroupModeError( 'In split mode `%s`: %s' % (flag, e) )

        splitModes.append(splitMode)

    ### GROUPBY MODE (optional)
    groupBy = None
    m = group_by_pattern.match(cropped)
    if m is not None:
        groupBy = GroupBy(m[1], m[2])
        cropped = cropped[m.end():]

    ### ASSIGNMODE MULTIPLY FLAG (preferred syntax)
    m = mul_pattern.match(cropped)
    multiply |= (m[1] == '*')
    cropped = cropped[m.end():]

    ### ASSIGNMODE
    m = cond_pattern.match(cropped)
    if m is not None:
        assignMode = Conditional(multiply, len(m[2]), m[1])
        cropped = cropped[m.end():]
    else:
        m = rand_pattern.match(cropped)
        if m is not None:
            assignMode = Random(multiply)
            cropped = cropped[m.end():]
        else:
            assignMode = DefaultAssign(multiply)

    ### GROUPMODE
    groupMode = GroupMode(splitModes, groupBy, assignMode)
    return cropped, groupMode


# Tests!
if __name__ == '__main__':
    tests = ['foo', '* foo', '10', '%4', '(20)', '/10', '#7', '#14..20', '/',
        '()', '(0)', '#', '*% 2', '*(07)', '/010', '(', '(8', '#0..2!', '\\7', '\\0',
        '\\1!', '\\1!!', '(2)!!', '*!', '!!']
    tests2 = ['{0=1}', '{0="foo"}!', '{0="yes"|0 != "no" | 1 LIKE /foo/ | 2 NOT LIKE /bar/ }']
    print('TESTS:')
    for test in tests:
        try:
            out, mode = parse(test)
            print(test + ((' → "' + out + '"') if out else '') + ' : ' + str(mode))
        except Exception as e:
            print(test + ' : ' + 'ERROR! ' + str(e))
        print()

    print()
    _, mode = parse('{ 0 = "bar" | 0 = "foo" }')
    print( mode )
    print( mode.apply( ['bar'] , ['one', 'two', 'three'] ) )
    print( mode.apply( ['bar'] , ['one', 'two'] ) )
    print( mode.apply( ['foo'] , ['one', 'two', 'three'] ) )
    print( mode.apply( ['xyz'] , ['one', 'two', 'three'] ) )
    print( mode.apply( ['xyz'] , ['one', 'two'] ) )

    print()
    _, mode = parse('{ 0 = 1 }')
    print( mode )
    print( mode.apply( ['bar', 'xyz'] , ['one', 'two'] ) )
    print( mode.apply( ['bar', 'bar'] , ['one', 'two'] ) )
    print( mode.apply( ['bar', 'xyz'] , ['one'] ) )