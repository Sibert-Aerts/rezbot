import re
import math

# Pipe grouping syntax!

### Intro
# What happens here is how a pipe determines how different inputs are grouped when they are processed by pipes.
# In many pipes "grouping" makes no difference, pipes such as "convert" or "translate" simply act on each individual input regardless of how they are grouped.

# There are, however, some pipes where it does make a difference. Take for example the "join" pipe:

#   >>> [alpha|beta|gamma|delta] -> join s=", "
# Output: alpha → alpha, beta, gamma, delta
#         beta
#         gamma
#         delta

#   >>> [alpha|beta|gamma|delta] -> (2) join s=", "
# Output: alpha → alpha, beta
#         beta  → gamma, delta
#         gamma
#         delta

# The number of inputs it receives at once determine what its output looks like, and even how many outputs it produces!
# The other situation where group modes matter is when applying multiple pipes in parallel, like so:

#   >>> [alpha|beta|gamma|delta] > (1) convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         ｂｅｔａ
#         𝔤𝔞𝔪𝔪𝔞
#         ｄｅｌｔａ

# The (1) tells the script to split the values into groups of 1 item each. Each of these groups of size 1 are then *alternately*
# fed into "convert fraktur" and "convert fullwidth", as you can see from the output. This should make the utility of grouping clear.
# Note: If we don't put the (1) there, it will assume the default group mode /1, which simply puts all values into one group and applies it
# to the first pipe of the parallel pipes, leaving the other pipe unused (e.g. in the example, all inputs would be converted to fraktur lettering.)


### Some quick syntax examples:

#   >>> {foo} > (2) bar
# Means: Fetch output produced by the source named "foo" (which could be any number of strings) and feed it into the "bar" pipe in groups of 2.

# e.g. >>> {words n=4} > (2) join s=" AND "
# Might produce the following 2 rows of output: "trousers AND presbyterian", "lettuce's AND africanism"

#   >>> {foo} > (2) [bar|tox]
# Means: Fetch output from the source "foo", split it into groups of 2, feed the first group into "bar", the second into "tox", third into "bar", and so on.

# e.g. >>> {words n=4} > (2) [join s=" AND " | join s=" OR "]
# Might produce the 2 rows of output: "derides AND clambered", "swatting OR quays"

#   >>> {foo} > *(2) [bar|tox]
# Means: Fetch output from source "foo", split it in groups of 2, feed each group individually into "bar", and then feed each group into "tox".

# e.g. >>> {words n=4} > *(2) [join s=" AND " | join s=" OR "]
# Might produce these 4 outputs: "horseflies AND retool", "horseflies OR retool", "possum AND ducts", "possum OR ducts"


### All syntax rules:

## Multiply option:
# Given by adding an asterisk* before the group mode:
#   >>> {source} > * $$$$ [pipe1|pipe2|...]
# (With $$$$ representing a group mode)
# *Each* group of input is fed into *each* of the simultaneous pipes (pipe1, pipe2, etc)
# Resulting in (number of groups) × (number of simultaneous pipes) pipe applications total, which is usually a lot.

# Strict option:
# Given by adding an exclamation mark after the group mode!
#   >>> {source} > $$$$ ! [pipe1|pipe2|...]
# (With $$$$ representing a group mode)
# This option tells the group mode to simply throw away input values that don't "fit" according to the group mode.
# What it specifically throws away (if anything) depends on both the type of group mode, and the number of values it's grouping.

# Very Strict option:
# Given by adding two exclamation marks after the group mode!!
#   >>> {source} > $$$$ !! [pipe1|pipe2|...]
# (With $$$$ representing a group mode)
# The group mode raises a terminal error if the input values don't "fit" according to the group mode, cutting script execution short completely.
# This is useful if there is semantic significance to the structure of the values you are grouping on.


## Default grouping (Divide grouping special case):
#   >>> {source} > [pipe1|pipe2|...|pipex]
# Feeds all input to pipe1 as a single group, ignoring pipe2 through pipex.
# Identical to Divide grouping with N as 1, i.e. "/1".
#   >>> [alpha|beta|gamma|delta] > convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔟𝔢𝔱𝔞
#         𝔤𝔞𝔪𝔪𝔞
#         𝔡𝔢𝔩𝔱𝔞

