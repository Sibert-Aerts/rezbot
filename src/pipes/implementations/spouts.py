from datetime import datetime, timezone
from typing import TypeVar

import discord
from discord import Embed, Message, Client, Interaction, ButtonStyle
import discord.ui
from discord.errors import HTTPException
from discord.ext.commands import Bot

from pipes.signature import Par, Signature, get_signature, Hex, url, with_signature, parse_bool, Option
from pipes.pipe import Spout, Spouts
from pipes.processor import PipelineWithOrigin
from pipes.events import events
from resource.upload import uploads
from pipes.context import Context
import utils.rand as rand

from .sources import SourceResources

#######################################################
#                     Decorations                     #
#######################################################

spouts = Spouts()
'The canonical object storing/indexing all `Spout` instances.'

_CATEGORY = None

def spout_from_func(signature: dict[str, Par]=None, /, *, command=False, **kwargs):
    '''Makes a Spout out of a function.'''
    func = None
    if callable(signature):
        (func, signature) = (signature, None)

    def _spout_from_func(func):
        global spouts, _CATEGORY
        # Name is the function name with the _spout bit cropped off
        name = func.__name__.rsplit('_', 1)[0].lower()
        doc = func.__doc__
        # Signature may be set using @with_signature, given directly, or not given at all
        sig = get_signature(func, Signature(signature or {}))    
        spout = Spout(sig, func, name=name, doc=doc, category=_CATEGORY, **kwargs)
        spouts.add(spout, command)
        return func

    if func: return _spout_from_func(func)
    return _spout_from_func

T = TypeVar('T')

def spout_from_class(cls: type[T]) -> type[T]:
    '''
    Makes a Spout out of a class by reading its definition, and either the class' or the method's docstring.
    ```py
    # Fields:
    name: str
    aliases: list[str]=None
    command: bool=False

    # Methods:
    @with_signature(...)
    @staticmethod
    def spout_function(bot, ctx: Context, items: list[str], **kwargs) -> list[str]: ...

    @staticmethod
    def may_use(user: discord.User) -> bool: ...
    ```
    '''
    def get(key, default=None):
        return getattr(cls, key, default)
    
    spout = Spout(
        get_signature(cls.spout_function),
        cls.spout_function,
        name=cls.name,
        doc=cls.__doc__ or cls.spout_function.__doc__,
        category=_CATEGORY,
        aliases=get('aliases'),
        may_use=get('may_use'),
    )
    spouts.add(spout, get('command', False))
    return cls

#####################################################
#                  Spouts : EMBEDS                  #
#####################################################

@spout_from_class
class SpoutEmbed:
    name = 'embed'
    command = True

    @with_signature(
        color       = Par(Hex, Hex(0x222222), 'The left-side border color as a hexadecimal value.'),
        title       = Par(str, None, 'The title.', required=False),
        link        = Par(url, None, 'A link opened by clicking the title.', required=False),
        author      = Par(str, None, 'A name presented as the author\'s.', required=False),
        author_icon = Par(url, None, 'Link to the author\'s portrait.', required=False),
        thumb       = Par(url, None, 'Link to an image shown as a thumbnail.', required=False),
        image       = Par(url, None, 'Link to an image shown in big.', required=False),
        footer      = Par(str, None, 'The footer text.', required=False),
        footer_icon = Par(url, None, 'Link to the footer icon.', required=False),
        timestamp   = Par(int, None, 'A timestamp representing the date that shows up in the footer.', required=False),
    )
    @staticmethod
    async def spout_function(bot, ctx, values, color, title, author, author_icon, link, thumb, image, footer, footer_icon, timestamp):
        ''' Outputs text as the body of a Discord embed box.'''
        embed = Embed(title=title, description='\n'.join(values), color=color, url=link)

        if timestamp is not None:
            embed.timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if image is not None:
            embed.set_image(url=image)
        if thumb is not None:
            embed.set_thumbnail(url=thumb)
        if author or author_icon:
            # This is not the empty string (↓↓), it's a soft hyphen to force icon to show up even when the name is empty.
            embed.set_author(name=author or '­', icon_url=author_icon)
        if footer or footer_icon:
            # It's a soft hyphen here also
            embed.set_footer(text=footer or '­', icon_url=footer_icon)

        await ctx.message.channel.send(embed=embed)


