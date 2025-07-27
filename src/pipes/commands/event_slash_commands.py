'''
A module providing a collection of slash commands for interacting with Events.
'''
from typing import Literal

from discord.ext import commands
from discord import app_commands, Interaction, Message

from pipes.core.executable_script import ExecutableScript
from pipes.core.events import Event, ALL_EVENTS
from pipes.core.state import Context, ItemScope
from rezbot_commands import RezbotCommands
from utils.util import normalize_name
from utils.texttools import chunk_lines

from pipes.views.event_views import EventView
from .slash_commands_util import event_type_map, autocomplete_event, choice_to_scriptoid, autocomplete_invoke_command


class EventSlashCommands(RezbotCommands):

    # ================================================= Event Listing =================================================

    @app_commands.command()
    @app_commands.describe(enabled='If given, only list Events enabled (disabled) in this channel')
    async def events(self, interaction: Interaction, enabled: bool=None):
        ''' Display a list of Events. '''
        def reply(*a, **kw):
            if not interaction.response.is_done():
                return interaction.response.send_message(*a, **kw)
            return interaction.channel.send(*a, **kw)

        if not ALL_EVENTS:
            return await reply('No events registered.')

        # Collect enabled/disabled events for the current channel
        enabled_events, disabled_events = [], []
        for event in ALL_EVENTS.values():
            if interaction.channel.id in event.channels: enabled_events.append(event)
            else: disabled_events.append(event)

        infos = []
        if enabled_events and enabled is not False:
            infos += ['**__Enabled:__**'] + ['• ' + str(e) for e in enabled_events]

        if disabled_events and enabled is not True:
            infos += ['**__Disabled:__**'] + [', '.join(e.name for e in disabled_events)]

        for chunk in chunk_lines(infos):
            await reply(chunk)

    # ================================================ Event Management ===============================================

    event_group = app_commands.Group(name='event', description='Define, redefine, describe or delete Events')
    ''' The `/event <action>` command group'''

    @event_group.command(name='define')
    @app_commands.describe(
        name='The name of the new Event',
        event_type='The type of Event',
        trigger='The type-dependent trigger',
        code='The code which is triggered',
        force='Set to True to ignore static errors and save the Event anyway',
    )
    @app_commands.rename(event_type='type')
    async def event_define(self, interaction: Interaction,
        name: str,
        event_type: Literal['OnMessage', 'OnReaction', 'OnInvoke'],
        trigger: str,
        code: str,
        force: bool=False,
    ):
        ''' Define a new Event and enable it in this channel. '''
        reply = interaction.response.send_message
        EventType = event_type_map[event_type]

        name = normalize_name(name)
        if name in ALL_EVENTS:
            return await reply(f'An Event called `{name}` already exists, try the `/event edit` command.')

        ## Instantiate the new Event instance
        try:
            event = EventType.from_trigger_str(name=name, author_id=interaction.user.id, channels=[interaction.channel.id], script=code, trigger=trigger)
        except Exception as e:
            return await reply(f'Failed to define new Event `{name}`:\n\t{type(e).__name__}: {str(e)}', ephemeral=True)

        ## Check for static errors
        errors = event.get_static_errors()
        if not force and errors.terminal:
            # TODO: View with "force anyway" button
            return await reply(
                f'Could not define new Event `{name}` as errors were found.\nYou can either fix these errors, or re-run this command with `force: True`.',
                embed=errors.embed('code for Event: ' + name),
                ephemeral=True,
            )

        ## Finally: Actually assign the event to the registry
        ALL_EVENTS[name] = event
        view = EventView(self.bot, event, ALL_EVENTS, interaction.channel)
        view.set_message(await reply(f'Successfully defined a new Event.', embed=event.embed(bot=self.bot, channel=interaction.channel), view=view))

    @event_group.command(name='edit')
    @app_commands.describe(
        event_choice='The Event to edit',
        event_type='If given, the Event\'s new type',
        trigger='If given, the Event\'s new type-dependent trigger',
        code='If given, the Event\'s new code',
        force='Set to True to ignore static errors and save the Event anyway',
    )
    @app_commands.rename(event_choice='event')
    @app_commands.autocomplete(event_choice=autocomplete_event())
    async def event_edit(self, interaction: Interaction,
        event_choice: str,
        event_type: Literal['OnMessage', 'OnReaction', 'OnInvoke']=None,
        trigger: str=None,
        code: str=None,
        force: bool=False
    ):
        ''' Redefine one or more fields on an existing Event. '''
        reply = interaction.response.send_message

        try:
            event, _ = choice_to_scriptoid(event_choice, Event)
        except:
            return await reply(f'Failed to update Event, likely due to nonexistent Event.', ephemeral=True)

        ## Write the various properties
        if event_type is not None:
            EventType = event_type_map[event_type]
            if trigger is None:
                return await reply(f'When changing Event Type, the trigger must be given as well.')
            event = EventType.from_trigger_str(name=event.name, desc=event.desc, author_id=event.author_id, channels=event.channels, script=event.script, trigger=trigger)
            ALL_EVENTS[event.name] = event
        elif trigger is not None:
            event.set_trigger(trigger)
        if code is not None:
            event.script = code
            errors = event.get_static_errors()
            if not force and errors.terminal:
                # TODO: View with "force anyway" button
                return await reply(
                    f'Could not update Event `{event.name}` as errors were found.\nYou can either fix these errors, or re-run this command with `force: True`.',
                    embed=errors.embed('code for Event: ' + event.name),
                )

        ALL_EVENTS.write()
        view = EventView(self.bot, event, ALL_EVENTS, interaction.channel)
        view.set_message(await reply(f'Successfully edited the Event.', embed=event.embed(bot=self.bot, channel=interaction.channel), view=view))

    @event_group.command(name='delete')
    @app_commands.describe(event_choice='The Event to delete')
    @app_commands.rename(event_choice='event')
    @app_commands.autocomplete(event_choice=autocomplete_event())
    async def event_delete(self, interaction: Interaction, event_choice: str):
        ''' Delete an Event. '''
        reply = interaction.response.send_message

        try:
            event, _ = choice_to_scriptoid(event_choice, Event)
        except:
            return await reply(f'Command failed, likely due to nonexistent Event.', ephemeral=True)

        del ALL_EVENTS[event.name]
        await reply(f'Successfully deleted Event `{event.name}`.')

    async def _event_set_enabled(self, interaction: Interaction, event_choice: str, enable: bool):
        reply = interaction.response.send_message

        try:
            event, _ = choice_to_scriptoid(event_choice, Event)
        except:
            return await reply(f'Command failed, likely due to nonexistent Event.', ephemeral=True)

        if enable:
            if interaction.channel.id in event.channels:
                await reply(f'Event {event.name} is already enabled in {interaction.channel.mention}.')
            else:
                event.channels.append(interaction.channel.id)
                ALL_EVENTS.write()
                await reply(f'Event {event.name} has been enabled in {interaction.channel.mention}.')
        else:
            if interaction.channel.id not in event.channels:
                await reply(f'Event {event.name} is already disabled in {interaction.channel.mention}.')
            else:
                event.channels.remove(interaction.channel.id)
                ALL_EVENTS.write()
                await reply(f'Event {event.name} has been disabled in {interaction.channel.mention}.')

    @event_group.command(name='enable')
    @app_commands.describe(event_choice='The Event to enable')
    @app_commands.rename(event_choice='event')
    @app_commands.autocomplete(event_choice=autocomplete_event(enabled=False))
    async def event_enable(self, interaction: Interaction, event_choice: str):
        ''' Enable an Event in this channel. '''
        await self._event_set_enabled(interaction, event_choice, enable=True)

    @event_group.command(name='disable')
    @app_commands.describe(event_choice='The Event to disable')
    @app_commands.rename(event_choice='event')
    @app_commands.autocomplete(event_choice=autocomplete_event(enabled=True))
    async def event_disable(self, interaction: Interaction, event_choice: str):
        ''' Disable an Event in this channel. '''
        await self._event_set_enabled(interaction, event_choice, enable=False)


    # ================================================ Event Invocation ===============================================

    @app_commands.command()
    @app_commands.describe(
        command='Determines which Event(s) to invoke.',
        message='The "message" text received by the Event script.',
    )
    @app_commands.autocomplete(command=autocomplete_invoke_command)
    async def invoke(self, interaction: Interaction, command: str, message: str=''):
        ''' Invoke an "On Invoke" event. '''
        if not self.bot.should_listen_to_user(interaction.user):
            return

        for event in ALL_EVENTS.on_invoke_events:
            if not event.test(interaction.channel, command):
                continue
            # Fetch Event's author
            author = interaction.guild.get_member(event.author_id) or self.bot.get_user(event.author_id)
            # Create execution context
            context = Context(
                origin=Context.Origin(
                    type=Context.Origin.Type.EVENT,
                    activator=interaction.user,
                    event=event,
                ),
                author=author,
                interaction=interaction,
                arguments={'message': message},
            )
            scope = ItemScope(items=[message])
            await ExecutableScript.execute_from_string(event.script, context, scope)

            # In case the script does not resolve the interaction. There is no way to resolve a slash command without a reply, so reply.
            if not interaction.response.is_done():
                await interaction.response.send_message("Done.", ephemeral=True)

    async def context_menu_execute_script(self, interaction: Interaction, message: Message):
        ''' Show a modal allowing a user to write and then execute a script (on the selected message). '''
        if not self.bot.should_listen_to_user(interaction.user):
            return
        await interaction.response.send_modal(ExecuteScriptModal(self.bot, interaction, message))


# Load the bot cog
async def setup(bot: commands.Bot):
    event_slash_commands = EventSlashCommands(bot)
    await bot.add_cog(event_slash_commands)

    # Add the context menu command, for some reason it has to be like this
    bot.tree.add_command(app_commands.context_menu(name="Execute script")(event_slash_commands.context_menu_execute_script))


# Down here due to circular dependencies
from pipes.views.command_views import ExecuteScriptModal
