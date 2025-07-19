from pyparsing import ParseResults
from typing import Literal, NamedTuple

from ..state import ItemScope, ItemScopeError


class TmplItem:
    ''' Abstract class representing an Item inside a TemplatedString. '''
    __slots__ = ("is_implicit",)
    is_implicit: bool

    @staticmethod
    def from_parsed(result: ParseResults):
        if result._name == 'implicit_item':
            return ImplicitTmplItem.from_parsed(result)
        elif result._name == 'explicit_item':
            return ExplicitTmplItem.from_parsed(result)
        else:
            raise Exception(f'Unexpected ParseResult._name: {result._name}')


class ImplicitTmplItem(TmplItem):
    ''' Class representing an implicitly-indexed item Item inside a TemplatedString, less featureful than an explicitly-indexed item. '''
    __slots__ = ('is_implicit', 'carrots', 'index', 'bang')
    carrots: int
    index: int
    bang: bool

    def __init__(self, carrots: int, bang: bool):
        self.is_implicit = True
        self.carrots = carrots
        self.index = None
        self.bang = bang

    @staticmethod
    def from_parsed(result: ParseResults):
        return ImplicitTmplItem(carrots=len(result.get('carrots', '')), bang=bool(result.get('bang')))

    def __repr__(self):
        return f'ImplicitItem(carrots={self.carrots}, index={self.index}, bang={self.bang})'
    def __str__(self):
        return '{%s%s}' % ('^'*self.carrots, '!' if self.bang else '')

    def evaluate(self, scope: ItemScope) -> list[str]:
        if scope is None: raise ItemScopeError('No scope!')
        return [scope.get_item(self.carrots, self.index, self.bang)]


class ExplicitTmplItem(TmplItem):
    ''' Class representing an explicitly-indexed item Item inside a TemplatedString. '''
    Index = NamedTuple('ParsedItemIndex', [
        ('carrots', int),
        ('index', int),
        ('bang', bool)
    ])
    Range = NamedTuple('ParsedItemRange', [
        ('carrots', int),
        ('start', int | None),
        ('end', int | Literal[False] | None),
        ('bang', bool)
    ])

    __slots__ = ('is_implicit', 'indices')
    indices: list[Index | Range]

    def __init__(self, indices: list[Index]):
        self.is_implicit = False
        self.indices = indices

    @staticmethod
    def from_parsed(result: ParseResults):
        indices = []
        for index_result in result['indices']:
            index_result: ParseResults
            carrots = len(index_result.get('carrots', ''))
            bang = index_result.get('bang', '') == '!'
            if 'index' in index_result:
                index = int(index_result['index'])
                indices.append(ExplicitTmplItem.Index(carrots, index, bang))
            else:
                start = int(s) if (s := index_result['interval'].get('start')) else None
                end = int(e) if (e := index_result['interval'].get('end')) else None
                indices.append(ExplicitTmplItem.Range(carrots, start, end, bang))
        return ExplicitTmplItem(indices)

    def __repr__(self):
        indices = []
        for i in self.indices:
            if isinstance(i, ExplicitTmplItem.Index):
                indices.append(f'(carrots={i.carrots}, index={i.index}, bang={i.bang})')
            else:
                indices.append(f'(carrots={i.carrots}, start={i.start}, end={i.end}, bang={i.bang})')
        return 'ExplicitItem([%s])' % ', '.join(indices)
    def __str__(self):
        indices = []
        for i in self.indices:
            if isinstance(i, ExplicitTmplItem.Index):
                indices.append('%s%d%s' % ('^'*i.carrots, i.index, '!' if i.bang else ''))
            else:
                indices.append('%s%s:%s%s' % ('^'*i.carrots, i.start if i.start is not None else '', i.end if i.end is not None else '', '!' if i.bang else ''))
        return '{%s}' % ','.join(indices)

    def evaluate(self, scope: ItemScope) -> list[str]:
        if scope is None: raise ItemScopeError('No scope!')
        items = []
        for index in self.indices:
            if isinstance(index, ExplicitTmplItem.Index):
                items.append(scope.get_item(index.carrots, index.index, index.bang))
            else:
                items.extend(scope.get_items(index.carrots, index.start, index.end, index.bang))
        return items
