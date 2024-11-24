from discord import Message, Client, ui, TextStyle, Interaction

from pipes.core.state.context import Context
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pipes.core.processor import PipelineProcessor


class ExecuteScriptModal(ui.Modal):
    '''Modal allowing a user to write and execute a script.'''

    script_input = ui.TextInput(label='Script', row=2, style=TextStyle.long)

    def __init__(self, bot: Client, interaction: Interaction, message: Message=None, **kwargs):
        super().__init__(title='Execute Script', **kwargs)
        self.bot = bot
        self.original_interaction = interaction
        self.target_message = message

    async def on_submit(self, interaction: Interaction):
        script = self.script_input.value

        context = Context(
            origin=Context.Origin(
                type=Context.Origin.Type.DIRECT_TARGETING_MESSAGE,
                activator=interaction.user,
            ),
            author=interaction.user,
            interaction=interaction,
            message=self.target_message,
        )

        processor: PipelineProcessor = self.bot.pipeline_processor
        await processor.execute_script(script, context)

        # In case the script does not resolve the interaction. There is no way to resolve a slash command without a reply, so reply.
        if not interaction.response.is_done():
            await interaction.response.send_message("Done.", ephemeral=True)
