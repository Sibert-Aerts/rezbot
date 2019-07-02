from pyparsing import Literal, Regex, Group as pGroup, Forward, Empty, ZeroOrMore, OneOrMore
import functools
import random
import np

class ChoiceTree:
    '''
    Class that parses strings and returns combinations based on a "choice" system.
    e.g.
        "abc[de|fg]" → ["abcde", "abcfg"]
        "I [eat|like] [|hot]dogs" → ["I eat dogs", "I like dogs", "I eat hotdogs", "I like hotdogs"]

    Couldn't be bothered to look up how to implement the iterator pattern but it works so idc :-D
    '''
    class Text:
        def __init__(self, text):
            self.text = text if text == '' else ''.join(text.asList())
            self.count = 1
            self.reset()

        __str__ = __repr__ = lambda s: s.text

        def next(self):
            self.done = True
            return self.text

        def random(self):
            return self.text

        def reset(self):
            self.done = False

        def current(self):
            return self.text

    class Choice:
        def __init__(self, vals):
            self.vals = vals.asList()
            self.count = sum(v.count for v in self.vals)
            self.reset()

        __str__ = __repr__ = lambda s: '[{}]'.format('|'.join([str(v) for v in s.vals]))

        def next(self):
            next = self.vals[self.i]
            out = next.next()
            # print(out)
            if next.done:
                self.i += 1
                if self.i == len(self.vals):
                    self.done = True
            return out

        def random(self):
            # Weighted based on the number of different possible branches each child has.
            return np.random.choice(self.vals, p=list(v.count/self.count for v in self.vals)).random()

        def reset(self):
            self.i = 0
            self.done = False
            [c.reset() for c in self.vals]

        def current(self):
            return self.vals[self.i].current()

    class Group:
        def __init__(self, vals):
            self.vals = vals.asList()
            self.count = functools.reduce(lambda x,y: x*y, (c.count for c in self.vals), 1)
            self.reset()

        __str__ = __repr__ = lambda s: ''.join([str(v) for v in s.vals])

        def next(self):
            i = 0
            out = ''
            while True:
                out += self.vals[i].next()
                if self.vals[i].done:
                    if i == len(self.vals)-1:
                        self.done = True
                        break
                    else:
                        self.vals[i].reset()
                else:
                    break
                i += 1
            i += 1

            while i < len(self.vals):
                out += self.vals[i].current()
                i += 1

            return out

        def random(self):
            return ''.join(v.random() for v in self.vals)

        def reset(self):
            self.done = False
            [c.reset() for c in self.vals]

        def current(self):
            return ''.join([c.current() for c in self.vals])

    escapedLbr = Literal('\\[').suppress().setParseAction(lambda x: '[')
    escapedRbr = Literal('\\]').suppress().setParseAction(lambda x: ']')
    escapedDiv = Literal('\\|').suppress().setParseAction(lambda x: '|')
    escapedEsc = Literal('\\\\').suppress().setParseAction(lambda x: '\\')
    lbr = Literal('[').suppress()
    rbr = Literal(']').suppress()
    div = Literal('|').suppress()
    esc = Literal('\\').suppress().setParseAction(lambda x: '\\')
    _text = Regex('[^\\[\\|\\]\\\\]+') # any sequence of characters not containing '[', ']', '|' or '\'
    text = pGroup( OneOrMore( escapedLbr|escapedRbr|escapedDiv|escapedEsc|esc|_text ) ).setParseAction(lambda t: ChoiceTree.Text(t[0]))
    eStr = Empty().setParseAction(lambda t: ChoiceTree.Text(''))
    group = Forward()
    choice = pGroup( lbr + group + ZeroOrMore( div + group ) + rbr ).setParseAction(lambda t: ChoiceTree.Choice(t[0]))
    group << pGroup( OneOrMore( text|choice ) | eStr ).setParseAction(lambda t: ChoiceTree.Group(t[0])).leaveWhitespace()

    def __init__(self, text, parse_flags=False, add_brackets=False):
        self.flag_random = False
        if parse_flags:
            if text[:3] == '[?]':
                text = text[3:]
                self.flag_random = True

        if add_brackets: text = '[' + text + ']'

        self.tree = ChoiceTree.group.parseString(text).asList()[0]
        self.count = self.tree.count

    def all(self):
        if self.flag_random:
            return [self.random()]
        out = []
        while not self.tree.done:
            out.append(self.tree.next())
        self.tree.reset()
        return out

    def random(self):
        return self.tree.random()