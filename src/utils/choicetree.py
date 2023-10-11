from pyparsing import Char, Literal, Regex, Group, Forward, Empty, ZeroOrMore, OneOrMore, ParseResults, Word
from typing import Generator, Any
import functools
from random import choices
from itertools import product


class ChoiceTreeError(ValueError):
    pass
class EmptyChoiceTreeError(ChoiceTreeError):
    pass


class ChoiceTree:
    '''
    Class that parses strings representing possible combinations, allowing you to iterate and index over them.
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
        so that in python notation e.g. "abc" → ["abc"] and "[a|b|c]" → ["a", "b", "c"]
    By this notation, the ordinals are given as [] for 1, [|] for 2, [||] for 3 etc.
        in the sense that "[||]X" → ["X", "X", "X"],
        but for shorthand, we allow the notation [1], [2], [3] etc.
        This also allows us to write [0] for the empty list (otherwise unwriteable), which when multipled with anything makes the empty list.
        e.g. "[A|B|[0]C]" → ["A", "B"]    and    "[A|B][C|D][0]" → []

    What ChoiceTree does is parse such expressions, and using the distributivity rule ( [a|b]c == ab|ac )
        it simplifies/normalizes the expression to a sum of products.
    '''
    
    # ================ Classes

    class Node:
        count: int
        def __iter__(self) -> Generator[str, Any, None]: ...
        def __len__(self) -> int: ...
        def __getitem__(self, i: int) -> str: ...
        def random(self) -> str: ...

    class Text(Node):
        '''Text end node.'''
        def __init__(self, text: ParseResults):
            self.text: str = text if text == '' else ''.join(text.as_list())
            self.count = 1

        def __repr__(self):
            return self.text
        
        def __iter__(self):
            yield self.text

        def __len__(self):
            return 1

        def __getitem__(self, i):
            if i != 0: raise IndexError()
            return self.text

        def random(self):
            return self.text

    class Choice(Node):
        '''Conjunction of nodes [A|B|C]'''
        def __init__(self, vals: ParseResults):
            self.nodes: list[ChoiceTree.Node] = vals.as_list()
            self.count = sum(v.count for v in self.nodes)

        def __repr__(self):
            return '[{}]'.format('|'.join(str(n) for n in self.nodes))

        def __iter__(self):
            for val in self.nodes:
                yield from val

        def __getitem__(self, i):
            if i >= self.count: raise IndexError()
            for val in self.nodes:
                if i < val.count:
                    return val[i]
                i -= val.count

        def __len__(self):
            return self.count

        def random(self):
            # Weighted based on the number of different possible branches each child has.
            return choices(self.nodes, weights=(v.count for v in self.nodes))[0].random()

    class Ordinal(Node):
        '''
        Special Choice node notation for (choice out of `n` empty strings), effectively acting as a multiplier/weight.
        [1] does absolutely nothing, [2] behaves as [|], 3 as [||], etc.
        [0] annihilates the current choice entirely, something unrepresentable otherwise.
        '''
        def __init__(self, val: ParseResults):
            self.count = int(val[0])

        def __repr__(self):
            return f'[{self.count}]'

        def __iter__(self):
            for _ in range(self.count):
                yield ''

        def __getitem__(self, i):
            if i >= self.count: raise IndexError()
            return ''

        def __len__(self):
            return self.count
        
        def random(self):
            return ''

    class Concat(Node):
        '''Multiple choices and text strings attached end to end.'''
        def __init__(self, vals):
            self.nodes: list[ChoiceTree.Node] = vals.as_list()
            self.count = functools.reduce(lambda x, y: x*y, (n.count for n in self.nodes), 1)

        def __repr__(self):
            return ''.join(str(v) for v in self.nodes)

        def __iter__(self):
            # Double reversed because we want the combinations to vary left-to-right
            for combo in product(*reversed(self.nodes)):
                yield ''.join(reversed(combo))

        def __getitem__(self, i):
            if i >= self.count: raise IndexError()
            combo = []
            for node in self.nodes:
                combo.append(node[i % node.count])
                i //= node.count
            return ''.join(combo)

        def __len__(self):
            return self.count

        def random(self):
            if self.count == 0:
                raise EmptyChoiceTreeError()
            return ''.join(v.random() for v in self.nodes)

    # ================ Grammar

    escaped_symbol = Char('~').suppress() + Char('[|]')
    escaped_esc = Literal('~~')
    sole_esc = Char('~')
    lbr = Literal('[').suppress()
    rbr = Literal(']').suppress()
    bar = Literal('|').suppress()
    _text = Regex(r'[^\[\|\]~]+') # any sequence of characters not containing '[', ']', '|' or '~'
    number = Word('0123456789')

    text = Group( OneOrMore( escaped_symbol|escaped_esc|sole_esc|_text ) ).set_parse_action(lambda s, l, t: ChoiceTree.Text(t[0]))
    concat = Forward()
    ordinal = Group( lbr + number + rbr ).set_parse_action(lambda t: ChoiceTree.Ordinal(t[0]))
    choice = Group( lbr + concat + ZeroOrMore( bar + concat ) + rbr ).set_parse_action(lambda s, l, t: ChoiceTree.Choice(t[0]))
    empty = Empty().set_parse_action(lambda s, l, t: ChoiceTree.Text(''))
    concat <<= Group( OneOrMore(text|ordinal|choice) | empty ).leave_whitespace().set_parse_action(lambda s, l, t: ChoiceTree.Concat(t[0]))
    _root = Group( concat + ZeroOrMore( bar + concat ) ).set_parse_action(lambda s, l, t: ChoiceTree.Choice(t[0]))

    # ================ Methods

    def __init__(self, text, parse_flags=False, parse_all=True):
        self.flag_random = False
        if parse_flags:
            if text[:3] == '[?]':
                text = text[3:]
                self.flag_random = True

        self.root: ChoiceTree.Concat = ChoiceTree._root.parse_string(text, parse_all=parse_all)[0]

    def __repr__(self):
        return f'ChoiceTree({self.root})'

    def __iter__(self):
        if self.flag_random:
            yield self.random()
            return
        yield from self.root

    def __getitem__(self, i):
        return self.root[i]

    def __len__(self):
        if self.flag_random:
            return 1
        return self.root.count

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
    print(prob_test)
    print('Frequency table, expected: 10%/90%/0%')
    for c in 'ABC':
        print(f'{c}: {prob_output.count(c)/100}%')

    print()
    tree = ChoiceTree('[A|B|C|D]--[E|F[G|H|I]]')
    print('tree ==', tree)
    for i in range(len(tree)):
        print(f'tree[{i}] == {tree[i]}')