## Row grouping:
#   >>> {source} > (N) [pipe1|pipe2|...|pipeX]
# Groups the first N inputs and feeds them to pipe1, the second N inputs to pipe2, ..., the X+1th group of N inputs to pipe1 again, etc.
# If the number of inputs doesn't divide by N:
#   • If the strict option is given: It will throw away the remaining less-than-N items.
#   • If N starts with a '0': It will pad out the last group with empty strings to make N items.
#   • Otherwise: The last group will simply contain less than N items.
# If your inputs are a row-first matrix, and given N the size of a row (i.e. number of columns) in the matrix, this groups all the rows.
#   >>> [alpha|beta|gamma|delta|epsilon|phi] > (3) convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔟𝔢𝔱𝔞
#         𝔤𝔞𝔪𝔪𝔞
#         ｄｅｌｔａ
#         ｅｐｓｉｌｏｎ
#         ｐｈｉ

## Divide grouping:
#   >>> {source} > /N [pipe1|pipe2|...|pipex]
# Splits the input into N equally sized* groups of sequential inputs, and feeds the first group into pipe1, second into pipe2, etc.
# Call M the number of inputs to be grouped. In case M is not divisible by N:
#   • If the strict option is given: Input is split into groups of floor(M/N), throwing away extraneous items.
#   • If N starts with '0': Input is split into groups of ceil(M/N), and the last group is padded out with empty strings.
#   • If N doesn't start with '0': Input is split into groups of ceil(M/N), except the last groups which may contain less items or even be empty.
# If your inputs are a row-first matrix, and given N the size of a column (i.e. number of rows) in the matrix, this groups all the rows.
#   >>> [alpha|beta|gamma|delta|epsilon|phi] > /3 convert [fraktur|fullwidth|smallcaps]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔟𝔢𝔱𝔞
#         ｇａｍｍａ
#         ｄｅｌｔａ
#         ᴇᴘsɪʟᴏɴ
#         ᴘʜɪ

## Modulo grouping:
#   >>> {source} > %N [pipe1|pipe2|...|pipex]
# Splits the input into N equally sized* groups of inputs that have the same index modulo N. This changes the order of the values, even if the pipe is a NOP.
# Behaves identical to Divide grouping otherwise, including N starting with '0' to pad each group out to equal size, and strictness rules.
# If your inputs are a row-first matrix, and given N the size of a row (i.e. number of columns) in the matrix, this groups all the columns.
#   >>> [alpha|beta|gamma|delta|epsilon|phi] > %3 convert [fraktur|fullwidth|smallcaps]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔡𝔢𝔩𝔱𝔞
#         ｂｅｔａ
#         ｅｐｓｉｌｏｎ
#         ɢᴀᴍᴍᴀ
#         ᴘʜɪ

## Column grouping:
#   >>> {source} > \N [pipe1|pipe2|...|pipex]
# Splits the input into groups of size N* by applying Modulo(M/N) with M the number of items, and (/) rounding up or down depending on padding or strictness.
# There's no good intuitive explanation here, just the mathematical one:
# If your inputs are a row-first matrix, and given N the size of a column (i.e. number of rows) in the matrix, this groups all the columns.
#   >>> [alpha|beta|gamma|delta|epsilon|phi] > \3 convert [fraktur|fullwidth]
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
#   >>> [alpha|beta|gamma|delta|epsilon|phi] > \3 convert [fraktur|fullwidth] > %3
# Output: 𝔞𝔩𝔭𝔥𝔞
#         ｂｅｔａ
#         𝔤𝔞𝔪𝔪𝔞
#         ｄｅｌｔａ
#         𝔢𝔭𝔰𝔦𝔩𝔬𝔫
#         ｐｈｉ

## Interval grouping:
#   >>> {source} > #A..B [pipe1|pipe2|...]
# Groups inputs from index A up to, but NOT including, index B as one group and applies them to pipe1, the other pipes are never used.
# If the strict option is given, the items outside the selected range are thrown away, otherwise they are left in place, unaffected.
# A and B can be negative, and follows python's negative index logic for those. (e.g. a[-1] == a[len(a)-1])
# A and B may also use '-0' to indicate the last position in the string. (i.e. '-0' -> len(inputs))
#   >>> [alpha|beta|gamma|delta] > #1..3 convert fullwidth
# Output: alpha
#         ｂｅｔａ
#         ｇａｍｍａ
#         delta

## Index grouping (Interval special case):
#   >>> {source} > #A [pipe1|pipe2|...]
# Same as Interval grouping with B := A+1. (Except if B is -0 then A is -0 as well.) (This has a use case, I swear)
#   >>> [alpha|beta|gamma|delta] > #2 convert fullwidth
# Output: alpha
#         beta
#         ｇａｍｍａ
#         delta

class GroupModeError(ValueError):
    pass

