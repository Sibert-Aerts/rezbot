from discord import ui, ButtonStyle, Interaction, Message
from discord.interactions import Interaction

import permissions


class ConfirmView(ui.View):
    """Generic Confirm/Cancel functionality."""
    def __init__(self):
        super().__init__()
        self.value = None

    @ui.button(label='Confirm', style=ButtonStyle.green)
    async def confirm(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.value = True
        self.stop()

    @ui.button(label='Cancel', style=ButtonStyle.grey)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.value = False
        self.stop()


class RezbotButton(ui.Button):
    '''Bespoke-er Button class, maybe?'''
    pass


class RezbotView(ui.View):
    '''Bespoke-er View class for my purposes.'''
    message: Message = None
    buttons: list[RezbotButton]

    def __init__(self, remove_on_timeout=False, timeout=86400):
        super().__init__(timeout=timeout)
        self.remove_on_timeout = remove_on_timeout
        self.buttons = []

    def set_message(self, message: Message):
        self.message = message

    async def update_message(self):
        if self.message:
            await self.message.edit(view=self)

    async def remove_from_message(self):
        if self.message:
            await self.message.edit(view=None)

    # ======== Default Behaviour

    async def interaction_check(self, interaction: Interaction):
        # Ignore muted users
        if permissions.is_muted(interaction.user.id):
            return False
        return await super().interaction_check(interaction)

    async def on_timeout(self):
        if self.remove_on_timeout:
            await self.remove_from_message()
            return

        # Disable all Buttons
        for item in self._children:
            if isinstance(item, ui.Button):
                item.disabled = True

        # Update message to disable buttons
        await self.update_message()