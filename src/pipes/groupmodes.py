import re
import math

# Pipe grouping syntax!

### Intro
# What happens here is how a pipe determines how different inputs are grouped when they are processed by pipes.
# In many pipes "grouping" makes no difference, pipes such as "convert" or "translate" simply act on each individual input regardless of how they are grouped.

# There are, however, pipes where it makes a difference. Take for example the "join" pipe:

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
# Furthermore, even "normal" pipes make use of grouping, in the context of simultaneous pipes:

#   >>> [alpha|beta|gamma|delta] > (1) convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         ｂｅｔａ
#         𝔤𝔞𝔪𝔪𝔞
#         ｄｅｌｔａ

# This script divided the inputs into groups of 1, and fed them individually, simultaneously into either "convert fraktur" or "convert fullwidth".
# These should make the utility and power of grouping clear.


### Some quick syntax examples:

#   >>> foo > bar > tox
# Means: Take the string "foo", feed it into the pipe named "bar" and feed that output into the pipe named "tox" which produces the final output.

#   >>> foo > *[bar|tox]
# Means: Take the string "foo", feed it into BOTH the pipes "bar" and "tox", and the final output is the combined of those 2 pipes' outputs.
#   So, if neither "bar" nor "tox" had any effects on the input string, the output would now be the string "foo", TWICE.

#   >>> {foo} > (2) bar
# Means: Fetch output produced by the source named "foo", which could be any number of strings, and feed it into the "bar" pipe in groups of 2.
# e.g. >>> {words n=4} > (2) join sep=" and "
# Might produce the following 2 rows of output: "trousers and presbyterian", "lettuce's and africanism"

#   >>> {foo} > (2) [bar|tox]
# Means: Fetch output from the source "foo", split it into groups of 2, feed the first group into "bar", the second into "tox", third into "bar", and so on,
#   combining into a single column of output.

#   >>> {foo} > *(2) [bar|tox]
# Means: Fetch output from source "foo", split it in groups of 2, feed each group individually into "bar", and then feed each group into "tox",
#   combining into a single column of output.


### All syntax rules:

## Multiplication mode:
#   >>> {source} > * %%%% [pipe1|pipe2|...]
# (With %%%% representing any group mode)
# *Each* group of input is fed into *each* of the simultaneous pipes (pipe1, pipe2, etc)
# Resulting in (number of groups) x (number of simultaneous pipes) pipe applications total, which is usually a lot.

## Default grouping:
#   >>> {source} > [pipe1|pipe2|...|pipex]
# Feeds all input to pipe1 as a single group, ignoring pipe2 through pipex.
# Identical to divide grouping with $n as 1.
#   >>> [alpha|beta|gamma|delta] > convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔟𝔢𝔱𝔞
#         𝔤𝔞𝔪𝔪𝔞
#         𝔡𝔢𝔩𝔱𝔞

## Normal grouping:
#   >>> {source} > ($n) [pipe1|pipe2|...|pipex]
# Groups the first $n inputs and feeds them to pipe1, the second $n inputs to pipe2, ..., the x+1th group of $n inputs to pipe1 again, etc.
# If the number of inputs doesn't divide by $n, the last group will contain less than $n items, 
# unless $n starts with '0', then it will be padded out with empty strings.
#   >>> [alpha|beta|gamma|delta] > (3) convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔟𝔢𝔱𝔞
#         𝔤𝔞𝔪𝔪𝔞
#         ｄｅｌｔａ

## Divide grouping:
#   >>> {source} > /$n [pipe1|pipe2|...|pipex]
# Splits the input into $n equally sized* groups of sequential inputs, and feeds the first group into pipe1, second into pipe2, etc.
# Call $m the number of inputs to be grouped. In case $m is not divisible by $n:
#   • If $n doesn't start with '0': Input is split into groups of ceil($m/$n), except the last group which may contain less items.
#   • If $n starts with '0': Input is split into groups of ceil($m/$n), and the last group is padded out with empty strings.
#   • (Currently no option to group inputs into groups of floor($m/$n), cropping out other inputs.)
#   >>> [alpha|beta|gamma|delta] > /2 convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔤𝔞𝔪𝔪𝔞
#         ｂｅｔａ
#         ｄｅｌｔａ

