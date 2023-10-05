'''
A module providing a collection of slash commands for interacting with Events.
'''
from typing import Literal

from discord.ext import commands
from discord import app_commands, Interaction

from pipes.core.events import Event, events
from pipes.core.context import Context, ItemScope
from pipes.core.processor import PipelineProcessor
from mycommands import MyCommands
from utils.util import normalize_name

from pipes.views import EventView
from .slash_commands_util import event_type_map, autocomplete_event, choice_to_scriptoid, autocomplete_send_tone

class EventSlashCommands(MyCommands):

    # ================================================= Event Listing =================================================

    @app_commands.command()
    @app_commands.describe(enabled='If given, only list Events enabled (disabled) in this channel')
    async def events(self, interaction: Interaction, enabled: bool=None):
        ''' Display a list of Events. '''
        def reply(*a, **kw):
            if not interaction.response.is_done():
                return interaction.response.send_message(*a, **kw)
            return interaction.channel.send(*a, **kw)

        if not events:
            await reply('No events registered.')
            return

        enabled_events, disabled_events = [], []
        for event in events.values():
            if interaction.channel.id in event.channels: enabled_events.append(event)
            else: disabled_events.append(event)

        if enabled_events and enabled is not False:
            infos = ['**__Enabled:__**'] + ['• ' + str(e) for e in enabled_events]
            await reply('\n'.join(infos))

        if disabled_events and enabled is not True:
            infos = ['**__Disabled:__**'] + [', '.join(e.name for e in disabled_events)]
            await reply('\n'.join(infos))


    # ================================================ Event Management ===============================================

    event_group = app_commands.Group(name='event', description='Define, redefine, describe or delete Events')
    ''' The `/event <action>` command group'''

    @event_group.command(name='define')
    @app_commands.describe(
        name='The name of the new Event',
        event_type='The type of Event',
        trigger='The type-dependent trigger',
        code='The code which is triggered'
    )
    @app_commands.rename(event_type='type')
    async def event_define(self, interaction: Interaction,
        name: str,
        event_type: Literal['OnMessage', 'OnReaction', 'OnYell'],
        trigger: str,
        code: str,
    ):
        ''' Define a new Event and enable it in this channel. '''
        reply = interaction.response.send_message
        EventType = event_type_map[event_type]

        name = normalize_name(name)
        if name in events:
            return await reply(f'An Event called `{name}` already exists, try the `/event edit` command.')
            
        # TODO: Check event script code before saving
        event = EventType.from_trigger_str(name=name, author_id=interaction.user.id, channels=[interaction.channel.id], script=code, trigger=trigger)
        events[name] = event
        view = EventView(self.bot, event, events, interaction.channel)
        view.set_message(await reply(f'Successfully defined a new Event.', embed=event.embed(bot=self.bot, channel=interaction.channel), view=view))

    @event_group.command(name='edit')
    @app_commands.describe(
        event_choice='The Event to edit',
        event_type='If given, the Event\'s new type',
        trigger='If given, the Event\'s new type-dependent trigger',
        code='If given, the Event\'s new code',
    )
    @app_commands.rename(event_choice='event')
    @app_commands.autocomplete(event_choice=autocomplete_event())
    async def event_edit(self, interaction: Interaction,
        event_choice: str,
        event_type: Literal['OnMessage', 'OnReaction', 'OnYell']=None,
        trigger: str=None,
        code: str=None,
    ):
        ''' Redefine one or more fields on an existing Event. '''
        reply = interaction.response.send_message

        try:
            event, _ = choice_to_scriptoid(event_choice, Event)
        except:
            return await reply(f'Command failed, likely due to nonexistent Event.', ephemeral=True)

        # TODO: Check event code for errors

        if event_type is not None:
            EventType = event_type_map[event_type]
            if trigger is None:
                return await reply(f'When changing Event Type, the trigger must be given as well.')
            event = EventType.from_trigger_str(name=event.name, desc=event.desc, author_id=event.author_id, channels=event.channels, script=event.script, trigger=trigger)
            events[event.name] = event
        elif trigger is not None:
            event.set_trigger(trigger)
        if code is not None:
            event.script = code

        events.write()
        view = EventView(self.bot, event, events, interaction.channel)
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

        del events[event.name]
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
                events.write()
                await reply(f'Event {event.name} has been enabled in {interaction.channel.mention}.')
        else:
            if interaction.channel.id not in event.channels:
                await reply(f'Event {event.name} is already disabled in {interaction.channel.mention}.')
            else:                
                event.channels.remove(interaction.channel.id)
                events.write()
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
        tone='Determines which Event(s) will receive your message.',
        message='The "message" argument received by the Event script.',
    )
    @app_commands.autocomplete(tone=autocomplete_send_tone)
    async def yell(self, interaction: Interaction, tone: str, message: str=''):
        ''' Yell a message in a tone that an Event may react to. '''
        if not self.bot.should_listen_to_user(interaction.user):
            return

        for event in events.on_yell_events:
            if not event.test(interaction.channel, tone):
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
            processor: PipelineProcessor = self.bot.pipeline_processor
            scope = ItemScope(items=[message])
            await processor.execute_script(event.script, context, scope)

            # In case the script does not resolve the interaction. There is no way to resolve a slash command without a reply, so reply.
            if not interaction.response.is_done():
                await interaction.response.send_message("Done.", ephemeral=True)


# Load the bot cog
async def setup(bot: commands.Bot):
    await bot.add_cog(EventSlashCommands(bot))