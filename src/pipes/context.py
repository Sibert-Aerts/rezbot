from discord import Message, Member, Interaction, TextChannel


class ContextError(ValueError):
    '''Special error used by the Context class when a context string cannot be fulfilled.'''


class ItemScope:
    '''
    An object representing a "scope" of items during a script's execution.
    '''
    items: list[str]
    parent: 'ItemScope | None'
    to_be_ignored: set[str]
    to_be_removed: set[str]

    def __init__(self, parent: 'ItemScope'=None, items: list[str]=None):
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
    # ======== Owned types

    class Origin:
        '''
        An object storing information related to how and why a script's execution was initiated.
        '''    
        class Type:
            UNKNOWN = object()
            DIRECT = object()
            COMMAND = object()
            EVENT = object()
            VIEW_CALLBACK = object()

        name: str
        type: Type
        event: 'Event'

        def __init__(
                self,
                name: str=None,
                type: 'Context.Origin.Type'=Type.UNKNOWN,
                event: 'Event'=None,
            ):
            self.name = name
            self.type = type
            self.event = event

    # ======== Context state

    parent: 'Context | None'

    # ======== Important execution context values

    origin: Origin = None

    author: Member = None
    'Whoever wrote the code currently being executed, if known.'

    activator: Member = None
    'Whoever is causing the current code to be executed, if anyone (?).'

    message: Message = None
    'The "subject", possibly triggering, message of the current execution, if applicable (?)'

    interaction: Interaction = None
    'The triggering interaction of the current execution, if any.'

    channel: TextChannel = None
    'The channel of either the subject message or interaction, if any.'

    # ======== Execution state we rolled into this object for convenience

    item_scope: ItemScope


    def __init__(
        self,
        parent: 'Context'=None,
        *,
        origin: Origin=None,
        author: Member=None,
        activator: Member=None,
        message: Message=None,
        interaction: Interaction=None,

        items: list[str]=None,
    ):
        self.parent = parent

        if parent:
            for attr in ('origin', 'author', 'activator', 'message', 'interaction', 'channel'):
                setattr(self, attr, getattr(parent, attr, None))

        self.origin = origin or self.origin or Context.Origin()
        self.author = author or self.author
        self.activator = activator or self.activator
        self.message = message or self.message
        self.interaction = interaction or self.interaction
        self.channel = (
            (self.message and self.message.channel)
            or (self.interaction and self.interaction.channel)
            or self.channel
        )

        self.item_scope = ItemScope(parent.item_scope if parent else None, items=items)

    # ======================================= ItemContext API ======================================

    def set_items(self, items: list[str]):
        self.item_scope.set_items(items)

    def get_item(self, carrots: int, index: int, bang: bool):
        return self.item_scope.get_item(carrots, index, bang)

    def extract_ignored(self):
        return self.item_scope.extract_ignored()
