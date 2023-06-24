
'''
The PipelineWithOrigin class essentially represents a Rezbot script that may be executed.
The PipelineProcessor class provides the primary interface through which Rezbot Scripts are executed.
'''

import re

from discord import Client, Message, TextChannel

# More import statements at the bottom of the file, due to circular dependencies.
from pipes.context import Context, ItemScope
from pipes.logger import ErrorLog


class PipelineProcessor:
    ''' Singleton class providing some global config, methods and hooks to the Bot. '''

    def __init__(self, bot: Client, prefix: str):
        self.bot = bot
        self.prefix = prefix
        bot.pipeline_processor = self
        SourceResources.bot = bot
        Context.bot = bot

    # ========================================= Event hooks ========================================

    async def on_message(self, message: Message):
        '''Check if an incoming message triggers any custom Events.'''
    
        # TODO: for even in events.active_on_reaction_events... This shouldn't re-filter the events each time
        for event in events.values():
            if not isinstance(event, OnMessage):
                continue
            match: re.Match = event.test(message)
            if match:
                if match is not True and (groups := match.groups(default='')):
                    # If match is indeed a regex Match object with regex Match Groups in it:
                    #   Fill the starting items with the groups in order of appearance ({i} == match[i+1]) (LEGACY, do not change numbering!)
                    #   Fill the arguments with each group, mapped both by index ({arg i} == match[i]) and by name ({arg name} == match[name]).
                    items = list(groups)
                    arguments = {str(i+1): m for i, m in enumerate(match.groups())}
                    arguments['0'] = match[0]
                    arguments.update(match.groupdict())
                else:
                    # Otherwise: Item 0 and argument 0 are simply the full message.
                    #  I don't think this one ever actually happens, since the only OnMessage trigger is a regex, but who knows.
                    items = [message.content]
                    arguments = {'0': message.content}
                # Fetch Event's author
                author = message.guild.get_member(event.author_id) or self.bot.get_user(event.author_id)
                # Create execution context
                context = Context(
                    origin=Context.Origin(
                        name='Event: ' + event.name,
                        activator=message.author,
                        type=Context.Origin.Type.EVENT,
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
                # Fetch Event's author
                author = channel.guild.get_member(event.author_id) or self.bot.get_user(event.author_id)
                # Create execution context
                context = Context(
                    origin=Context.Origin(
                        name='Event: ' + event.name,
                        activator=member,
                        type=Context.Origin.Type.EVENT,
                        event=event,
                    ),
                    author=author,
                    message=message,
                    arguments={'emoji': emoji},
                )
                scope = ItemScope(items=[emoji, str(user_id)]) # Legacy way of conveying who reacted
                await self.execute_script(event.script, context, scope)

    # ====================================== Script execution ======================================

    async def execute_script(self, script: str, context: Context, scope: ItemScope=None):
        try:
            pipeline_with_origin = PipelineWithOrigin.from_string(script)
        except Exception as e:
            errors = ErrorLog().log(f'🛑 **Unexpected script parsing error:**\n {type(e).__name__}: {e}', terminal=True)
            await PipelineWithOrigin.send_error_log(context, errors)
            raise e
        else:
            return await pipeline_with_origin.execute(context, scope)

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
            elif await events.parse_command(self.bot, script, message):
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
                        name=f'{message.author.display_name}\'s script',
                        type=Context.Origin.Type.DIRECT,
                        activator=message.author,    
                    ),
                    author=message.author,
                    message=message,
                )
                await self.execute_script(script, context)

        return True


# These lynes be down here dve to dependencyes cyrcvlaire
from pipes.pipeline_with_origin import PipelineWithOrigin
from pipes.events import events, OnMessage, OnReaction
from pipes.implementations.sources import SourceResources
from pipes.commands.macro_commands import parse_macro_command