## Modulo grouping:
#   >>> {source} > %$n [pipe1|pipe2|...|pipex]
# Splits the input into $n equally sized* groups of inputs that have the same index modulo $n.
# Behaves identical to Divide grouping otherwise, including $n starting with '0' to pad each group out to equal size.
#   >>> [alpha|beta|gamma|delta] > %2 convert [fraktur|fullwidth]
# Output: 𝔞𝔩𝔭𝔥𝔞
#         𝔟𝔢𝔱𝔞
#         ｇａｍｍａ
#         ｄｅｌｔａ

## Interval grouping:
#   >>> {source} > #$i..$j [pipe1|pipe2|...]
# Groups inputs from index $i up to (not including) index $j as one group and applies them to pipe1.
# All other input is kept in place, unaffected, all other pipes are ignored.
# $i and $j can be negative, and follows python's negative index logic for those. (e.g. a[-1] == a[len(a)-1])
# $i and $j may also use '-0' to indicate the last position in the string. (i.e. '-0' -> len(inputs))
#   >>> [alpha|beta|gamma|delta] > #1..3 convert fullwidth
# Output: alpha
#         ｂｅｔａ
#         ｇａｍｍａ
#         delta

## Index grouping:
#   >>> {source} > #$i [pipe1|pipe2|...]
# Same as Interval grouping with $j = $i+1. (Except if $j == '-0' then $i == '-0' as well.)
#   >>> [alpha|beta|gamma|delta] > #2 convert fullwidth
# Output: alpha
#         beta
#         ｇａｍｍａ
#         delta

class GroupMode:
    def __init__(self, multiply):
        self.multiply = multiply

    def __str__(self, ):
        return 'MULTIPLIED' if self.multiply else 'REGULAR'

    def apply(self, *args, **kwargs):
        raise NotImplementedError()

class Default(GroupMode):
    def __init__(self, multiply, size, padding):
        super().__init__(multiply)
        self.size = size
        self.padding = padding

    def __str__(self):
        return '{} GROUPS SIZE {} WITH{} PADDING'.format(super().__str__(), self.size, 'OUT' if not self.padding else '')

    def apply(self, values, pipes):
        # TODO: crop rule
        if self.padding:
            values = values + (math.ceil(len(values)/self.size)*self.size - len(values)) * ['PADDING']
        out = []

        for i in range(0, len(values), self.size):
            # Slice the inputs according to group size
            vals = values[i: i+self.size]

            if self.multiply:
                for pipe in pipes:
                    out.append((vals, pipe))
            else:
                # (i/size) is always an int, we just cast it else % gets angry
                out.append((vals, pipes[int(i/self.size) % len(pipes)]))
        return out

class Divide(GroupMode):
    def __init__(self, multiply, count, padding):
        super().__init__(multiply)
        self.count = count
        self.padding = padding

    def __str__(self):
        return '{} DIVIDE INTO {} WITH{} PADDING'.format(super().__str__(), self.count, 'OUT' if not self.padding else '')

    def apply(self, values, pipes):
        # TODO: crop rule
        size = math.ceil(len(values)/self.count)
        # Same logic as Default

        if self.padding:
            values = values + (math.ceil(len(values)/size)*size - len(values)) * ['PADDING']
        out = []

        for i in range(0, len(values), size):
            # Slice the inputs according to group size
            vals = values[i: i+size]

            if self.multiply:
                for pipe in pipes:
                    out.append((vals, pipe))
            else:
                # (i/size) is always an int, we just cast it else % gets angry
                out.append((vals, pipes[int(i/size) % len(pipes)]))
        return out

