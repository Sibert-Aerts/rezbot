
'''
The PipelineProcessor class provides the primary interface through which Rezbot Scripts are executed.
'''

import re

from discord import Client, Message, TextChannel

from .state import ErrorLog, Context, ItemScope
from .executable_script import ExecutableScript
from .events import ALL_EVENTS
from pipes.commands.macro_commands import parse_macro_command


class PipelineProcessor:
    ''' Singleton class providing some global config, methods and hooks to the Bot. '''

    def __init__(self, bot: Client, prefix: str):
        self.bot = bot
        self.prefix = prefix
        Context.bot = bot

    # ========================================= Event hooks ========================================

    async def on_message(self, message: Message):
        '''Check if an incoming message triggers any custom Events.'''
        for event in ALL_EVENTS.on_message_events:
            match: re.Match = event.test(message)
            if not match: continue
            if isinstance(match, re.Match):
                # Fill the starting items with the groups in order of appearance ({i} == match[i+1]) (LEGACY, do not change numbering!),
                #   unless there are no match groups at all, in which case {0} is filled in as the full message (inconsistent, but LEGACY)
                items = match.groups(default='') or (message.content,)
                # Fill the arguments with each group, mapped both by index ({arg i} == match[i]) and by name ({arg name} == match[name]).
                #   Note: Argument values may be None, which is a special case that can be handled via {arg x default='...'}
                arguments = {str(i+1): m for i, m in enumerate(match.groups())}
                arguments['0'] = match[0]
                arguments.update(match.groupdict())

            # Fetch the Event's author
            author = message.guild.get_member(event.author_id) or self.bot.get_user(event.author_id)
            # Create execution context
            context = Context(
                origin=Context.Origin(
                    type=Context.Origin.Type.EVENT,
                    activator=message.author,
                    event=event,
                ),
                author=author,
                message=message,
                arguments=arguments,
            )
            await self.execute_script(event.script, context, ItemScope(items=items))

    async def on_reaction(self, channel: TextChannel, emoji: str, user_id: int, msg_id: int):
        '''Check if an incoming reaction triggers any custom Events.'''
        # For efficiency we only fetch the message/member once we know that this is
        #   a reaction that we actually care about
        message = member = None
        for event in ALL_EVENTS.on_reaction_events:
            if not event.test(channel, emoji):
                continue
            if message is None or member is None:
                message = await channel.fetch_message(msg_id)
                member = channel.guild.get_member(user_id)
                # Only once we fetch the member can we test if we have them muted, to call the whole thing off
                if not self.bot.should_listen_to_user(member):
                    return
            # Fetch the Event's author
            author = channel.guild.get_member(event.author_id) or self.bot.get_user(event.author_id)
            # Create execution context
            context = Context(
                origin=Context.Origin(
                    type=Context.Origin.Type.EVENT,
                    activator=member,
                    event=event,
                ),
                author=author,
                message=message,
                arguments={'emoji': emoji},
            )
            scope = ItemScope(items=[emoji, str(user_id)]) # Legacy way of conveying who reacted
            await self.execute_script(event.script, context, scope)

    # ====================================== Script execution ======================================

    @staticmethod
    async def execute_script(script: str, context: Context, scope: ItemScope=None):
        try:
            executable_script = ExecutableScript.from_string(script)
        except Exception as e:
            # Make a single-use error log so we can use the send_error_log method
            errors = ErrorLog().log(f'🛑 **Unexpected script parsing error:**\n {type(e).__name__}: {e}', terminal=True)
            await ExecutableScript.send_error_log(context, errors)
            raise e
        else:
            await executable_script.execute(context, scope)

    async def interpret_incoming_message(self, message: Message):
        '''
        Starting point for executing scripts directly from a message, or for the 'script-like' Macro/Event definition syntax.
        '''

        # Test for the script prefix and remove it (pipe_prefix in config.ini, default: '>>')
        if not message.content.startswith(self.prefix):
            return False
        script = message.content[len(self.prefix):]

        ## Check if it's a script or some kind of script-like command
        if re.match(r'\s*(NEW|EDIT|DESC).*::', script, re.I):
            ##### MACRO DEFINITION:
            # >> (NEW|EDIT|DESC) <type> <name> :: <code>
            if await parse_macro_command(self.bot, script, message):
                pass
            ##### EVENT DEFINITION:
            # >> (NEW|EDIT) EVENT <name> ON MESSAGE <regex> :: <code>
            elif await ALL_EVENTS.parse_command(self.bot, script, message):
                pass
            ##### ERROR:
            # Our script clearly resembles a script-like command but isn't one!
            else:
                await message.channel.send('Error: Poorly formed script-like command.')

        ##### NORMAL SCRIPT EXECUTION:
        else:
            async with message.channel.typing():
                context = Context(
                    origin=Context.Origin(
                        type=Context.Origin.Type.DIRECT,
                        activator=message.author,
                    ),
                    author=message.author,
                    message=message,
                )
                await self.execute_script(script, context)

        return True
