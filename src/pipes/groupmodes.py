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

## Strict option:
# Given by adding an exclamation mark after the group mode!
#   >>> {source} > $$$$ ! [pipe1|pipe2|...]
# (With $$$$ representing a group mode)
# This option tells the group mode to simply throw away input values that don't "fit".
# What it specifically throws away (if anything) depends on the type of group mode and the values it's grouping.

## Default grouping:
#   >>> {source} > [pipe1|pipe2|...|pipex]
# Feeds all input to pipe1 as a single group, ignoring pipe2 through pipex.
# Identical to Divide grouping with $n as 1, i.e. "/1".
#   >>> [alpha|beta|gamma|delta] > convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔟𝔢𝔱𝔞
#         𝔤𝔞𝔪𝔪𝔞
#         𝔡𝔢𝔩𝔱𝔞

## Normal grouping:
#   >>> {source} > ($n) [pipe1|pipe2|...|pipex]
# Groups the first $n inputs and feeds them to pipe1, the second $n inputs to pipe2, ..., the x+1th group of $n inputs to pipe1 again, etc.
# If the number of inputs doesn't divide by $n:
#   • If the strict option is given: It will throw away the remaining less-than-$n items.
#   • If $n starts with a '0': It will pad out the last group with empty strings to make $n items.
#   • Otherwise: The last group will simply contain less than $n items.
#   >>> [alpha|beta|gamma|delta] > (3) convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔟𝔢𝔱𝔞
#         𝔤𝔞𝔪𝔪𝔞
#         ｄｅｌｔａ

## Divide grouping:
#   >>> {source} > /$n [pipe1|pipe2|...|pipex]
# Splits the input into $n equally sized* groups of sequential inputs, and feeds the first group into pipe1, second into pipe2, etc.
# Call $m the number of inputs to be grouped. In case $m is not divisible by $n:
#   • If the strict option is given: Input is split into groups of floor($m/$n), throwing away extraneous items.
#   • If $n starts with '0': Input is split into groups of ceil($m/$n), and the last group is padded out with empty strings.
#   • If $n doesn't start with '0': Input is split into groups of ceil($m/$n), except the last groups which may contain less items or even be empty.
#   >>> [alpha|beta|gamma|delta] > /2 convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔟𝔢𝔱𝔞
#         ｇａｍｍａ
#         ｄｅｌｔａ

## Modulo grouping:
#   >>> {source} > %$n [pipe1|pipe2|...|pipex]
# Splits the input into $n equally sized* groups of inputs that have the same index modulo $n.
# Behaves identical to Divide grouping otherwise, including $n starting with '0' to pad each group out to equal size and strictness.
#   >>> [alpha|beta|gamma|delta] > %2 convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔤𝔞𝔪𝔪𝔞
#         ｂｅｔａ
#         ｄｅｌｔａ

## Interval grouping:
#   >>> {source} > #$i..$j [pipe1|pipe2|...]
# Groups inputs from index $i up to (not including) index $j as one group and applies them to pipe1, the other pipes are never used.
# If the strict option is given, the items outside the selected range are thrown away, otherwise they are left in place, unaffected.
# $i and $j can be negative, and follows python's negative index logic for those. (e.g. a[-1] == a[len(a)-1])
# $i and $j may also use '-0' to indicate the last position in the string. (i.e. '-0' -> len(inputs))
#   >>> [alpha|beta|gamma|delta] > #1..3 convert fullwidth
# Output: alpha
#         ｂｅｔａ
#         ｇａｍｍａ
#         delta

## Index grouping:
#   >>> {source} > #$i [pipe1|pipe2|...]
# Same as Interval grouping with $j := $i+1. (Except if $j == '-0' then $i == '-0' as well.) (This has use cases, I swear)
#   >>> [alpha|beta|gamma|delta] > #2 convert fullwidth
# Output: alpha
#         beta
#         ｇａｍｍａ
#         delta

class GroupModeError(ValueError):
    pass

class GroupMode:
    def __init__(self, multiply, strict):
        self.multiply = multiply
        self.strict = strict

    def __str__(self):
        qualifiers = []
        if self.strict: qualifiers.append('STRICT')
        if self.multiply: qualifiers.append('MULTIPLIED')
        return ' '.join(qualifiers)

    def apply(self, values, pipes):
        raise NotImplementedError()

