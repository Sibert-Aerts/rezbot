'''
ItemScope and Context are "sibling" classes representing downstream information in the execution of a Rezbot script.

Downstream information meaning: Information from higher scopes/evaluations flowing down into nested scopes/evaluations, with limited info flowing back up.
    (ie. ItemScope does in fact carry a little bit of info upstream, it's not strictly downstream!)

Their 'lifespans' are quite different, though:

A Context is created before script execution ever starts, and is carried all the way into the deepest leaves of a script's execution,
    being used by Sources and Spouts (and soon Pipes?) to perform the fundamental actions that make Scripts useful.

An ItemContext may be created ahead of execution, but often is only created (or deepened) during a Pipeline's execution,
    and carries only as deep as (NB. recursive) TemplatedString evaluation.
    Pipes, Sources and Spouts do not have access to items outside of their scope at all.
'''
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
    parent: 'ItemScope' | None
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
        if index >= count: raise ItemScopeError('Out of range: References item {} out of only {} items.'.format(index, count))
        if index < 0: index += count
        if index < 0: raise ItemScopeError('Out of range: Negative index {} for only {} items.'.format(index-count, count))

        # Only flag items to be ignored if we're in the current scope (idk how it would work with higher scopes)
        if scope is self:
            (self.to_be_ignored if bang else self.to_be_removed).add(index)
        return scope.items[index]

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
        This information will never change, even as Contexts get nested, and as such is bundled in this sub-object.
        '''
        class Type:
            UNKNOWN = object()
            DIRECT = object()
            COMMAND = object()
            EVENT = object()
            INTERACTION_CALLBACK = object()
            EVALUATE_SOURCES_PIPE = object()

        name: str # TODO: Get rid of? Should be interpretable from other info

        type: Type =Type.UNKNOWN
        'Enum denoting where the execution originated from.'
        activator: Member = None
        'Whoever caused this execution.'
        event: 'Event' = None
        'Event that triggered this execution, if any.'

        def __init__(
                self,
                name: str=None,
                type: 'Context.Origin.Type'=Type.UNKNOWN,
                activator: Member=None,
                event: 'Event'=None,
            ):
            self.name = name
            self.type = type
            self.activator = activator
            self.event = event

    # ======== Context state

    parent: 'Context | None'

    # ======== Parent-inherited context values

    origin: Origin = None

    bot: Client = None
    'The bot\'s client, assigned statically at startup.'

    author: Member = None
    'Whoever wrote the code currently being executed, if known.'

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

    def __init__(
        self,
        parent: 'Context'=None,
        *,
        origin: Origin=None,
        author: Member=None,
        message: Message=None,
        interaction: Interaction=None,

        macro: 'Macro'=None,
        arguments: 'Macro'=None,
    ):
        self.parent = parent

        # If a parent Context is given, use most of its properties as defaults
        if parent:
            for attr in ('origin', 'author', 'message', 'interaction', 'channel', 'macro', 'arguments'):
                setattr(self, attr, getattr(parent, attr, None))

        self.origin = origin or self.origin or Context.Origin()
        self.author = author or self.author
        self.message = message or self.message
        self.interaction = interaction or self.interaction
        self.channel = (
            (self.message and self.message.channel)
            or (self.interaction and self.interaction.channel)
            or self.channel
        )

        self.macro = macro or self.macro
        self.arguments = arguments if arguments is not None else self.arguments

    def into_macro(self, macro: 'Macro', arguments: dict[str, str]):
        '''Create a new Context for execution inside the given Macro.'''
        author = None
        if macro.authorId and self.channel:
            author = self.channel.guild.get_member(macro.authorId)
        return Context(self, author=author, macro=macro, arguments=arguments)
