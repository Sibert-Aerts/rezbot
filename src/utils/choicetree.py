from pyparsing import Char, Literal, Regex, Group as pGroup, Forward, Empty, ZeroOrMore, OneOrMore
import functools
import numpy as np

class ChoiceTree:
    '''
        Class that parses strings representing possible combinations, and returns possible combinations.
        e.g.
            "abc[de|fg]" → [ "abcde", "abcfg" ]
            "I [eat|like] [|hot]dogs" → [ "I eat dogs", "I like dogs", "I eat hotdogs", "I like hotdogs" ]

        Escape symbol is '~'
        e.g.
            "abc~[def~]" → [ "abc[def]" ]
        Due to reasons, an escaped escape '~~' is not turned into a literal '~',
            if this is not up to liking, simply .replace('~~', '~') yourself after parsing.
        
        Essentially, consider the noncommutative Semiring of (unordered) lists of strings,
            so that in python notation: list1+list2 == [*list1, *list2] the concatenation of lists
            and list1*list2 == [a+b for a in list1 for b in list2] the concatenation of each pair of strings.
            (This ring has as neutral element the list of the empty string, and as zero element the empty list.)
        We write addition using the "|" symbol, the product is implicit (i.e. a*b == ab), and use [] as parentheses,
            so that in python notation e.g. "abc" == ["abc"] and "a|b|c" == ["a", "b", "c"]

        What ChoiceTree does is parse such expressions, and using the distributivity rule ( [a|b]c == ab|ac )
            it simplifies the expression to a sum of products.
    '''
    
    # ================ Classes

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
            for c in self.vals:
                c.reset()

        def current(self):
            return self.vals[self.i].current()

    class Group:
        def __init__(self, vals):
            self.vals = vals.asList()
            self.count = functools.reduce(lambda x,y: x*y, (c.count for c in self.vals), 1)
            self.reset()

        __str__ = __repr__ = lambda s: ''.join(str(v) for v in s.vals)

        def next(self):
            i = 0
            out = []
            while True:
                out.append(self.vals[i].next())
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
                out.append(self.vals[i].current())
                i += 1

            return ''.join(out)

        def random(self):
            return ''.join(v.random() for v in self.vals)

        def reset(self):
            self.done = False
            for c in self.vals:
                c.reset()

        def current(self):
            return ''.join(c.current() for c in self.vals)

    # ================ Grammar

    escaped_symbol = Char('~').suppress() + Char('[|]')
    escaped_esc = Literal('~~')
    sole_esc = Char('~')
    lbr = Literal('[').suppress()
    rbr = Literal(']').suppress()
    div = Literal('|').suppress()
    _text = Regex(r'[^\[\|\]~]+') # any sequence of characters not containing '[', ']', '|' or '~'

    text = pGroup( OneOrMore( escaped_symbol|escaped_esc|sole_esc|_text ) ).set_parse_action(lambda t: ChoiceTree.Text(t[0]))
    group = Forward()
    choice = pGroup( lbr + group + ZeroOrMore( div + group ) + rbr ).set_parse_action(lambda t: ChoiceTree.Choice(t[0]))
    empty = Empty().set_parse_action(lambda t: ChoiceTree.Text(''))
    group <<= pGroup( OneOrMore( text|choice ) | empty ).leave_whitespace().set_parse_action(lambda t: ChoiceTree.Group(t[0]))

    # ================ Methods

    def __init__(self, text, parse_flags=False, add_brackets=False):
        self.flag_random = False
        if parse_flags:
            if text[:3] == '[?]':
                text = text[3:]
                self.flag_random = True

        if add_brackets: text = '[' + text + ']'

        self.root: ChoiceTree.Group = ChoiceTree.group.parse_string(text)[0]
        self.count = self.root.count

    def __iter__(self):
        if self.flag_random: yield self.random(); return
        while not self.root.done:
            yield self.root.next()
        self.root.reset()

    def random(self):
        return self.root.random()



## Some itty bitty tests
if __name__ == '__main__':
    tests = [
        '',
        'ABC',
        'A[B|C]',
        'A[B|C][D|E]',
        'A[B|C[D|E]]',
        'A[B|C[D|]]',
        '~A~~B~~[C]',
        'A~[B~|C~]',
        'A~[B|C~]',
        '[AAAA|BBBB[CCCCCCC|DDDDD]E[FFFF[GGGG|HHHH|]|JJJJ|]KKKKKK|LLLLL[MMMM|NNN]][OOOOOOOO|PPP[QQQQ|RRRRRR[SSSSSS|TTTTT[UUUU|VVVVV]]]',
    ]
    for test in tests:
        print(repr(test).ljust(20), ' → ', repr(list(ChoiceTree(test)))[1:-1])
