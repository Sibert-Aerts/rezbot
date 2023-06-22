from discord import Message, Client, TextChannel, ui, ButtonStyle, TextStyle, Interaction
from discord.interactions import Interaction

from .generic_views import ConfirmView
from pipes.events import Event, Events, OnMessage, OnReaction


class EditEventModal(ui.Modal):
    '''Modal for editing an Event.'''
    # TODO: If discord ever adds checkboxes, dropdowns, etc. to modals, allow editing other fields
    desc_input = ui.TextInput(label='Description', row=1, style=TextStyle.long, required=False)
    script_input = ui.TextInput(label='Script', row=2, style=TextStyle.long)

    def __init__(self, bot: Client=None, event: Event=None, **kwargs):
        super().__init__(title=f'Edit {event.name}'[:52], **kwargs)
        self.bot = bot
        self.event = event
        self.desc_input.default = event.desc
        self.script_input.default = event.script

        if isinstance(event, (OnMessage, OnReaction)):
            trigger_label = f'Trigger ({type(event).__name__})'
            trigger_value = event.get_trigger_str()
            self.trigger_input = ui.TextInput(label=trigger_label, default=trigger_value, row=0, required=True)
            self.add_item(self.trigger_input)

        self.confirmed = False

    async def on_submit(self, interaction: Interaction):
        if isinstance(self.event, (OnMessage, OnReaction)):
            self.event.desc = self.desc_input.value
            self.event.update(self.script_input.value, self.trigger_input.value)
        # events.write() is called by the View
        await interaction.response.edit_message(embed=self.event.embed(bot=self.bot, channel=interaction.channel))
        self.confirmed = True


class EventView(ui.View):
    '''View which is to be added to a message containing the Event's embed.'''
    def __init__(self, bot: Client, event: Event, events: Events, channel: TextChannel, timeout=86400, **kwargs):
        super().__init__(timeout=timeout, **kwargs)
        self.bot = bot
        self.channel = channel
        self.message = None
        self.event: Event = event
        self.events: Events = events
        self._on_change_enable()

    def set_message(self, message: Message):
        self.message = message
        self.channel = message.channel

    # =========================================== Utility ==========================================

    async def _remove_self(self):
        if self.message:
            await self.message.edit(view=None)

    def _on_change_enable(self):
        enabled = self.channel.id in self.event.channels
        self.button_toggle_enable.label = 'Disable here' if enabled else 'Enable here'
        self.button_toggle_enable.style = ButtonStyle.gray if enabled else ButtonStyle.primary

    # ========================================== Handlers ==========================================

    # TODO: Interaction check?
    
    async def on_timeout(self):
        await self._remove_self()
        return await super().on_timeout()

    # =========================================== Buttons ==========================================

    @ui.button(label='Edit', row=0, style=ButtonStyle.primary, emoji='✏')
    async def button_edit(self, interaction: Interaction, button: ui.Button):
        '''Opens Modal to edit the Event.'''
        edit_event_modal = EditEventModal(self.bot, self.event)
        await interaction.response.send_modal(edit_event_modal)
        await edit_event_modal.wait()
        if edit_event_modal.confirmed:
            self.events.write()

    @ui.button(row=0)
    async def button_toggle_enable(self, interaction: Interaction, button: ui.Button):
        '''Toggles whether the Event is enabled, appearance is variable.'''
        enabled = self.channel.id in self.event.channels
        if enabled:
            self.event.channels.remove(self.channel.id)
        else:
            self.event.channels.append(self.channel.id)
        self.events.write()
        self._on_change_enable()
        await interaction.response.edit_message(embed=self.event.embed(bot=self.bot, channel=interaction.channel), view=self)

    @ui.button(row=0, label='Disable everywhere', style=ButtonStyle.gray)
    async def button_disable_everywhere(self, interaction: Interaction, button: ui.Button):
        '''Disables the Event in all of this server's channels.'''
        self.event.disable_in_guild(interaction.guild)
        self.events.write()
        self._on_change_enable()
        await interaction.response.edit_message(embed=self.event.embed(bot=self.bot, channel=interaction.channel), view=self)

    @ui.button(row=0, style=ButtonStyle.danger, emoji='✖')
    async def button_delete(self, interaction: Interaction, button: ui.Button):
        '''Delete the Event, asks for confirmation first.'''
        confirm_msg = f'Are you sure you want to delete Event `{self.event.name}`?'
        confirm_view = ConfirmView()
        await interaction.response.send_message(confirm_msg, view=confirm_view, ephemeral=True)
        await confirm_view.wait()

        if confirm_view.value:
            del self.events[self.event.name]
            delete_msg = f'Event `{self.event.name}` has been deleted by {interaction.user.name}.'
            await self._remove_self()
            await interaction.channel.send(delete_msg)
