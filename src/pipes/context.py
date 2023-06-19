from discord import Message, Member, Interaction, TextChannel, Client

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    # NOTE: These are only here for type annotation purposes, no code can actually access these.
    from pipes.events import Event
    from pipes.macros import Macro


class ItemScopeError(ValueError):
    '''Special error used by the ItemScope class when an item does not exist.'''

class ContextError(ValueError):
    '''Special error to be used when the current Context does not allow a certain operation.'''


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
            if ctx.parent is None: raise ItemScopeError('Out of scope: References a parent context beyond scope!')
            ctx = ctx.parent

        count = len(ctx.items)
        # Make sure the index fits in the context's range of items
        if index >= count: raise ItemScopeError('Out of range: References item {} out of only {} items.'.format(index, count))
        if index < 0: index += count
        if index < 0: raise ItemScopeError('Out of range: Negative index {} for only {} items.'.format(index-count, count))

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
    An object providing context downstream along the execution/evaluation of a Rezbot script.
    '''
    # ======== Owned types

    class Origin:
        '''
        An object storing information related to how and why a script's execution was initiated.
        '''
        # TODO: Does this need to be a sub-object? The reason I made the separation is that
        #   every single sub-Context should not change any of the values contained within it;
        #   i.e. they're a kind of 'higher context' than a single Context strictly represents.
        # But does that need to be a different sub-object, isn't that just annoying?
        # Also strictly speaking, most of the properties of Context don't actually ever need to change,
        #   only `author` and that's only in the context of a Macro, so you could make that like macro_author,
        #   or like a property that either returns macro.author or origin.author or whatev.
        class Type:
            UNKNOWN = object()
            DIRECT = object()
            COMMAND = object()
            EVENT = object()
            INTERACTION_CALLBACK = object()
            EVALUATE_SOURCES_PIPE = object()

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

    # ======== Parent-inherited context values

    origin: Origin = None

    bot: Client = None
    'The bot\'s client.' # TODO: This is rarely filled in

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
    
    # == Macro context values

    macro: 'Macro' = None
    'Inside a Macro call, the Macro that is being called'

    arguments: dict[str, str] = None
    'Arguments passed into the current Event or Macro, accessible through {arg param_name}'

    # ======== Execution state we rolled into this object for "convenience"

    # TODO: Kick this guy back out, sure we're both "downstream", but this guy has different start and end points to its life cycle.
    #   Let him live his own life and not interrupt with ours, even if that means one more variable we're passing around for a little bit of time.
    item_scope: ItemScope


    def __init__(
        self,
        parent: 'Context'=None,
        *,
        origin: Origin=None,
        bot: Client=None,
        author: Member=None,
        activator: Member=None,
        message: Message=None,
        interaction: Interaction=None,

        macro: 'Macro'=None,
        arguments: 'Macro'=None,

        items: list[str]=None,
    ):
        self.parent = parent

        # If a parent Context is given, use most of its properties as defaults
        if parent:
            for attr in ('origin', 'bot', 'author', 'activator', 'message', 'interaction', 'channel', 'macro', 'arguments'):
                setattr(self, attr, getattr(parent, attr, None))

        self.origin = origin or self.origin or Context.Origin()
        self.bot = bot or self.bot
        self.author = author or self.author
        self.activator = activator or self.activator
        self.message = message or self.message
        self.interaction = interaction or self.interaction
        self.channel = (
            (self.message and self.message.channel)
            or (self.interaction and self.interaction.channel)
            or self.channel
        )

        self.macro = macro or self.macro
        self.arguments = arguments if arguments is not None else self.arguments

        # TODO: Maybe bad idea that this is inside Context, I'm definitely not wrapping my mind around it very well
        if items is None:
            self.item_scope = ItemScope(parent.item_scope if parent else None)
        else:
            self.item_scope = ItemScope(items=items)

    def into_macro(self, macro: 'Macro', arguments: dict[str, str]):
        '''Create a new Context for execution inside the given Macro.'''
        author = None
        if macro.authorId and self.channel:
            author = self.channel.guild.get_member(macro.authorId)
        return Context(self, author=author, macro=macro, arguments=arguments)


    # ======================================= ItemContext API ======================================

    def set_items(self, items: list[str]):
        self.item_scope.set_items(items)

    def get_item(self, carrots: int, index: int, bang: bool):
        return self.item_scope.get_item(carrots, index, bang)

    def extract_ignored(self):
        return self.item_scope.extract_ignored()
