from discord import Client, Interaction, ui, ButtonStyle, TextStyle

from .spouts import spout_from_class, spout_from_func, set_category, with_signature, Par, Context
from pipes.signature import Option, parse_bool
from pipes.pipeline_with_origin import PipelineWithOrigin

################################################################################
#                               Spouts : INTERACT                              #
################################################################################
set_category('INTERACT')


@spout_from_class
class ButtonSpout:
    '''
    Creates a message with a Discord UI Button, which may execute a callback script.
    Callback script will have an Interaction in its Context (if not deferred).
    '''
    name = 'button'
    command = True
    
    ButtonStyleOption = Option('primary', 'secondary', 'success', 'danger', name='ButtonStyle', stringy=True)
    
    class Button(ui.Button):
        def set_spout_args(self, bot: Client, ctx: Context, script: PipelineWithOrigin, defer: bool):
            # NOTE: These values may hang around for a while, be wary of memory leaks
            self.bot = bot
            self.original_context = ctx
            self.script = script
            self.defer = defer

        async def callback(self, interaction: Interaction):
            if not self.bot.should_listen_to_user(interaction.user):
                return
            if self.defer:
                await interaction.response.defer()
            if not self.script:
                return
            context = Context(
                origin=Context.Origin(
                    name='button script',
                    type=Context.Origin.Type.INTERACTION_CALLBACK,
                ),
                author=self.original_context.author,
                activator=interaction.user,
                message=interaction.message,
                interaction=interaction,
            )
            await self.script.execute(self.bot, context)

    class View(ui.View):
        def __init__(self, button: ui.Button, **kwargs):
            super().__init__(**kwargs)
            self.button = button
            self.add_item(button)

        def set_message(self, message):
            self.message = message

        async def on_timeout(self):
            self.button.disabled = True
            await self.message.edit(view=self)

    @with_signature(
        script  = Par(PipelineWithOrigin.from_string, required=False, desc='Script to execute when the button is pressed.'),
        label   = Par(str, required=False, desc='The label'),
        emoji   = Par(str, required=False, desc='The button\'s emoji'),
        style   = Par(ButtonStyleOption, default='primary', desc='The button\'s style: primary/secondary/success/danger.'),
        timeout = Par(int, default=3600, desc='Amount of seconds the button stays alive without being clicked.'),
        defer   = Par(parse_bool, default=True, desc='Whether to instantly defer (=close) the Interaction generated, set to False if you want to respond yourself.'),
    )
    @staticmethod
    async def spout_function(bot: Client, ctx: Context, values, *, script, label, style, emoji, timeout, defer):
        if not label and not emoji:
            raise ValueError('A button should have at least a `label` or `emoji`.')
        button = ButtonSpout.Button(label=label, emoji=emoji, style=getattr(ButtonStyle, style))
        button.set_spout_args(bot, ctx, script, defer)
        view = ButtonSpout.View(button, timeout=timeout)
        view.set_message(await ctx.channel.send(view=view))


@spout_from_class
class ModalSpout:
    '''
    Opens a Discord UI Modal with a text prompt, and calls back with the value entered into the prompt.
    Can only be used when an active Discord Interaction is in Context (e.g. during a non-deferred `button` callback).
    Callback script will have an Interaction in its Context (if not deferred).
    '''
    name = 'modal'
        
    class Modal(ui.Modal):
        def set_spout_args(self, bot: Client, ctx: Context, script: PipelineWithOrigin, defer: bool):
            # NOTE: These values may hang around for a while, be wary of memory leaks
            self.bot = bot
            self.original_context = ctx
            self.script = script
            self.defer = defer

        def set_text_input(self, text_input):
            self.text_input = text_input
            self.add_item(text_input)

        async def on_submit(self, interaction: Interaction):
            if not self.bot.should_listen_to_user(interaction.user):
                return
            if self.defer:
                await interaction.response.defer()
            if not self.script:
                return
            context = Context(
                origin=Context.Origin(
                    name='modal script',
                    type=Context.Origin.Type.INTERACTION_CALLBACK,
                ),
                author=self.original_context.author,
                activator=interaction.user,
                message=interaction.message,
                interaction=interaction,
                items=[self.text_input.value]
            )
            await self.script.execute(self.bot, context)

    @with_signature(
        script   = Par(PipelineWithOrigin.from_string, required=False, desc='Script to execute when the button is pressed.'),
        title    = Par(str, default='Modal', desc='The modal\'s title'),
        label    = Par(str, default='Text', desc='The text field\'s label'),
        default  = Par(str, required=False, desc='The text field\'s default content'),
        required = Par(parse_bool, default=False, desc='If the text field is required'),
        defer   = Par(parse_bool, default=True, desc='Whether to instantly defer (=close) the Interaction generated, set to False if you want to respond yourself.'),
    )
    @staticmethod
    async def spout_function(bot: Client, ctx: Context, values, *, script, title, label, default, required, defer):
        if not ctx.interaction:
            raise ValueError('This spout can only be used when an Interaction is present, e.g. from pressing a button.')
        if ctx.interaction.response.is_done():
            raise ValueError('This Interaction has already been responded to.')

        # Create our Modal and give it a single text input
        modal = ModalSpout.Modal(title=title)
        modal.set_spout_args(bot, ctx, script, defer)
        modal.set_text_input(ui.TextInput(
            label=label,
            style=TextStyle.paragraph,
            default=default,
            required=required
        ))

        await ctx.interaction.response.send_modal(modal)


