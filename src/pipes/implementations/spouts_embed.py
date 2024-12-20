from datetime import datetime, timezone
from discord import Embed, Message

from .spouts import spout_from_class, spout_from_func, set_category, Par, with_signature, Context
from pipes.core.signature import url, Hex, ListOf


#####################################################
#                  Spouts : EMBEDS                  #
#####################################################
set_category('EMBED')

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
        image       = Par(ListOf(url), None, 'Up to four links to images to display in big, separated by commas.', required=False),
        footer      = Par(str, None, 'The footer text.', required=False),
        footer_icon = Par(url, None, 'Link to the footer icon.', required=False),
        timestamp   = Par(int, None, 'A timestamp representing the date that shows up in the footer.', required=False),
    )
    @staticmethod
    async def spout_function(ctx: Context, values, *, color, title, author, author_icon, link, thumb, image: list[str], footer, footer_icon, timestamp):
        ''' Outputs text as the body of a Discord embed box.'''
        embed = Embed(title=title, description='\n'.join(values), color=color, url=link)
        embeds = [embed]

        if timestamp is not None:
            embed.timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if image:
            embed.set_image(url=image[0])
            # Multiple images in one embed is achieved by having additional embeds each linking to the same URL
            if len(image) > 1 and not link:
                link = embed.url = 'http://0.0.0.0/'
            for img in image[1:4]:
                embeds.append(Embed(url=link).set_image(url=img))
        if thumb is not None:
            embed.set_thumbnail(url=thumb)
        if author or author_icon:
            # This is not the empty string (↓↓), it's a soft hyphen to force icon to show up even when the name is empty.
            embed.set_author(name=author or '­', icon_url=author_icon)
        if footer or footer_icon:
            # It's a soft hyphen here also
            embed.set_footer(text=footer or '­', icon_url=footer_icon)

        await ctx.channel.send(embeds=embeds)


@spout_from_func({
    'name':     Par(str, 'Twitter User', 'The account\'s display name.'),
    'handle':   Par(str, 'twitter_user', 'The account\'s handle, (without the @).'),
    'icon':     Par(url, 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png', 'URL linking to their profile picture.'),
    'retweets': Par(str, '', 'The number of retweets, hidden if empty.'),
    'likes':    Par(str, '', 'The number of likes, hidden if empty.'),
    'timestamp':Par(int, None, 'Time the tweet was sent, "now" if empty.', required=False),
}, command=True)
async def tweet_spout(ctx: Context, values, *, name, handle, icon, retweets, likes, timestamp):
    ''' Outputs text as a fake tweet embed. '''
    embed = Embed(description='\n'.join(values), color=0x1da1f2)
    embed.set_author(name=f'{name} (@{handle})', url='https://twitter.com/'+handle, icon_url=icon)
    embed.set_footer(text='Twitter', icon_url='https://abs.twimg.com/icons/apple-touch-icon-192x192.png')
    embed.timestamp = datetime.now(tz=timezone.utc) if timestamp is None else datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if retweets:
        embed.add_field(name='Retweets', value=retweets)
    if likes:
        embed.add_field(name='Likes', value=likes)
    await ctx.channel.send(embed=embed)


@spout_from_func(aliases=['remove_embed'])
@with_signature(
    message = Par(str, 'this', 'The message to react to: this/that or a message ID.'),
)
async def remove_embeds_spout(ctx: Context, values, *, message: str):
    ''' Removes all embeds from the specified message. '''
    message: Message = await ctx.get_message(message)
    await message.edit(suppress=True)
