from discord import Message, ui, ButtonStyle, TextStyle, Interaction
from discord.interactions import Interaction

from .generic_views import ConfirmView, RezbotView
from pipes.core.macros import Macro, Macros


class EditMacroModal(ui.Modal):
    '''Modal for editing a macro's code and description fields.'''
    # If Discord ever adds checkboxes, dropdowns, etc. to modals, extend this to allow editing other fields
    desc_input = ui.TextInput(label='Description', style=TextStyle.long, required=False)
    code_input = ui.TextInput(label='Code', style=TextStyle.long)

    def __init__(self, macro: Macro=None, **kwargs):
        super().__init__(title=f'Edit {macro.kind} Macro {macro.name}'[:52], **kwargs)
        self.macro = macro
        self.desc_input.default = macro.desc
        self.code_input.default = macro.code
        self.confirmed = False

    async def on_submit(self, interaction: Interaction):
        self.macro.desc = self.desc_input.value
        self.macro.code = self.code_input.value
        # macros.write() is called by the View
        await interaction.response.edit_message(embed=self.macro.embed(channel=interaction.channel))
        self.confirmed = True


class MacroView(RezbotView):
    '''View which is to be added to a message containing the Macro's embed.'''
    def __init__(self, macro: Macro, macros: Macros, timeout=86400):
        super().__init__(remove_on_timeout=True, timeout=timeout)
        self.macro: Macro = macro
        self.macros: Macros = macros
        self._on_change_visible()

    # =========================================== Utility ==========================================

    def _on_change_visible(self):
        visible = self.macro.visible
        self.button_toggle_hide.label = 'Hide' if visible else 'Unhide'
        self.button_toggle_hide.style = ButtonStyle.gray if visible else ButtonStyle.primary

    # ========================================== Handlers ==========================================

    async def interaction_check(self, interaction: Interaction):
        if not self.macro.authorised(interaction.user):
            await interaction.response.send_message('You\'re not authorised to modify this macro.', ephemeral=True, delete_after=15)
            return False
        return await super().interaction_check(interaction)

    # =========================================== Buttons ==========================================

    @ui.button(label='Edit', row=0, style=ButtonStyle.primary, emoji='✏')
    async def button_edit(self, interaction: Interaction, button: ui.Button):
        '''Opens Modal to edit the Macro.'''
        edit_macro_modal = EditMacroModal(self.macro)
        await interaction.response.send_modal(edit_macro_modal)
        await edit_macro_modal.wait()
        if edit_macro_modal.confirmed:
            self.macros.write()

    @ui.button(row=0)
    async def button_toggle_hide(self, interaction: Interaction, button: ui.Button):
        '''Toggles whether the Macro is hidden, appearance is variable.'''
        self.macro.visible = not self.macro.visible
        self.macros.write()
        self._on_change_visible()
        await interaction.response.edit_message(embed=self.macro.embed(channel=interaction.channel), view=self)

    @ui.button(row=0, style=ButtonStyle.danger, emoji='✖')
    async def button_delete(self, interaction: Interaction, button: ui.Button):
        '''Delete the Macro, asks for confirmation first.'''
        confirm_msg = f'Are you sure you want to delete {self.macros.kind} Macro `{self.macro.name}`?'
        confirm_view = ConfirmView()
        await interaction.response.send_message(confirm_msg, view=confirm_view, ephemeral=True)
        await confirm_view.wait()

        if confirm_view.value:
            del self.macros[self.macro.name]
            delete_msg = f'{self.macros.kind} Macro `{self.macro.name}` has been deleted by {interaction.user.name}.'
            await interaction.channel.send(delete_msg)
            await self.remove_from_message()
