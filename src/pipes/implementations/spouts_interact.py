from operator import itemgetter
from discord import Client, Interaction, ui, ButtonStyle, TextStyle

from .spouts import spout_from_class, spout_from_func, set_category, with_signature, Par, Context, Spout
from pipes.signature import Option, parse_bool
from pipes.pipeline_with_origin import PipelineWithOrigin
from pipes.context import ItemScope

################################################################################
#                               Spouts : INTERACT                              #
################################################################################
set_category('INTERACT')


@spout_from_class
class ButtonSpout:
    '''
    Creates a Discord UI Button which may execute a callback script.
    Callback script will have an Interaction in its Context (if not deferred).
    '''
    name = 'button'
    command = True
    mode = Spout.Mode.aggregated

    ButtonStyleOption = Option('primary', 'secondary', 'success', 'danger', name='ButtonStyle', stringy=True)

    class Button(ui.Button):
        '''Button which executes a given script on click.'''
        def set_spout_args(self, ctx: Context, script: PipelineWithOrigin, lockout: bool, defer: bool):
            # NOTE: These values may hang around for a while, be wary of memory leaks
            self.original_context = ctx
            self.script = script
            self.lockout = lockout
            self.locked = False
            self.defer = defer

        async def callback(self, interaction: Interaction):
            if not self.original_context.bot.should_listen_to_user(interaction.user):
                return
            if self.locked:
                await interaction.response.send_message('Someone else already clicked this button.', ephemeral=True)
                return
            if self.defer:
                await interaction.response.defer()
            if not self.script:
                return
            if self.lockout:
                self.locked = True
            context = Context(
                origin=Context.Origin(
                    name='button script',
                    type=Context.Origin.Type.INTERACTION_CALLBACK,
                    activator=interaction.user,
                ),
                author=self.original_context.author,
                message=interaction.message,
                interaction=interaction,
            )
            await self.script.execute(context)
            self.locked = False

    class View(ui.View):
        '''Simple view which shows several buttons and disables them on timeout.'''
        def __init__(self, buttons: ui.Button, **kwargs):
            super().__init__(**kwargs)
            self.buttons = buttons
            for button in buttons:
                self.add_item(button)

        def set_message(self, message):
            self.message = message

        async def on_timeout(self):
            for button in self.buttons:
                button.disabled = True
            await self.message.edit(view=self)

    @with_signature(
        script  = Par(PipelineWithOrigin.from_string, required=False, desc='Script to execute when the button is pressed.'),
        label   = Par(str, required=False, desc='The label'),
        emoji   = Par(str, required=False, desc='The button\'s emoji'),
        style   = Par(ButtonStyleOption, default='primary', desc='The button\'s style: primary/secondary/success/danger.'),
        timeout = Par(int, default=86400, desc='Amount of seconds the button stays alive without being clicked.'),
        lockout = Par(parse_bool, default=False, desc='Whether this button should wait for each click\'s script to complete before allowing another.'),
        defer   = Par(parse_bool, default=True, desc='Whether to instantly defer (=close) the Interaction generated, set to False if you want to respond yourself.'),
    )
    @staticmethod
    async def spout_function(ctx: Context, values_and_args_list: list[tuple[list[str], dict[str]]]):
        timeouts = [a['timeout'] for _, a in values_and_args_list]
        max_timeout = 0 if any(t==0 for t in timeouts) else max(timeouts)

        buttons = []
        for _, args in values_and_args_list:
            script, label, emoji, style, lockout, defer = itemgetter('script', 'label', 'emoji', 'style', 'lockout', 'defer')(args)
            # TODO: This error should be emitted at hook time, not right now
            if not label and not emoji:
                raise ValueError('A button should have at least a `label` or `emoji`.')
            button = ButtonSpout.Button(label=label, emoji=emoji, style=getattr(ButtonStyle, style))
            button.set_spout_args(ctx, script, lockout, defer)
            buttons.append(button)

        # Max. 25 buttons fit on one message
        for i in range(0, len(buttons), 25):
            view = ButtonSpout.View(buttons[i:i+25], timeout=max_timeout)
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
        def set_spout_args(self, ctx: Context, script: PipelineWithOrigin, defer: bool):
            # NOTE: These values may hang around for a while, be wary of memory leaks
            self.original_context = ctx
            self.script = script
            self.defer = defer

        def set_text_input(self, text_input):
            self.text_input = text_input
            self.add_item(text_input)

        async def on_submit(self, interaction: Interaction):
            if not self.original_context.bot.should_listen_to_user(interaction.user):
                return
            if self.defer:
                await interaction.response.defer()
            if not self.script:
                return
            context = Context(
                origin=Context.Origin(
                    name='modal script',
                    type=Context.Origin.Type.INTERACTION_CALLBACK,
                    activator=interaction.user,
                ),
                author=self.original_context.author,
                message=interaction.message,
                interaction=interaction,
            )
            scope = ItemScope([self.text_input.value])
            await self.script.execute(context, scope)

    @with_signature(
        script   = Par(PipelineWithOrigin.from_string, required=False, desc='Script to execute when the button is pressed.'),
        title    = Par(str, default='Modal', desc='The modal\'s title'),
        label    = Par(str, default='Text', desc='The text field\'s label'),
        default  = Par(str, required=False, desc='The text field\'s default content'),
        required = Par(parse_bool, default=False, desc='If the text field is required'),
        defer   = Par(parse_bool, default=True, desc='Whether to instantly defer (=close) the Interaction generated, set to False if you want to respond yourself.'),
    )
    @staticmethod
    async def spout_function(ctx: Context, values, *, script, title, label, default, required, defer):
        if not ctx.interaction:
            raise ValueError('This spout can only be used when an Interaction is present, e.g. from pressing a button.')
        if ctx.interaction.response.is_done():
            raise ValueError('This Interaction has already been responded to.')

        # Create our Modal and give it a single text input
        modal = ModalSpout.Modal(title=title)
        modal.set_spout_args(ctx, script, defer)
        modal.set_text_input(ui.TextInput(
            label=label,
            style=TextStyle.paragraph,
            default=default,
            required=required
        ))

        await ctx.interaction.response.send_modal(modal)

