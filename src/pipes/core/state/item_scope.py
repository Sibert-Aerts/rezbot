'''
For a comparison between Context and ItemScope, cf. context.py
'''

class ItemScopeError(ValueError):
    '''Special error used by the ItemScope class when an item does not exist.'''


class ItemScope:
    '''
    An object representing a "scope" of items during a script's execution, with possible parent scopes.
    '''
    items: list[str]
    parent: 'ItemScope | None'
    to_be_ignored: set[str]
    to_be_removed: set[str]

    def __init__(self, parent: 'ItemScope'=None, items: list[str]=None):
        self.parent = parent
        self.items = items or []
        self.to_be_ignored = set()
        self.to_be_removed = set()

    def set_items(self, items: list[str]):
        '''In-place replace this scope with a subsequent sibling to the same parent scope.'''
        self.items = items
        self.to_be_ignored = set()
        self.to_be_removed = set()

    def get_item(self, carrots: int, index: int, bang: bool) -> str:
        '''Retrieves a specific item from this scope or a parent's scope, and possibly marks it for ignoring/removal.'''
        scope = self
        # For each ^ go up a scope
        for _ in range(carrots):
            if scope.parent is None: raise ItemScopeError('Out of scope: References a parent scope beyond scope.')
            scope = scope.parent

        count = len(scope.items)
        # Make sure the index fits in the scope's range of items
        if count == 0: raise ItemScopeError('No items in scope.')
        if index >= count: raise ItemScopeError('Out of range: Index {} out of only {} items.'.format(index, count))
        if index < 0: index += count
        if index < 0: raise ItemScopeError('Out of range: Negative index {} out of only {} items.'.format(index-count, count))

        # Only flag items to be ignored if we're in the current scope (idk how it would work with higher scopes)
        if scope is self:
            (self.to_be_ignored if bang else self.to_be_removed).add(index)
        return scope.items[index]

    def get_items(self, carrots: int, start: int | None, end: int | None, bang: bool) -> list[str]:
        '''Retrieves a range of items from this scope or a parent's scope, and possibly marks them for ignoring/removal.'''
        scope = self
        # For each ^ go up a scope
        for _ in range(carrots):
            if scope.parent is None: raise ItemScopeError('Out of scope: References a parent scope beyond scope.')
            scope = scope.parent

        count = len(scope.items)
        # Make sure the start index fits in the scope's range of items
        if start is None: start = 0
        else:
            if start > count: raise ItemScopeError('Out of range: Start index {} out of only {} items.'.format(start, count))
            if start < 0: start += count
            if start < 0: raise ItemScopeError('Out of range: Negative start index {} out of only {} items.'.format(start-count, count))
        # Make sure the end index fits in the scope's range of items
        if end is None: end = count
        else:
            if end > count: raise ItemScopeError('Out of range: End index {} out of only {} items.'.format(end, count))
            if end < 0: end += count
            if end < 0: raise ItemScopeError('Out of range: Negative end index {} out of only {} items.'.format(end-count, count))

        # Only flag items to be ignored if we're in the current scope (idk how it would work with higher scopes)
        if scope is self:
            (self.to_be_ignored if bang else self.to_be_removed).update(range(start, end))
        return scope.items[start:end]

    def extract_ignored(self) -> tuple[set[str], list[str]]:
        ### Merge the sets into a clear view:
        # If "conflicting" instances occur (i.e. both {0} and {0!}) give precedence to the {0!}
        # Since the ! is an intentional indicator of what they want to happen; Do not remove the item
        to_be = [ (i, True) for i in self.to_be_removed.difference(self.to_be_ignored) ] + [ (i, False) for i in self.to_be_ignored ]

        # Finnicky list logic for ignoring/removing the appropriate indices
        to_be.sort(key=lambda x: x[0], reverse=True)
        ignored = []
        items = list(self.items)
        for i, rem in to_be:
            if not rem: ignored.append(self.items[i])
            del items[i]
        ignored.reverse()

        return ignored, items
