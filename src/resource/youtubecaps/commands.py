import asyncio
import re
import random

import discord
from discord.ext import commands

from mycommands import MyCommands
from resource.youtubecaps import youtubeCaps
import utils.util as util
import permissions

'''
Main command module, contains a bunch of random functionality.
'''

info_string = '''
Commands for using the youtube captions feature:
• **youtube_videos**: List all videos with saved captions
• **youtube random**: Random caption from a random video
• **youtube [video title, ID or tag]**: Random caption from matching video(s)
• **youtube [other query]**: Random caption that matches the query (from any video)

Commands for moderating captions:
• **youtube_add [video url or ID]**: Save video's captions
• **youtube_remove [video]**: Delete video's saved captions
• **youtube_alias [video] [alias]**: Set video's alias
• **youtube_add/remove_tags [video] [...tags]**: Add/remove tags to video
'''

class YoutubeCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command(aliases=['yt'])
    async def youtube(self, ctx):
        '''Get a random caption from a youtube video from a list of saved youtube videos'''
        query = util.strip_command(ctx)
        if query.strip() in ['', 'help']:
            await ctx.send(info_string)
        elif query.strip().lower() == 'random':
            cap, url = youtubeCaps.get_random()
            await ctx.send(url)
            await ctx.send(cap)
        else:
            try:
                cap, url = youtubeCaps.search(query)
                await ctx.send(url)
                await ctx.send(cap)
            except IndexError:
                await ctx.send('no results found for search "{}".'.format(query))

    @commands.command(aliases=['yt_random'], hidden=True)
    async def youtube_random(self, ctx):
        '''Get a random caption from a youtube video from a list of saved youtube videos'''
        cap, url = youtubeCaps.get_random()
        await ctx.send(url)
        await ctx.send(cap)


    @commands.command(aliases=['yt_add'])
    async def youtube_add(self, ctx, url, alias=None, *tags):
        '''Add a video to the list of tracked videos'''
        try:
            if url[0] == '<' and url[-1] == '>': url = url[1:-1]
            title, what = youtubeCaps.download_subs(url, alias, tags)
            aliastext = '' if alias is None else ' with alias "{}"'.format(alias)
            tagstext = '' if len(tags) == 0 else ', tags: ' + ', '.join(tags)
            await ctx.send('successfully saved {} for youtube video "{}"{}{}'.format(what, title, aliastext, tagstext))
        except ValueError as e:
            await ctx.send(e)
        except Exception as e:
            print(e)
            await ctx.send('something went wrong. make sure the url is correct.')


    @commands.command(aliases=['youtube_remove', 'yt_delete', 'yt_remove', 'yt_del'])
    @permissions.check(permissions.owner)
    async def youtube_delete(self, ctx, identifier):
        '''Delete a video from the list of tracked videos'''
        try:
            title = youtubeCaps.delete(identifier)
            await ctx.send('successfully deleted captions for video "{}".'.format(title))
        except ValueError as e:
            await ctx.send(e)


    @commands.command(aliases=['yt_alias'])
    async def youtube_alias(self, ctx, ident, alias):
        '''Change a video's alias'''
        video = youtubeCaps.identify(ident)
        if video is None:
            await ctx.send('"{}" does not uniquely identify a video.'.format(ident))
            return
        oldAlias = video.alias
        video.alias = alias
        video.write()
        if oldAlias is None:
            await ctx.send('successfully set the alias for video "{}" to "{}".'.format(video.title, alias))
        else:
            await ctx.send('successfully changed the alias for video "{}" from "{}" to "{}".'.format(video.title, oldAlias, alias))


    @commands.command(aliases=['youtube_tag', 'youtube_add_tag', 'yt_tag'])
    async def youtube_add_tags(self, ctx, ident, *tags):
        '''Give a video new tags'''
        video = youtubeCaps.identify(ident)
        if video is None:
            await ctx.send('"{}" does not uniquely identify a video.'.format(ident))
            return
        video.tags = list(set(video.tags).union(tags))
        video.write()
        await ctx.send('tags successfully added, tags for "{}" are now: {}.'.format(video.title, ', '.join(video.tags)))


    @commands.command(aliases=['youtube_remove_tag', 'youtube_delete_tags', 'youtube_delete_tag', 'yt_del_tag', 'yt_del_tags'])
    async def youtube_remove_tags(self, ctx, ident, *tags):
        '''Remove tags from a video.'''
        video = youtubeCaps.identify(ident)
        if video is None:
            await ctx.send('"{}" does not uniquely identify a video.'.format(ident))
            return
        video.tags = list(set(video.tags) - set(tags))
        video.write()
        await ctx.send('tags successfully removed, tags for "{}" are now: {}.'.format(video.title, ', '.join(video.tags)))


    @commands.command(aliases=['youtube_info', 'youtube_list', 'youtube_all', 'yt_videos', 'yt_info', 'yt_list', 'yt_all'])
    async def youtube_videos(self, ctx, ident=''):
        '''List all known youtube videos.'''
        if ident == '':
            info = 'Loaded videos:\n'
            for id in youtubeCaps.videos:
                video = youtubeCaps.videos[id]
                info += '• **{}**'.format(video.title)
                if video.alias:
                    info += ' AKA "{}"'.format(video.alias)
                info += ', tags: `{}`\n'.format(', '.join(video.tags) if video.tags else '(None)')
            await ctx.send(info)
        else:
            video = youtubeCaps.identify(ident)
            if video is None:
                await ctx.send('"{}" does not uniquely identify a video.'.format(ident))
                return
            # TODO

# Commands cog
def setup(bot):
    bot.add_cog(YoutubeCommands(bot))