# TODO: Make this one work aggregated too
@spout_from_class
class ModalButtonSpout:
    '''
    Combines 'button' and 'modal' spouts for easier use.
    Posts a message with a Discord button, which opens a Discord modal, which then executes a callback script.
    Callback script will have an Interaction in its Context (if defer=False).
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
        timeout = Par(int, default=86400, desc='Amount of seconds the button stays alive without being clicked.'),
        input_label = Par(str, default='Text', desc='The text field\'s label'),
        default  = Par(str, required=False, desc='The text field\'s default content'),
        required = Par(parse_bool, default=False, desc='If the text field is required'),
        defer = Par(parse_bool, default=True, desc='Whether to instantly defer (=close) the Interaction generated, set to False if you want to respond yourself.'),
    )
    @staticmethod
    async def spout_function(ctx: Context, values, *, script, title, button_label, button_style, emoji, timeout, input_label, default, required, defer):
        # Modal that will (repeatedly) be served by the button
        def make_modal():
            modal = ModalSpout.Modal(title=title)
            modal.set_spout_args(ctx, script, defer)
            modal.set_text_input(ui.TextInput(
                label=input_label,
                default=default,
                required=required,
                style=TextStyle.paragraph,
            ))
            return modal

        # Button that will serve the modal
        button = ModalButtonSpout.Button(label=button_label, emoji=emoji, style=getattr(ButtonStyle, button_style))
        button.set_config(ctx.bot, make_modal)

        # Use the generic ButtonSpout View
        view = ButtonSpout.View([button], timeout=timeout)
        view.set_message(await ctx.channel.send(view=view))


@spout_from_func
async def whisper_spout(ctx: Context, values: list[str]):
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
async def defer_spout(ctx: Context, values: list[str], *, thinking, whisper):
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
async def edit_original_response_spout(ctx: Context, values: list[str], *, remove_view):
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