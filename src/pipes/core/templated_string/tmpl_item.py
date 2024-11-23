from pyparsing import ParseResults
from typing import Literal, NamedTuple

from ..context import ItemScope, ItemScopeError


class TmplItem:
    ''' Class representing an Item inside a TemplatedString. '''
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

    __slots__ = ('is_implicit', 'indices', 'implicit_carrots', 'implicit_index', 'implicit_bang')

    indices: list[Index | Range]
    # Implicit
    is_implicit: bool
    implicit_carrots: int
    implicit_index: int
    implicit_bang: bool

    def __init__(self, is_implicit: bool, indices: list[Index]=None, implicit_carrots: int=None, implicit_bang: bool=None):
        self.is_implicit = is_implicit
        self.indices = indices
        # TODO: Deprecate implicit_carrots syntax, and maybe also implicit_bang,
        #   if you want to be implicit you can't also be doing fancy things?
        self.implicit_carrots = implicit_carrots
        self.implicit_index = None
        self.implicit_bang = implicit_bang

    @staticmethod
    def from_parsed(result: ParseResults):
        if result._name == 'implicit_item':
            return TmplItem(is_implicit=True, implicit_carrots=len(result.get('carrots', '')), implicit_bang=bool(result.get('bang')))

        elif result._name == 'explicit_item':
            indices = []
            for index_result in result['indices']:
                index_result: ParseResults
                carrots = len(index_result.get('carrots', ''))
                bang = index_result.get('bang', '') == '!'
                if 'index' in index_result:
                    index = int(index_result['index'])
                    indices.append(TmplItem.Index(carrots, index, bang))
                else:
                    start = int(s) if (s := index_result['interval'].get('start')) else None
                    end = int(e) if (e := index_result['interval'].get('end')) else None
                    indices.append(TmplItem.Range(carrots, start, end, bang))
            return TmplItem(is_implicit=False, indices=indices)

        else:
            raise Exception(f'Unexpected ParseResult._name: {result._name}')

    def __repr__(self):
        if self.is_implicit:
            return f'Item(is_implicit=True, carrots={self.implicit_carrots}, index={self.implicit_index}, bang={self.implicit_bang})'
        indices = []
        for i in self.indices:
            if isinstance(i, TmplItem.Index):
                indices.append(f'(carrots={i.carrots}, index={i.index}, bang={i.bang})')
            else:
                indices.append(f'(carrots={i.carrots}, start={i.start}, end={i.end}, bang={i.bang})')
        return 'Item(is_implicit=False, [%s])' % ', '.join(indices)
    def __str__(self):
        if self.is_implicit:
            return '{%s%s}' % ('^'*self.implicit_carrots, '!' if self.implicit_bang else '')
        indices = []
        for i in self.indices:
            if isinstance(i, TmplItem.Index):
                indices.append('%s%d%s' % ('^'*i.carrots, i.index, '!' if i.bang else ''))
            else:
                indices.append('%s%s:%s%s' % ('^'*i.carrots, i.start if i.start is not None else '', i.end if i.end is not None else '', '!' if i.bang else ''))
        return '{%s}' % ','.join(indices)

    def evaluate(self, scope: ItemScope) -> list[str]:
        if scope is None: raise ItemScopeError('No scope!')
        if self.is_implicit:
            return [scope.get_item(0, self.implicit_index, self.implicit_bang)]
        items = []
        for index in self.indices:
            if isinstance(index, TmplItem.Index):
                items.append(scope.get_item(index.carrots, index.index, index.bang))
            else:
                items.extend(scope.get_items(index.carrots, index.start, index.end, index.bang))
        return items
