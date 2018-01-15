import re
import math

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
        nop = {'name':'', 'args':''}
        rval = self.rval if self.rval != 'LEN' else len(values)
        lval = self.lval
        while lval < 0: lval += len(values)
        while rval < 0: rval += len(values)
        if rval < lval: # negative range: nop
            return [(values, nop)]
        else:
            return [
                (values[0: lval], nop),
                (values[lval: rval], pipes[0]),
                (values[rval: len(values)], nop),
            ]


pattern = re.compile(r'(\*?)(\(|%|#|/|)\s*(-?\d*(?:\.\.+-?\d+)?|\d*)\s*\)?\s*')

def parse(bigPipe):
    m = re.match(pattern, bigPipe)
    if m is not None:
        flag = m.group()
        multiply, mode, value = m.groups()
        # print('FLAG:', flag)
        # print('GROUPS:', m.groups())

        multiply = (multiply == '*')

        if not mode:
            if not multiply:
                return bigPipe, Divide(False, 1, False)
            else:
                mode = '('

        if mode in ['(', '%', '/']:
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
            lval = int(vals[0])
            if len(vals) == 2:
                rval = int(vals[1])
            elif lval == -1:
                rval = 'LEN' # special case value because you can't slice from [-1: -0] to get the last character!!!!!!
            else:
                rval = lval + 1
            mode = Interval(multiply, lval, rval)

        bigPipe = bigPipe[len(flag):]

    else:
        mode = Divide(False, 1, False)
    return bigPipe, mode


if __name__ == '__main__':
    tests = ['foo', '*foo', '10', '%4', '(20)', '/10', '#7', '#14..20', '/', '()', '#', '*% 2', '*(07)', '/010']
    print('TESTS:')
    for test in tests:
        try:
            print(test + ' : ' + str(parse(test)[1]))
        except:
            print(test + ' : ' + 'INVALID!')
        print()