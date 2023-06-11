from discord import Message, Member, Interaction

## BIG TODO: Integrate Errorlogs, message and all other ExecutionState into this thing? or something.

class ContextError(ValueError):
    '''Special error used by the Context class when a context string cannot be fulfilled.'''


class ItemScope:
    items: list[str]
    parent: 'ItemScope | None'
    to_be_ignored: set[str]
    to_be_removed: set[str]

    def __init__(self, parent: 'Context'=None, items: list[str]=None):
        self.items = items or []
        self.parent = parent
        self.to_be_ignored = set()
        self.to_be_removed = set()

    def set_items(self, items: list[str]):
        self.items = items
        self.to_be_ignored = set()
        self.to_be_removed = set()

    def get_item(self, carrots: int, index: int, bang: bool) -> str:
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


class Context:
    '''
    An object providing context to the execution/evaluation of a Rezbot script.
    '''
    parent: 'Context | None'

    # ======== Important execution context values

    author: Member = None
    'Whoever wrote the code currently being executed, if known.'
    activator: Member = None
    'Whoever is causing the current code to be executed, if anyone (?).'
    message: Message = None
    'The "subject", possibly triggering, message of the current execution, if applicable (?)'
    interaction: Interaction = None
    'The triggering interaction of the current execution, if any.'

    # ======== Execution state we rolled into this object for convenience

    item_scope: ItemScope

    def __init__(
        self,
        parent: 'Context'=None,
        *,
        author: Member=None,
        activator: Member=None,
        message: Message=None,
        interaction: Interaction=None,

        items: list[str]=None,
    ):
        self.parent = parent

        if parent:
            for attr in ('author', 'activator', 'message', 'interaction'):
                setattr(self, attr, getattr(parent, attr, None))

        self.author = author or self.author
        self.activator = activator or self.activator
        self.message = message or self.message
        self.interaction = interaction or self.interaction

        if parent:
            self.item_scope = ItemScope(parent.item_scope)
        else:
            self.item_scope = ItemScope(items=items)

    # ==================================== ItemContext API Proxy ===================================

    def set_items(self, items: list[str]):
        self.item_scope.set_items(items)

    def get_item(self, carrots: int, index: int, bang: bool):
        return self.item_scope.get_item(carrots, index, bang)

    def extract_ignored(self):
        return self.item_scope.extract_ignored()
