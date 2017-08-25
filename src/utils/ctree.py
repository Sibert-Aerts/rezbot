from pyparsing import Literal, Regex, Group as pGroup, Forward, Empty, ZeroOrMore, OneOrMore
import functools
import random

class CTree:
    '''
    Class that parses strings and returns combinations based on a "choice" system.
    e.g. 
        "abc[de|fg]" → ["abcde", "abcfg"]
        "I [eat|like] [|hot]dogs" → ["I eat dogs", "I like dogs", "I eat hotdogs", "I like hotdogs"]

    Use:
    `expandedList = CTree.get_all(text)`

    Couldn't be bothered to look up how to implement the iterator pattern but it works so idc :-D
    '''
    class Str:
        def __init__(self, str):
            self.str = str
            self.reset()

        __str__ = __repr__ = lambda s: s.str

        def next(self):
            self.done = True
            return self.str

        def reset(self):
            self.done = False

        def current(self):
            return self.str

    class Choice:
        def __init__(self, vals):
            self.vals = vals.asList()
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

        def reset(self):
            self.i = 0
            self.done = False
            [c.reset() for c in self.vals]

        def current(self):
            return self.vals[self.i].current()

    class Group:
        def __init__(self, vals):
            self.vals = vals.asList()
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

        def reset(self):
            self.done = False
            [c.reset() for c in self.vals]

        def current(self):
            return ''.join([c.current() for c in self.vals])

    lbr = Literal('[').suppress()
    rbr = Literal(']').suppress()
    div = Literal('|').suppress()
    str = Regex('[^\[\|\]]+').setParseAction(lambda t: CTree.Str(t[0]))
    eStr = Empty().setParseAction(lambda t: CTree.Str(''))
    group = Forward()
    choice = pGroup(lbr + group + ZeroOrMore(div + group) + rbr).setParseAction(lambda t: CTree.Choice(t[0]))
    group << pGroup(OneOrMore(choice|str) | eStr).setParseAction(lambda t: CTree.Group(t[0])).leaveWhitespace()

    def parse(str):
        return CTree.group.parseString(str).asList()[0]

    def get_all(str):
        tree = CTree.parse(str)
        out = []
        while not tree.done:
            out.append(tree.next())
        return out