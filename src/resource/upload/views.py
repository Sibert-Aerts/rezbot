from discord import Client, TextChannel, ui, ButtonStyle, TextStyle, Interaction
from discord.components import SelectOption

from generic_views import ConfirmView, RezbotView
from . import FileInfo, File, Files


class EditFileModal(ui.Modal):
    '''Modal for editing a File's metadata.'''

    def __init__(self, bot: Client=None, file: File=None, **kwargs):
        super().__init__(title=f'Edit {file.info.name}.txt metadata'[:52], **kwargs)
        self.bot = bot
        self.file = file

        # Construct modal input fields
        self.title_input = ui.TextInput(label='Title', style=TextStyle.short, default=file.info.title, required=False)
        self.add_item(self.title_input)
        self.desc_input = ui.TextInput(label='Description', style=TextStyle.long, default=file.info.description, required=False)
        self.add_item(self.desc_input)

        self.order_input = ui.Label(
            text='Order',
            component=ui.Select(
                options=[
                    SelectOption(label='Sequential', value='sequential', default=file.info.sequential),
                    SelectOption(label='Random', value='random', default=not file.info.sequential),
                ],
                required=True,
            ),
        )
        self.add_item(self.order_input)

        self.categories_input = ui.TextInput(label='Categories', style=TextStyle.short, default=', '.join(file.info.categories), required=False)
        self.add_item(self.categories_input)

        self.confirmed = False

    async def on_submit(self, interaction: Interaction):
        # Update file info
        self.file.info.title = self.title_input.value
        self.file.info.description = self.desc_input.value
        self.file.info.sequential = (self.order_input.component.values[0] == 'sequential')
        self.file.info.categories = FileInfo.normalize_categories(self.categories_input.value)

        # Write file info
        self.file.info.write()

        self.confirmed = True
        await interaction.response.edit_message(embed=self.file.embed(bot=self.bot, channel=interaction.channel))


class FileView(RezbotView):
    '''View which is to be added to a message containing the File's embed.'''

    def __init__(self, bot: Client, file: File, files: Files, channel: TextChannel, timeout=86400):
        super().__init__(remove_on_timeout=True, timeout=timeout)
        self.bot = bot
        self.channel = channel
        self.file: File = file
        self.files: Files = files

    # ========================================== Handlers ==========================================

    # TODO: Interaction check?

    # =========================================== Buttons ==========================================

    @ui.button(label='Edit', row=0, style=ButtonStyle.primary, emoji='✏')
    async def button_edit(self, interaction: Interaction, button: ui.Button):
        '''Opens Modal to edit the File.'''
        edit_file_modal = EditFileModal(self.bot, self.file)
        await interaction.response.send_modal(edit_file_modal)

    @ui.button(row=0, style=ButtonStyle.danger, emoji='✖')
    async def button_delete(self, interaction: Interaction, button: ui.Button):
        '''Delete the File, asks for confirmation first.'''

        if not self.file.may_delete(interaction.user):
            await interaction.response.send_message('Files can only be deleted by bot owners or the owner of the file.', ephemeral=True)

        confirm_msg = f'Are you sure you want to delete File `{self.file.info.name}.txt`?'
        confirm_view = ConfirmView()
        await interaction.response.send_message(confirm_msg, view=confirm_view, ephemeral=True)
        await confirm_view.wait()

        if confirm_view.value:
            self.files.delete_file(self.file.info.name)
            delete_msg = f'File `{self.file.info.name}` has been deleted by {interaction.user.name}.'
            await self.remove_from_message()
            await interaction.channel.send(delete_msg)
