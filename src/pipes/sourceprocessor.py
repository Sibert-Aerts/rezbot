
## TODO: put this guy in its own file
## BIG TODO: Integrate Errorlogs, message and all other ExecutionState into this thing? or something.

class ContextError(ValueError):
    '''Special error used by the Context class when a context string cannot be fulfilled.'''

class Context:
    def __init__(self, parent=None, source_processor=None, items=None):
        self.items = items or []
        self.parent = parent
        self.to_be_ignored = set()
        self.to_be_removed = set()

    def set(self, items):
        self.items = items
        self.to_be_ignored = set()
        self.to_be_removed = set()

    def get_item(self, carrots: str, index: str, exclamation: str):
        return self.get_parsed_item(len(carrots), int(index), exclamation == '!')

    def get_parsed_item(self, carrots: int, index: int, bang: bool):
        ctx = self
        # For each ^ go up a context
        for _ in range(carrots):
            if ctx.parent is None: raise ContextError('Out of scope: References a parent context beyond scope!')
            ctx = ctx.parent

        count = len(ctx.items)
        # Make sure the index fits in the context's range of items
        if index >= count: raise ContextError('Out of range: References item {} out of only {} items.'.format(index, count))
        if index < 0: index += count
        if index < 0: raise ContextError('Out of range: Negative index {} for only {} items.'.format(index-count, count))

        # Only flag items to be ignored if we're in the current context (idk how it would work with higher contexts)
        if ctx is self:
            (self.to_be_ignored if bang else self.to_be_removed).add(index)
        return ctx.items[index]

    def extract_ignored(self):
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
