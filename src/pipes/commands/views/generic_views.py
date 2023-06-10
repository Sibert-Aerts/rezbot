from discord import ui, ButtonStyle, Interaction
from discord.interactions import Interaction

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