@spout_from_class
class ModalButtonSpout:
    '''
    Combines 'button' and 'modal' spouts.
    Posts a message with a Discord button, which just opens a Discord modal, which then executes a callback script.
    Callback script will have an Interaction in its Context (if not deferred).
    '''
    name = 'modal_button'
    command = True
    
    class Button(ui.Button):
        def set_config(self, bot, make_modal):
            self.bot = bot
            self.make_modal = make_modal

        async def callback(self, interaction: Interaction):
            if not self.bot.should_listen_to_user(interaction.user):
                return
            await interaction.response.send_modal(self.make_modal())

    @with_signature(
        script = Par(PipelineWithOrigin.from_string, required=False, desc='Script to execute when the button is pressed.'),
        title = Par(str, default='Modal', desc='The modal\'s title'),
        button_label = Par(str, default='Button', desc='The button\'s label'),
        button_style = Par(ButtonSpout.ButtonStyleOption, default='primary', desc='The button\'s style: primary/secondary/success/danger.'),
        emoji   = Par(str, required=False, desc='The button\'s emoji'),
        timeout = Par(int, default=3600, desc='Amount of seconds the button stays alive without being clicked.'),
        input_label = Par(str, default='Text', desc='The text field\'s label'),
        default  = Par(str, required=False, desc='The text field\'s default content'),
        required = Par(parse_bool, default=False, desc='If the text field is required'),
        defer = Par(parse_bool, default=True, desc='Whether to instantly defer (=close) the Interaction generated, set to False if you want to respond yourself.'),
    )
    @staticmethod
    async def spout_function(bot: Client, ctx: Context, values, *, script, title, button_label, button_style, emoji, timeout, input_label, default, required, defer):
        # Modal that will (repeatedly) be served by the button
        def make_modal():
            modal = ModalSpout.Modal(title=title)
            modal.set_spout_args(bot, ctx, script, defer)
            modal.set_text_input(ui.TextInput(
                label=input_label,
                default=default,
                required=required,
                style=TextStyle.paragraph,
            ))
            return modal

        # Button that will serve the modal
        button = ModalButtonSpout.Button(label=button_label, emoji=emoji, style=getattr(ButtonStyle, button_style))
        button.set_config(bot, make_modal)

        # Use the generic single-button View
        view = ButtonSpout.View(button, timeout=timeout)
        view.set_message(await ctx.channel.send(view=view))


@spout_from_func
async def whisper_spout(bot: Client, ctx: Context, values: list[str]):
    '''
    Sends input as an ephemeral (invisible) Discord message, requires an active Interaction.
    If multiple lines of input are given, they're joined with line breaks.
    '''
    if not ctx.interaction:
        raise ValueError('This spout can only be used when an Interaction is present, e.g. from pressing a button.')
    if ctx.interaction.response.is_done():
        raise ValueError('This Interaction has already been responded to.')
    
    content = '\n'.join(values)
    await ctx.interaction.response.send_message(content, ephemeral=True)


@spout_from_func
@with_signature(
    thinking = Par(parse_bool, default=False, desc='If true, shows a symbolic "thinking" message, is silent otherwise.'),
    whisper = Par(parse_bool, default=False, desc='If true, the thinking message shows as a whisper'),
)
async def defer_spout(bot: Client, ctx: Context, values: list[str], *, thinking, whisper):
    '''
    "Defers" the active Interaction, preventing Discord from showing an "Interaction failed!" message.
    '''
    if not ctx.interaction:
        raise ValueError('This spout can only be used when an Interaction is present, e.g. from pressing a button.')
    if ctx.interaction.response.is_done():
        raise ValueError('This Interaction has already been responded to.')

    await ctx.interaction.response.defer(ephemeral=whisper, thinking=thinking)


@spout_from_func
@with_signature(
    remove_view = Par(parse_bool, default=False, desc='If true, removes the View (i.e. buttons) from the message.'),
)
async def edit_original_response_spout(bot: Client, ctx: Context, values: list[str], *, remove_view):
    '''
    Edit a resolved Interaction's original response message.
    
    In case the current Interaction has been responded to with a message via `defer thinking=True` or `whisper`, it will edit that message.

    In case the current Interaction has been responded to without a message (e.g. `button`, `modal`, or `defer thinking=False`),
    it will edit the *most recent* bot message in the chain of Interactions (e.g. the message containing the button that opened the modal.)
    '''
    if not ctx.interaction:
        raise ValueError('This spout can only be used when an Interaction is present, e.g. from pressing a button.')
    if not ctx.interaction.response.is_done():
        raise ValueError('This Interaction has not yet been responded to.')
    
    content = '\n'.join(values)
    kwargs = {}
    if remove_view: kwargs['view'] = None
    await ctx.interaction.edit_original_response(content=content, **kwargs)