class Row(GroupMode):
    def __init__(self, multiply, strict, size, padding):
        super().__init__(multiply, strict)
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
            ## Strict: Throw away the last group
            if self.strict:
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
            ## Strict: Do nothing.
            if self.strict: return []
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
    def __init__(self, multiply, strict, count, padding):
        super().__init__(multiply, strict)
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
            ## Strict: Throw away the tail end to make the length fit
            if self.strict:
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
            ## Strict: Do nothing. (Dubious?)
            if self.strict: return []
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
    def __init__(self, multiply, strict, modulo, padding):
        super().__init__(multiply, strict)
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
            ## Strict: Throw away the tail end to make the length fit
            if self.strict:
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
            if self.strict: return []
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
    def __init__(self, multiply, strict, size, padding):
        super().__init__(multiply, strict)
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
            ## Strict: Throw away the tail end to make the length fit
            if self.strict:
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
            if self.strict: return []
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

    def __init__(self, multiply, strict, lval, rval):
        super().__init__(multiply, strict)
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

        ## Manually adjust the indices to be non-negative
        while lval < 0: lval += length
        while rval < 0: rval += length
        ## Special case: If we're targeting a negative range, simply target the empty range [lval:lval]
        if rval < lval: rval = lval

        ## Non-strict: Apply NOP to the values outside of the selected range.
        if not self.strict:
            return [
                (values[0: lval], NOP),
                (values[lval: rval], pipes[0]),
                (values[rval: length], NOP),
            ]
        ## Strict: Throw away the values outside of the selected range.
        else:
            return [(values[lval: rval], pipes[0])]

# pattern:
# optionally starting with *
# then either:
#   % or # or / followed by -?\d* optionally followed by ..+-?\d+
# or:
#   ( \d+ )

pattern = re.compile(r'\s*(\*?)(?:(%|#|/|§)\s*(-?\d*(?:\.\.+-?\d+)?)|\(\s*(\d+)\s*\)|)(!?!?)\s*')
#                          ^↑^     ^^^↑^^^     ^^^^^^^^^↑^^^^^^^^^^    ^^^^^↑^^^^^^    ^^↑^
# Groups:                multiply   mode              value             lparvalue    strictness

def parse(bigPipe, error_log):
    m = re.match(pattern, bigPipe)

    ## Default behaviour: Divide into one.
    if m is None or m.group() == '':
        return bigPipe, Divide(False, False, 1, False)

    flag = m.group()
    multiply, mode, value, lparvalue, strict = m.groups()
    multiply = (multiply == '*')
    strict = (strict == '!')

    if lparvalue is not None:
        mode = '('
        value = lparvalue

    try:
        if not mode:
            mode = Divide(multiply, False, 1, False)

        ## Row, Column, Modulo or Divide mode
        elif mode in ['(', '%', '/', '§']:
            padding = (value[0]=='0') if value else False
            value = int(value) if value else 1

            if   mode == '(':
                mode = Row   (multiply, strict, value, padding)
            elif mode == '/':
                mode = Divide(multiply, strict, value, padding)
            elif mode == '%':
                mode = Modulo(multiply, strict, value, padding)
            elif mode == '§':
                mode = Column(multiply, strict, value, padding)

        ## Interval mode: '#'
        else:
            vals = re.split('\.+', value)
            lval = vals[0]
            rval = vals[1] if len(vals)>1 else None
            mode = Interval(multiply, strict, lval, rval)

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
    tests = ['foo', '*  foo', '10', '%4', '(20)', '/10', '#7', '#14..20', '/', '()', '(0)', '#', '*% 2', '*(07)', '/010', '(8', '#0..2!', '§7', '§0', '§1!']
    print('TESTS:')
    for test in tests:
        try:
            out, mode = parse(test, lambda x:x)
            print(test + ((' → "' + out + '"') if out else '') + ' : ' + str(mode))
        except Exception as e:
            print(test + ' : ' + 'ERROR! ' + str(e))
        print()
