from discord import ui, ButtonStyle, TextStyle, Interaction, SelectOption
from discord.interactions import Interaction

from .generic_views import ConfirmView
from pipes.macros import Macro, Macros


class EditMacroModal(ui.Modal):
    """Modal for editing a macro's code and description fields."""
    # TODO: If discord ever adds checkboxes, dropdowns, etc. to modals, allow editing other fields

    def __init__(self, macro: Macro=None, **kwargs):
        super().__init__(title=f'Edit code for {macro.name}', **kwargs)
        self.macro = macro
        self.desc_input = ui.TextInput(label='Description', default=macro.desc, style=TextStyle.long)
        self.add_item(self.desc_input)
        self.code_input = ui.TextInput(label='Code', default=macro.code, style=TextStyle.long)
        self.add_item(self.code_input)
        self.confirmed = False

    async def on_submit(self, interaction: Interaction):
        self.macro.desc = self.desc_input.value
        self.macro.code = self.code_input.value
        # macros.write() is called by the View
        await interaction.response.edit_message(embed=self.macro.embed(interaction))
        self.confirmed = True


class MacroView(ui.View):
    """View which is to be added to a message containing the Macro's embed."""
    def __init__(self, original_interaction: Interaction, macro: Macro, macros: Macros, timeout=600, **kwargs):
        super().__init__(timeout=timeout, **kwargs)
        self.original_interaction = original_interaction
        self.macro: Macro = macro
        self.macros: Macros = macros
        self._update_toggle_hide()

    # =========================================== Utility ==========================================

    async def _remove_self(self):
        await self.original_interaction.edit_original_response(view=None)

    def _update_toggle_hide(self):
        visible = self.macro.visible
        self.button_toggle_hide.label = 'Visible' if visible else 'Hidden'
        self.button_toggle_hide.style = ButtonStyle.secondary if visible else ButtonStyle.gray

    # ========================================== Handlers ==========================================

    async def interaction_check(self, interaction: Interaction):
        if not self.macro.authorised(interaction.user):
            await interaction.response.send_message('You\'re not authorised to modify this macro.', ephemeral=True, delete_after=15)
            return False
        return await super().interaction_check(interaction)
    
    async def on_timeout(self):
        await self._remove_self()
        return await super().on_timeout()

    # =========================================== Buttons ==========================================

    @ui.button(label='Edit', row=0, style=ButtonStyle.secondary, emoji='✏')
    async def button_edit(self, interaction: Interaction, button: ui.Button):
        """Opens Modal to edit the Macro."""
        edit_macro_modal = EditMacroModal(self.macro)
        await interaction.response.send_modal(edit_macro_modal)
        await edit_macro_modal.wait()
        if edit_macro_modal.confirmed:
            self.macros.write()

    @ui.button(row=0)
    async def button_toggle_hide(self, interaction: Interaction, button: ui.Button):
        """Toggles whether the Macro is hidden, appearance is variable."""
        macro = self.macro
        macro.visible = not macro.visible

        self.macros.write()
        await interaction.response.edit_message(embed=self.macro.embed(interaction), view=self)

    @ui.button(row=0, style=ButtonStyle.danger, emoji='✖')
    async def button_delete(self, interaction: Interaction, button: ui.Button):
        """Delete the Macro, asks for confirmation first."""
        confirm_msg = f'Are you sure you want to delete {self.macros.kind} Macro `{self.macro.name}`?'
        confirm_view = ConfirmView()
        await interaction.response.send_message(confirm_msg, view=confirm_view, ephemeral=True)
        await confirm_view.wait()

        if confirm_view.value:
            del self.macros[self.macro.name]
            delete_msg = f'{self.macros.kind} Macro `{self.macro.name}` has been deleted by {interaction.user.name}.'
            await self._remove_self()
            await interaction.channel.send(delete_msg)