class GroupMode:
    def __init__(self, multiply, strictness):
        self.multiply = multiply
        self.strictness = strictness

    def __str__(self):
        qualifiers = []
        if self.strictness == 1: qualifiers.append('STRICT')
        if self.strictness == 2: qualifiers.append('VERY STRICT')
        if self.multiply: qualifiers.append('MULTIPLIED')
        return ' '.join(qualifiers)

    def apply(self, values, pipes):
        raise NotImplementedError()

class Row(GroupMode):
    def __init__(self, multiply, strictness, size, padding):
        super().__init__(multiply, strictness)
        if size < 1: raise GroupModeError('Row size must be at least 1.')
        self.size = size
        self.padding = padding

    def __str__(self):
        return '{} GROUPS SIZE {}{}'.format(super().__str__(), self.size, ' WITH PADDING' if self.padding else '')

    def apply(self, values, pipes):
        length = len(values)    # The number of items we want to split
        size = self.size        # The size of each group (GIVEN)
        count= length //size    # The minimal number of groups we have to split it into
        rest = length % size    # The number of leftover items if we were to split into the minimal number of groups

        ## Deal with the fact that our last group does not contain the number of items we wanted:
        if rest:
            ## Very strict: Raise an error
            if self.strictness == 2:
                raise GroupModeError('Could not strictly group into rows size %d!' % size)
            ## Strict: Throw away the last group
            elif self.strictness == 1:
                length = count*size
                values = values[:length]
            ## Padding: The last group is padded out with (size-rest) empty strings.
            elif self.padding:
                values += [''] * (size - rest)
                count += 1
                length = count*size
                rest = 0
            ## Default: The last group only contains (rest) items.
            # NOTE: Padding fills up the "empty spots" from the Default behaviour.

        ## Special case: Values is an empty list.
        if length == 0:
            ## Very strict: Get angry
            if self.strictness == 2: raise GroupModeError('No values to strictly group!')
            ## Strict: Do nothing.
            if self.strictness == 1: return []
            ## Non-strict: Assume the empty list as our only group.
            if self.multiply: return [([], pipe) for pipe in pipes]
            else: return [([], pipes[0])]

        out = []

        ## Slice our input into groups of the desired size, and assign them to successive pipes.
        for i in range(0, length, size):
            vals = values[i: i+size]
            if self.multiply:
                for pipe in pipes: out.append((vals, pipe))
            else:
                out.append((vals, pipes[ i//size % len(pipes) ]))
        return out

class Divide(GroupMode):
    def __init__(self, multiply, strictness, count, padding):
        super().__init__(multiply, strictness)
        if count < 1: raise GroupModeError('Divide count must be at least 1.')
        self.count = count
        self.padding = padding

    def __str__(self):
        return '{} DIVIDE INTO {}{}'.format(super().__str__(), self.count, ' WITH PADDING' if self.padding else '')

    def apply(self, values, pipes):
        length = len(values)    # The number of items we want to split
        count = self.count      # The number of groups we want to split it into (GIVEN)
        size = length //count   # The minimal size of each group
        rest = length % count   # The number of leftover items if we were to split into groups of minimal size

        ## Deal with the fact that we can't split the values into equal sizes.
        if rest:
            ## Very strict: Raise an error
            if self.strictness == 2:
                raise GroupModeError('Could not strictly divide into %d rows!' % count)
            ## Strict: Throw away the tail end to make the length fit
            elif self.strictness == 1:
                length = size*count
                values = values[:length]
                rest = 0
            ## Padding: The last group is padded out.
            elif self.padding:
                values += [''] * (count - rest)
                size += 1
                length = size*count
                rest = 0
            ## Default: The first (rest) groups contain 1 more item than the remaining (count-rest) groups.
            # NOTE: This means padding does NOT fill in the "empty spots" from the default behaviour!
            # The significance of this is negligible though since any scenario where rest>0 is probably
            # a scenario where the specific alignment/grouping of values is meaningless, so we can just do what's easiest for us.

        ## Special case: Empty list of values.
        if length == 0:
            ## Very strict: Get angry
            if self.strictness == 2: raise GroupModeError('No values to strictly group!')
            ## Strict: Do nothing.
            if self.strictness == 1: return []
            ## Empty times applied to each pipe (count) times.
            if self.multiply: return [([], pipe) for pipe in pipes for _ in range(count)]
            ## Empty applied to (count) pipes once.
            return [([], pipes[i % len(pipes)]) for i in range(count)]

        out = []

        ## Slice our inputs into the desired number of groups, and assign them to successive pipes.
        for i in range(self.count):
            # The min(rest, i) and min(rest, i+1) ensure that the first (rest) slices get 1 extra value.
            left =    i   * size + min(rest, i)
            right = (i+1) * size + min(rest, i+1)
            vals = values[left:right]

            if self.multiply:
                for pipe in pipes: out.append((vals, pipe))
            else:
                out.append((vals, pipes[i % len(pipes)]))
        return out

class Modulo(GroupMode):
    def __init__(self, multiply, strictness, modulo, padding):
        super().__init__(multiply, strictness)
        if modulo < 1: raise GroupModeError('Modulo value must be at least 1.')
        self.modulo = modulo
        self.padding = padding

    def __str__(self):
        return '{} MODULO {}{}'.format(super().__str__(), self.modulo, ' WITH PADDING' if self.padding else '')

    def apply(self, values, pipes):
        length = len(values)    # The number of items we want to split
        count = self.modulo     # The number of groups we want to split it into (GIVEN)
        size = length //count   # The minimal size of each group
        rest = length % count   # The number of leftover items if we were to split into groups of minimal size

        ## Deal with the fact that we can't split the values into equal sizes.
        if rest:
            ## Very strict: Raise an error
            if self.strictness == 2:
                raise GroupModeError('Could not strictly group into %d columns!' % count)
            ## Strict: Throw away the tail end to make the length fit
            elif self.strictness == 1:
                length = size*count
                values = values[:length]
                rest = 0
            ## Padding: The last (count-rest) groups are padded out with one empty string.
            if self.padding:
                values += [''] * (count - rest)
                size += 1
                length = size*count
                rest = 0
            ## Default: The first (rest) groups contain 1 item more than the others.
            # NOTE: Padding and Default behaviour are "equivalent" here.

        ## Special case: Empty list of values; identical to Divide
        if length == 0:
            if self.strictness == 2: raise GroupModeError('No values to strictly group!')
            if self.strictness == 1: return []
            if self.multiply: return [([], pipe) for pipe in pipes for _ in range(count)]
            return [([], pipes[i % len(pipes)]) for i in range(count)]

        out = []
        for i in range(0, count):
            ## Slice into groups of items whose indices are x+i where x is a multiple of (count)
            vals = [values[x+i] for x in range(0, length, count) if x+i < length]

            if self.multiply:
                for pipe in pipes: out.append((vals, pipe))
            else:
                out.append((vals, pipes[i % len(pipes)]))
        return out

class Column(GroupMode):
    def __init__(self, multiply, strictness, size, padding):
        super().__init__(multiply, strictness)
        if size < 1: raise GroupModeError('Column size must be at least 1.')
        self.size = size
        self.padding = padding

    def __str__(self):
        return '{} COLUMNS SIZE {}{}'.format(super().__str__(), self.size, ' WITH PADDING' if self.padding else '')

    def apply(self, values, pipes):
        length = len(values)    # The number of items we want to split
        size = self.size        # The size of each group (GIVEN)
        count= length //size    # The minimal number of groups we have to split it into
        rest = length % size    # The number of leftover items if we were to split into the minimal number of groups

        ## Deal with the fact that we can't split the values into equal sizes.
        if rest:
            ## Very strict: Raise an error
            if self.strictness == 2:
                raise GroupModeError('Could not strictly group into columns size %d!' % size)
            ## Strict: Throw away the tail end to make the length fit
            elif self.strictness == 1:
                length = size*count
                values = values[:length]
                rest = 0
            ## Padding: Pad out the tail so the last (size-rest) groups contain one empty string.
            if self.padding:
                values += [''] * (size - rest)
                count += 1
                length = size*count
                rest = 0
            ## Default: The last (size-rest) groups contain 1 less item.
            # NOTE: Padding fills up the "empty spots" from the Default behaviour.

        ## Special case: Empty list of values; identical to Row
        if length == 0:
            if self.strictness == 2: raise GroupModeError('No values to strictly group!')
            if self.strictness == 1: return []
            if self.multiply: return [([], pipe) for pipe in pipes]
            else: return [([], pipes[0])]

        out = []
        for i in range(0, count):
            ## Slice into groups of items whose indices are x+i where x is a multiple of (count)
            vals = [values[x+i] for x in range(0, length, count) if x+i < length]

            if self.multiply:
                for pipe in pipes: out.append((vals, pipe))
            else:
                out.append((vals, pipes[i % len(pipes)]))
        return out

class Interval(GroupMode):

    # Magical objects.
    END = object()

    def __init__(self, multiply, strictness, lval, rval):
        super().__init__(multiply, strictness)
        ## lval is either an integer or the magical value END
        if lval == '': raise GroupModeError('Missing index.') 
        self.lval = int(lval) if lval != '-0' else Interval.END
        ## rval is either None, an integer, or the magical value END
        if rval is None:
            self.rval = None
        else:
            self.rval = int(rval) if rval != '-0' else Interval.END

    def __str__(self):
        return '{} INTERVAL FROM {} TO {}'.format(super().__str__(), self.lval, self.rval)

    def apply(self, values, pipes):
        NOP = None
        length = len(values)

        if length == 0: return [(values, NOP)]

        ## Determine the effective lval
        lval = self.lval if self.lval != Interval.END else length

        ## Determine the effective rval
        if self.rval is Interval.END:
            rval = length
        elif self.rval is None:
            if self.lval == -1:             # Writing #-1 is equivalent to #-1..-0: The last element
                rval = length
            elif self.lval == Interval.END: # Writing #-0 is equivalent to #-0..-0: The empty tail
                rval = length
            else: rval = lval + 1
        else:
            rval = self.rval

        ## Manually adjust the indices to be non-negative (may be larger than length)
        while lval < 0: lval += length
        while rval < 0: rval += length
        ## Special case: If we're targeting a negative range, simply target the empty range [lval:lval]
        if rval < lval: rval = lval

        ## Non-strict: Apply NOP to the values outside of the selected range.
        if not self.strictness:
            return [
                (values[0: lval], NOP),
                (values[lval: rval], pipes[0]),
                (values[rval: length], NOP),
            ]
        else:
            ## Very strict: Get angry when our range does not exactly cover the list of values?
            if self.strictness == 2 and (lval > 0 or rval != length):
                raise GroupModeError('The range does not strictly fit the set of values!')
            ## Strict: Throw away the values outside of the selected range.
            return [(values[lval: rval], pipes[0])]

# pattern:
# optionally starting with *
# then either:
#   % or # or / or \ followed by -?\d* optionally followed by ..+-?\d+
# or:
#   ( \d+ )

# TODO: This doesn't *really* need to be *one* regex, the fact it matches the empty string is a bit stupid too.

pattern = re.compile(r'\s*(\*?)(?:(%|#|/|\\)\s*(-?\d*(?:\.\.+-?\d+)?)|\(\s*(\d+)\s*\)|)\s*(!?!?)\s*')
#                          ^↑^     ^^^↑^^^^     ^^^^^^^^^↑^^^^^^^^^^    ^^^^^↑^^^^^^       ^^↑^
# Groups:                multiply    mode              value             lparvalue       strictness

def parse(bigPipe, error_log):
    m = re.match(pattern, bigPipe)

    ## Default behaviour: Divide into one.
    if m is None or m.group() == '':
        return bigPipe, Divide(False, False, 1, False)

    flag = m.group()
    multiply, mode, value, lparvalue, strictness = m.groups()
    multiply = (multiply == '*')
    strictness = len(strictness)

    if lparvalue is not None:
        mode = '('
        value = lparvalue

    try:
        if not mode:
            mode = Divide(multiply, False, 1, False)

        ## Row, Column, Modulo or Divide mode
        elif mode in ['(', '%', '/', '\\']:
            padding = (value[0]=='0') if value else False
            value = int(value) if value else 1

            if   mode == '(':
                mode = Row   (multiply, strictness, value, padding)
            elif mode == '/':
                mode = Divide(multiply, strictness, value, padding)
            elif mode == '%':
                mode = Modulo(multiply, strictness, value, padding)
            elif mode == '\\':
                mode = Column(multiply, strictness, value, padding)

        ## Interval mode: '#'
        else:
            vals = re.split('\.+', value)
            lval = vals[0]
            rval = vals[1] if len(vals)>1 else None
            mode = Interval(multiply, strictness, lval, rval)

        ## Cut off the groupmode flag
        bigPipe = bigPipe[len(flag):]
        return bigPipe, mode

    except GroupModeError as e:
        print('groupmode warning: ' + str(e))
        error_log('Group mode: "{}": {}'.format(flag.strip(), e))
        bigPipe = bigPipe[len(flag):]
        return bigPipe, Divide(False, False, 1, False)


# Tests!
if __name__ == '__main__':
    tests = ['foo', '* foo', '10', '%4', '(20)', '/10', '#7', '#14..20', '/', '()', '(0)', '#', '*% 2', '*(07)', '/010', '(8', '#0..2!', '\\7', '\\0', '\\1!', '\\1!!', '(2)!!']
    print('TESTS:')
    for test in tests:
        try:
            out, mode = parse(test, lambda x:x)
            print(test + ((' → "' + out + '"') if out else '') + ' : ' + str(mode))
        except Exception as e:
            print(test + ' : ' + 'ERROR! ' + str(e))
        print()