class Modulo(GroupMode):
    def __init__(self, multiply, modulo, padding):
        super().__init__(multiply)
        self.modulo = modulo
        self.padding = padding

    def __str__(self):
        return '{} MODULO {} WITH{} PADDING'.format(super().__str__(), self.modulo, 'OUT' if not self.padding else '')

    def apply(self, values, pipes):
        # TODO: crop rule
        if self.padding:
            values = values + (math.ceil(len(values)/self.modulo)*self.modulo - len(values)) * ['PADDING']

        out = []
        for i in range(0, self.modulo):
            vals = [values[x+i] for x in range(0, len(values), self.modulo) if x+i < len(values)]

            if self.multiply:
                for pipe in pipes:
                    out.append((vals, pipe))
            else:
                out.append((vals, pipes[i % len(pipes)]))
        return out

class Interval(GroupMode):
    def __init__(self, multiply, lval, rval):
        super().__init__(multiply)
        self.lval = lval
        self.rval = rval

    def __str__(self):
        return '{} INTERVAL FROM {} TO {}'.format(super().__str__(), self.lval, self.rval)

    def apply(self, values, pipes):
        # TODO: crop rule
        nop = None
        length = len(values)
        lval = int(self.lval) if self.lval != '-0' else length
        if self.rval is None:
            if   self.lval == '-1': rval = length # Writing #-1 is equivalent to #-1..-0: The last element
            elif self.lval == '-0': rval = length # Writing #-0 is equivalent to #-0..-0: The empty tail
            else: rval = lval + 1
        else:
            rval = int(self.rval) if self.rval != '-0' else length
        while lval < 0: lval += length
        while rval < 0: rval += length
        if rval < lval: # negative range: nop
            return [(values, nop)]
        else:
            return [
                (values[0: lval], nop),
                (values[lval: rval], pipes[0]),
                (values[rval: length], nop),
            ]

# pattern:
# optionally starting with *
# then either:
#   % or # or / followed by -?\d* optionally followed by ..+-?\d+
# or:
#   ( \d+ )

pattern = re.compile(r'(\*?)(?:(%|#|/)\s*(-?\d*(?:\.\.+-?\d+)?)|\(\s*(\d+)\s*\)|)\s*')

def parse(bigPipe):
    m = re.match(pattern, bigPipe)
    if m is not None:
        flag = m.group()
        # print('FLAG:', flag)
        # print('GROUPS:', m.groups())
        multiply, mode, value, lparvalue = m.groups()

        multiply = (multiply == '*')

        if lparvalue is not None:
            mode = '('
            value = lparvalue

        if not mode:
            mode = Divide(multiply, 1, False)
        elif mode in ['(', '%', '/']:
            padding = (value[0]=='0') if value else False # TODO: extend to 3-value enum: agnostic, pad and crop
            value = int(value) if value else 1
            if mode == '(':
                mode = Default(multiply, value, padding)
            elif mode == '%':
                mode = Modulo(multiply, value, padding)
            elif mode == '/':
                mode = Divide(multiply, value, padding)
        else:
            vals = re.split('\.+', value)
            lval = vals[0]
            rval = vals[1] if len(vals)>1 else None
            mode = Interval(multiply, lval, rval)

        bigPipe = bigPipe[len(flag):]

    else:
        mode = Divide(False, 1, False)
    return bigPipe, mode


if __name__ == '__main__':
    tests = ['foo', '*  foo', '10', '%4', '(20)', '/10', '#7', '#14..20', '/', '()', '#', '*% 2', '*(07)', '/010', '(8']
    print('TESTS:')
    for test in tests:
        try:
            out, mode = parse(test)
            print(test + ((' → "' + out + '"') if out else '') + ' : ' + str(mode))
        except Exception as e:
            print(test + ' : ' + 'ERROR! ' + str(e))
        print()