from pyparsing import Char, Literal, Regex, Group as pGroup, Forward, Empty, ZeroOrMore, OneOrMore, ParseResults, Word
import functools
from itertools import product
import numpy as np

class ChoiceTreeError(ValueError):
    pass
class EmptyChoiceTreeError(ChoiceTreeError):
    pass

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
        '''Text end node.'''
        def __init__(self, text: ParseResults):
            self.text = text if text == '' else ''.join(text.as_list())
            self.count = 1

        __str__ = __repr__ = lambda s: s.text
        
        def __iter__(self):
            yield self.text

        def __len__(self):
            return 1

        def random(self):
            return self.text

    class Choice:
        '''Conjunction of nodes [A|B|C]'''
        def __init__(self, vals: ParseResults):
            self.vals = vals.as_list()
            self.count = sum(len(v) for v in self.vals)

        __str__ = __repr__ = lambda s: '[{}]'.format('|'.join(str(v) for v in s.vals))

        def __iter__(self):
            for val in self.vals:
                yield from val

        def __len__(self):
            return self.count

        def random(self):
            # Weighted based on the number of different possible branches each child has.
            return np.random.choice(self.vals, p=list(v.count/self.count for v in self.vals)).random()

    class Ordinal:
        '''
        Special Choice node notation for (choice out of `n` empty strings), effectively acting as a multiplier/weight.
        [1] does absolutely nothing, [2] behaves as [|], 3 as [||], etc.
        [0] annihilates the current choice entirely, something unrepresentable otherwise.
        '''
        def __init__(self, val: ParseResults):
            self.count = int(val[0])

        __str__ = __repr__ = lambda self: f'[{self.count}]'

        def __iter__(self):
            for _ in range(self.count):
                yield ''

        def __len__(self):
            return self.count
        
        def random(self):
            return ''

    class Group:
        '''Multiple choices and text strings attached end to end.'''
        def __init__(self, vals):
            self.vals = vals.as_list()
            self.count = functools.reduce(lambda x, y: x*y, (len(c) for c in self.vals), 1)

        __str__ = __repr__ = lambda s: ''.join(str(v) for v in s.vals)

        def __iter__(self):            
            for tup in product(*reversed(self.vals)):
                yield ''.join(reversed(tup))

        def __len__(self):
            return self.count

        def random(self):
            if self.count == 0:
                raise EmptyChoiceTreeError()
            return ''.join(v.random() for v in self.vals)

    # ================ Grammar

    escaped_symbol = Char('~').suppress() + Char('[|]')
    escaped_esc = Literal('~~')
    sole_esc = Char('~')
    lbr = Literal('[').suppress()
    rbr = Literal(']').suppress()
    div = Literal('|').suppress()
    _text = Regex(r'[^\[\|\]~]+') # any sequence of characters not containing '[', ']', '|' or '~'
    number = Word('0123456789')

    text = pGroup( OneOrMore( escaped_symbol|escaped_esc|sole_esc|_text ) ).set_parse_action(lambda s, l, t: ChoiceTree.Text(t[0]))
    group = Forward()
    ordinal = pGroup( lbr + number + rbr).set_parse_action(lambda t: ChoiceTree.Ordinal(t[0]))
    choice = pGroup( lbr + group + ZeroOrMore( div + group ) + rbr ).set_parse_action(lambda s, l, t: ChoiceTree.Choice(t[0]))
    empty = Empty().set_parse_action(lambda s, l, t: ChoiceTree.Text(''))
    group <<= pGroup( OneOrMore(text|ordinal|choice) | empty ).leave_whitespace().set_parse_action(lambda s, l, t: ChoiceTree.Group(t[0]))

    # ================ Methods

    def __init__(self, text, parse_flags=False, add_brackets=False):
        self.flag_random = False
        if parse_flags:
            if text[:3] == '[?]':
                text = text[3:]
                self.flag_random = True

        if add_brackets: text = '[' + text + ']'
        self.root: ChoiceTree.Group = ChoiceTree.group.parse_string(text)[0]

    def __iter__(self):
        if self.flag_random:
            yield self.random()
            return
        yield from self.root

    def random(self):
        return self.root.random()

    def __len__(self):
        if self.flag_random:
            return 1
        return self.root.count


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
        'Five[5]',
        '[Five[5]|Three[3]]',
        '[Five[5]|Never[0]|Six[3][2]]',
        '[[0]|[0]|[0]]Never',
        'This one gets wiped[0]',
        '[?][One|Two|Three]',
    ]
    for test in tests:
        strings = list(ChoiceTree(test, parse_flags=True))
        print(repr(test).ljust(32), ' = ', ' + '.join(strings) if strings else '<nothing>')

    print()
    try:
        ChoiceTree('[0]').random()
        print('Assertion failed: Should have raised EmptyChoiceTreeError!')
    except EmptyChoiceTreeError:
        print('Assertion successful: Expected EmptyChoiceTreeError was raised.')


    print()
    prob_test = ChoiceTree('[A|B[10]|C[0]]')
    prob_output = [prob_test.random() for _ in range(10000)]
    print('Frequency table, expected: 10%/90%/0%')
    for c in 'ABC':
        print(f'{c}: {prob_output.count(c)/100}%')
