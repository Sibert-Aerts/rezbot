from discord import ui, components

from .spouts import spout_from_class, set_category, Par, with_signature, Context
from ..core.signature import url


#####################################################
#                 Spouts : COMPONENT                #
#####################################################
set_category('COMPONENT')


@spout_from_class
class SpoutMediaGallery:
    name = 'media_gallery'
    aliases = ['image_gallery', 'media_grid', 'image_grid']

    @with_signature(
        size = Par(int, 9, 'The number of images to combine into one gallery (max. 10, but 9 gives a consistent grid).', lambda x: 0 < x <= 10),
    )
    @staticmethod
    async def spout_function(ctx: Context, values: list[str], *, size: int):
        '''
        Outputs the provided image URLs as a Discord image gallery.

        If the images don't fit in one gallery (determined by the 'size' parameter)
        it will split them over multiple galleries in the same message.
        If they don't all fit in the same message (limit of 40 images or 10 galleries per message)
        it will further split them over multiple messages.
        '''

        # Normalize given URLs by running them through the url parser first
        values = [url(v) for v in values]

        # Keep a queue of galleries that still need to be posted and a count of images in these galleries
        galleries = []
        image_count = 0

        # Helper method that posts and clears the current queue of galleries, if any
        async def post_galleries():
            nonlocal galleries, image_count
            image_count = 0
            if not galleries:
                return
            layout_view = ui.LayoutView()
            for gallery in galleries:
                layout_view.add_item(gallery)
            await ctx.channel.send(view=layout_view)
            galleries.clear()

        # Split image URLs over galleries by the given max. number of images per gallery,
        #   then further split these galleries over multiple messages
        #   as a single message may only contain up to 40 images or 10 galleries.
        for i in range(0, len(values), size):
            urls = values[i:i+size]
            # Post the current gallery queue if this new one would put it over the image or gallery limit
            if image_count + len(urls) > 40 or len(galleries) == 10:
                await post_galleries()
            # Create a gallery containing the image URLs
            gallery = ui.MediaGallery(*(components.MediaGalleryItem(url) for url in urls))
            galleries.append(gallery)
            image_count += len(urls)

        # Post the final gallery queue
        await post_galleries()
