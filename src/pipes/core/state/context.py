'''
ItemScope and Context are "sibling" classes representing downstream information in the execution of a Rezbot script.

Downstream information meaning: Information from higher scopes/evaluations flowing down into nested scopes/evaluations, with limited info flowing back up.
    (ie. ItemScope does in fact carry a little bit of info upstream, it's not strictly downstream!)

Their 'lifespans' are quite different, though:

A Context is created before script execution ever starts, and is carried all the way into the deepest leaves of a script's execution,
    giving invoked Sources and Spouts (and one day Pipes?) important information about the script's execution context.
A modified Context is created when execution passes into a Macro, placing the Macro's arguments in context, as well as meta-information about the Macro.

An ItemScope may be created ahead of execution, but often is only created (or deepened) during a Pipeline's execution,
    and carries only as deep as (NB. recursive) TemplatedString evaluation.
    Pipes, Sources and Spouts do not have access to items outside of their scope at all.
'''

from discord import Message, Member, Interaction, TextChannel, Client

from .bot_state import BOT_STATE

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pipes.core.events import Event
    from pipes.core.macros import Macro
    from pipes.views.generic_views import RezbotButton


class ContextError(ValueError):
    '''Special error to be used when the current Context does not allow a certain operation.'''


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
            DIRECT = object()
            DIRECT_TARGETING_MESSAGE = object()
            COMMAND = object()
            EVENT = object()
            INTERACTION_CALLBACK = object()
            EVALUATE_SOURCES_PIPE = object()

        name: str
        'Human understandable name explaining who/what/where this execution originated from.'
        type: Type
        'Enum denoting where the execution originated from.'
        activator: Member = None
        'Whoever caused this execution.'
        event: 'Event' = None
        'Event that triggered this execution, if any.'

        def __init__(
                self,
                type: 'Context.Origin.Type',
                *,
                name: str=None,
                activator: Member,
                event: 'Event'=None,
            ):
            # Default formatted names
            if name is None:
                if event:
                    name = f'Event: {event.name}'
                elif type == Context.Origin.Type.DIRECT:
                    name = f'{activator.display_name}\'s script'
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

    button: 'RezbotButton' = None
    'The specific button that triggered this interaction.'

    # == Macro context values

    macro: 'Macro' = None
    'Inside a Macro call, the Macro that is being called'

    arguments: dict[str, str|None] = None
    'Arguments passed into the current Event or Macro, accessible through {arg param_name}'

    # ====================================== Creating Context ======================================

    def __init__(
        self,
        parent: 'Context'=None,
        *,
        origin: Origin=None,
        author: Member=None,
        message: Message=None,
        interaction: Interaction=None,
        button=None,

        macro: 'Macro'=None,
        arguments: dict[str, str|None]=None,
    ):
        if (not origin and not parent) or (origin and parent):
            raise ValueError('Context must have either an Origin or a parent Context.')
        self.parent = parent
        self.origin = origin or parent.origin

        # If a parent Context is given, use most of its properties as defaults
        if parent:
            for attr in ('author', 'message', 'interaction', 'channel', 'macro', 'arguments', 'button'):
                setattr(self, attr, getattr(parent, attr, None))

        self.author = author or self.author
        self.message = message or self.message
        self.interaction = interaction or self.interaction
        self.channel = (
            (self.message and self.message.channel)
            or (self.interaction and self.interaction.channel)
            or self.channel
        )
        self.button = button or self.button

        self.macro = macro or self.macro
        self.arguments = arguments if arguments is not None else self.arguments

    def into_macro(self, macro: 'Macro', arguments: dict[str, str]) -> 'Context':
        '''Create a new child Context for execution inside the given Macro.'''
        author = None
        if macro.authorId and self.channel:
            author = self.channel.guild.get_member(macro.authorId)
        return Context(self, author=author, macro=macro, arguments=arguments)

    # ======================================== Using Context =======================================

    async def get_member(self, key: str):
        '''
        Gets a contextual Discord Member (or sometimes User) from the given 'key'.
        '''
        key = key.strip().lower()

        ## CASE 1; ME: The person who activated the script
        if key in ('me', 'my'):
            return self.origin.activator

        ## CASE 2; THEY: The author of 'that' message (cf. get_message)
        if key in ('they', 'them', 'their'):
            msg = await self.get_message('that')
            return msg.author

        ## CASE 3; BOT: The bot itself
        if key == 'bot':
            bot = self.bot.user
            if self.channel.guild:
                # Member has more contextual info than just User
                bot = self.channel.guild.get_member(bot.id)
            return bot

        ## FINAL CASE: Member's unique handle or ID
        members = self.channel.guild.members

        ## FINAL.1: Find by user handle (AKA 'name' in Discord terminology)
        match = next((m for m in members if m.name == key), None)
        if match:
            return match

        ## FINAL.2: Find by ID
        try:
            member_id = int(key)
            match = next((m for m in members if m.id == member_id), None)
        except:
            pass
        if match:
            return match

        # FINAL: Could not find anyone
        raise ContextError(f'No Member found by handle or ID "{key}".')

    async def get_message(self, key: str):
        '''
        Gets a contextual Discord Message from the given 'key'.
        '''
        key = key.strip().lower()

        ## CASE 1; THIS: The current subject message
        if key == 'this':
            return self.message

        ## CASE 2; THAT: The message being directly targeted, being replied to, or immediately preceding the current message
        if key == 'that':
            if (
                self.origin.type is Context.Origin.Type.DIRECT_TARGETING_MESSAGE
                or (self.origin.event and self.origin.event.targets_current_message)
            ):
                return self.message
            elif self.message.reference and self.message.reference.message_id:
                msg_id = self.message.reference.message_id
                return await self.channel.fetch_message(msg_id)
            else:
                # Fetch the 2nd item from history (TODO: Race condition with new messages since this script was invoked)
                return [ msg async for msg in self.message.channel.history(limit=2) ][1]

        ## CASE 3: Starts with poundsign (#): Earmarked message(s)
        if len(key) > 1 and key.startswith("#"):
            earmark = key[1:]
            messages = BOT_STATE.earmarked_messages.get(earmark)
            if not messages:
                raise ValueError(f'Could not find message(s) by earmark "{earmark}".')
            return messages[0]

        ## FINAL CASE; integer: Message ID in the current channel
        int_key = None
        try:
            int_key = int(key)
        except:
            raise ValueError(f'Invalid message key "{key}".')

        return await self.channel.fetch_message(int_key)

