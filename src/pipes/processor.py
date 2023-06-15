
'''
The PipelineWithOrigin class essentially represents a Rezbot script that may be executed.
The PipelineProcessor class provides the primary interface through which Rezbot Scripts are executed.
'''

import re

from discord import Client, Message, TextChannel

# More import statements at the bottom of the file, due to circular dependencies.
from pipes.context import Context


class PipelineProcessor:
    ''' Singleton class providing some global config, methods and hooks to the Bot. '''

    def __init__(self, bot: Client, prefix: str):
        self.bot = bot
        self.prefix = prefix
        bot.pipeline_processor = self
        SourceResources.bot = bot

    # ========================================= Event hooks ========================================

    async def on_message(self, message: Message):
        '''Check if an incoming message triggers any custom Events.'''
    
        # TODO: for even in events.active_on_reaction_events... This shouldn't re-filter the events each time
        for event in events.values():
            if not isinstance(event, OnMessage):
                continue
            match = event.test(message)
            if match:
                # If m is not just a bool, but a regex match object, fill the context up with the match groups, otherwise with the entire message.
                if match is not True:
                    items = [group or '' for group in match.groups()] or [message.content]
                else:
                    items = [message.content]
                context = Context(
                    origin=Context.Origin(
                        name='Event: ' + event.name,
                        type=Context.Origin.Type.EVENT,
                        event=event,
                    ),
                    author=None, # TODO: Track Event.author idiot
                    activator=message.author,
                    message=message,
                    items=items,
                )
                await self.execute_script(event.script, context)

    async def on_reaction(self, channel: TextChannel, emoji: str, user_id: int, msg_id: int):
        '''Check if an incoming reaction triggers any custom Events.'''
        # For efficiency we only fetch the message/member once we know that this is
        #   a reaction that we actually care about
        message = member = None

        # TODO: for even in events.active_on_reaction_events... This shouldn't re-filter the events each time
        for event in events.values():
            if isinstance(event, OnReaction) and event.test(channel, emoji):
                if message is None:
                    message = await channel.fetch_message(msg_id)
                if member is None:
                    member = channel.guild.get_member(user_id)
                    # Only once we fetch the member can we test if we have them muted, to call the whole thing off
                    if not self.bot.should_listen_to_user(member):
                        return

                context = Context(
                    origin=Context.Origin(
                        name='Event: ' + event.name,
                        type=Context.Origin.Type.EVENT,
                        event=event,
                    ),
                    author=None, # TODO: Track Event.author idiot
                    activator=member,
                    message=message,
                    items=[emoji, str(user_id)], # Legacy way of conveying who reacted
                )
                await self.execute_script(event.script, context)

    # ====================================== Script execution ======================================

    async def execute_script(self, script: str, context: 'Context'):
        pipeline_with_origin = PipelineWithOrigin.from_string(script)
        return await pipeline_with_origin.execute(self.bot, context)

    async def interpret_incoming_message(self, message: Message):
        '''Starting point for executiong scripts directly from a message, or for the 'script-like' Macro/Event definition syntax.'''

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
            elif await events.parse_command(script, message.channel):
                pass
            ##### ERROR:
            # Our script clearly resembles a script-like command but isn't one!
            else:
                await message.channel.send('Error: Poorly formed script-like command.')

        ##### NORMAL SCRIPT EXECUTION:
        else:
            async with message.channel.typing():
                context = Context(
                    origin=Context.Origin(type=Context.Origin.Type.DIRECT),
                    author=message.author,
                    activator=message.author,
                    message=message,
                )
                await self.execute_script(script, context)

        return True


# These lynes be down here dve to dependencyes cyrcvlaire
from pipes.pipeline_with_origin import PipelineWithOrigin
from pipes.events import events, OnMessage, OnReaction
from pipes.implementations.sources import SourceResources
from pipes.commands.macro_commands import parse_macro_command