@spout_from_func({
    'name':     Par(str, 'test_user', 'The account\'s display name.'),
    'handle':   Par(str, 'test_user', 'The account\'s handle, (without the @).'),
    'icon':     Par(url, 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png', 'URL linking to their profile picture.'),
    'retweets': Par(str, '', 'The number of retweets, hidden if empty.'),
    'likes':    Par(str, '', 'The number of likes, hidden if empty.'),
    'timestamp':Par(int, None, 'Time the tweet was sent, "now" if empty.', required=False),
}, command=True)
async def tweet_spout(bot, ctx, values, name, handle, icon, retweets, likes, timestamp):
    ''' Outputs text as a fake tweet embed. '''
    embed = Embed(description='\n'.join(values), color=0x1da1f2)
    embed.set_author(name=f'{name} (@{handle})', url='https://twitter.com/'+handle, icon_url=icon)
    embed.set_footer(text='Twitter', icon_url='https://abs.twimg.com/icons/apple-touch-icon-192x192.png')
    embed.timestamp = datetime.now(tz=timezone.utc) if timestamp is None else datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if retweets:
        embed.add_field(name='Retweets', value=retweets)
    if likes:
        embed.add_field(name='Likes', value=likes)
    await ctx.message.channel.send(embed=embed)


#####################################################
#                 Spouts : MESSAGES                 #
#####################################################

@spout_from_func
async def delete_message_spout(bot, ctx, values):
    ''' Deletes the message which is the subject of the script's execution. '''
    await ctx.message.delete()


@spout_from_func
async def send_message_spout(bot, ctx: Context, values):
    '''
    Sends input as a Discord message.
    If multiple lines of input are given, they're joined with line breaks.
    '''
    await ctx.message.channel.send('\n'.join(values))


@spout_from_func({
    'id':      Par(int, -1, 'The message ID to reply to, -1 for the script\'s subject message.'),
    'mention': Par(parse_bool, False, 'Whether the reply should mention the person being replied to.'),
})
async def reply_spout(bot, ctx: Context, values, *, id, mention):
    '''
    Sends input as a Discord message replying to another message.
    If multiple lines of input are given, they're joined with line breaks.
    '''
    if id > 0:
        message = await ctx.message.channel.fetch_message(id)
    else:
        message = ctx.message
    await message.reply('\n'.join(values), mention_author=mention)


@spout_from_func({
    'emote': Par(str, None, 'The emote that you\'d like to use to react. (Emoji or custom emote)'),
})
async def react_spout(bot, ctx, values, emote):
    ''' Reacts to the message using the specified emote. '''
    try:
        await ctx.message.add_reaction(emote)
    except HTTPException as e:
        if e.text == 'Unknown Emoji':
            raise ValueError('Unknown Emote: `{}`'.format(emote))
        else:
            raise e


@spout_from_func
@with_signature(
    sticker = Par(str, None, 'Name or ID of the sticker.'),
    here    = Par(parse_bool, True, 'Whether to restrict to this server\'s stickers.'),
)
async def sticker_spout(bot: Bot, ctx: Context, values: list[str], sticker: str, here :bool):
    ''' Sends a message with a sticker attached. '''    
    if here:
        stickers = list(ctx.message.guild.stickers)
    else:
        stickers = [s for guild in SourceResources.bot.guilds for s in guild.stickers]

    name_or_id = sticker
    sticker = None

    # Try ID match
    try: sticker = bot.get_sticker(int(name_or_id))
    except: pass
    # Try exact name match
    if sticker is None:
        sticker = next((s for s in stickers if s.name == name_or_id), None)
    # Try name search match
    if sticker is None:
        search = name_or_id.lower()
        stickers = [s for s in stickers if search in s.name.lower()]
        if stickers: sticker = rand.choose(stickers)

    if sticker is None:
        raise ValueError(f'Unknown sticker "{name_or_id}".')
    await ctx.message.channel.send(stickers=[sticker])


#####################################################
#                   Spouts : STATE                  #
#####################################################

@spout_from_func({
    'name' :   Par(str, None, 'The variable name'),
    'persist': Par(parse_bool, False, 'Whether the variable should persist indefinitely.')
}, command=True)
async def set_spout(bot, ctx, values, name, persist):
    '''
    Stores the input as a variable with the given name.
    Variables can be retrieved via the `get` Source.
    If `persist`=True, variables will never disappear until manually deleted by the `delete_var` Spout.
    '''
    SourceResources.variables.set(name, values, persistent=persist)


@spout_from_func({
    'name' :  Par(str, None, 'The variable name'),
    'strict': Par(parse_bool, False, 'Whether an error should be raised if the variable does not exist.')
}, command=True)
async def delete_var_spout(bot, ctx, values, name, strict):
    ''' Deletes the variable with the given name. '''
    try:
        SourceResources.variables.delete(name)
    except:
        if strict:
            raise KeyError(f'No variable "{name}" found.')


@spout_from_func({
    'name' : Par(str, None, 'The new file\'s name'),
    'sequential': Par(parse_bool, True, 'Whether the order of entries matters when retrieving them from the file later.'),
    'sentences': Par(parse_bool, False, 'Whether the entries should be split based on sentence recognition instead of a splitter regex.'),
    'editable': Par(parse_bool, False, 'Whether the file should be able to be modified at a later time.'),
    'categories': Par(str, '', 'Comma-separated, case insensitive list of categories the file should be filed under.')
})
async def new_file_spout(bot, ctx: Context, values, name, sequential, sentences, editable, categories):
    '''Writes the input to a new txt file.'''
    # Files are stored as raw txt's, but we want to make sure our list of strings remain distinguishable.
    # So we join the list of strings by a joiner that we determine for sure is NOT a substring of any of the strings,
    # so that if we split on the joiner later we get the original list of strings.
    if not sentences:
        joiner = '\n'
        while any(joiner in value for value in values):
            joiner += '&'
        if len(joiner) > 1: joiner += '\n'
    else:
        joiner = '\n'

    uploads.add_file(name, joiner.join(values), ctx.activator.display_name, ctx.activator.id,
        editable=editable, splitter=joiner, sequential=sequential, sentences=sentences, categories=categories)


#####################################################
#                  Spouts : SPECIAL                 #
#####################################################

@spout_from_func
async def suppress_print_spout(bot, ctx, values):
    '''
    (WIP) Prevents the default behaviour of printing output to a Discord message.
    Useful for Event scripts that silently modify variables, or that don't do anything in certain circumstances.
    '''
    # NOP, just having *any* spout is enough to prevent the default "print" behaviour
    pass


@spout_from_func
async def print_spout(bot, ctx, values):
    ''' Appends the values to the output message. (WIP: /any/ other spout suppresses print output right now!) '''
    # The actual implementation of "print" is hardcoded into the pipeline processor code
    # This definition is just here so it shows up in the list of spouts
    pass


@spout_from_func({
    'name': Par(str, None, 'The name of the event to be disabled.')
})
async def disable_event_spout(bot, ctx: Context, values, name):
    ''' Disables the specified event. '''
    if name not in events:
        raise ValueError('Event %s does not exist!' % name)
    event = events[name]
    if ctx.message.channel.id in event.channels:
        event.channels.remove(ctx.message.channel.id)


@spout_from_class
class ButtonSpout:
    name = 'button'
    command = True
    
    ButtonStyleOption = Option('primary', 'secondary', 'success', 'danger', name='ButtonStyle', stringy=True)
    
    class Button(discord.ui.Button):
        def set_spout_args(self, bot: Client, ctx: Context, values: list[str], script: PipelineWithOrigin):
            self.bot = bot
            self.original_context = ctx
            self.values = values
            self.script = script

        async def callback(self, interaction: Interaction):
            await interaction.response.defer()
            if not self.script:
                return
            context = Context(
                author=self.original_context.author,
                activator=interaction.user,
                message=interaction.message,
                interaction=interaction,
                items=self.values
            )
            await self.script.execute(self.bot, interaction.message, context=context, name='button script')

    class View(discord.ui.View):
        def __init__(self, button: discord.ui.Button, **kwargs):
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
    )
    @staticmethod
    async def spout_function(bot: Client, ctx: Context, values: list[str], *, script, label, style, emoji, timeout):
        if not label and not emoji:
            raise ValueError('A button should have at least a `label` or `emoji`.')
        button = ButtonSpout.Button(label=label, emoji=emoji, style=getattr(ButtonStyle, style))
        button.set_spout_args(bot, ctx, values, script)
        view = ButtonSpout.View(button, timeout=timeout)
        view.set_message(await ctx.message.channel.send(view=view))
