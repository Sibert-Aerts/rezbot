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

class YoutubeCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command(pass_context=True)
    async def youtube(self, ctx):
        '''Get a random caption from a youtube video from a list of saved youtube videos'''
        query = util.strip_command(ctx)
        if query.strip() in ['', 'help']:
            await self.say('<info string goes here>')
        elif query.strip().lower() == 'random':
            cap, url = youtubeCaps.get_random()
            await self.say(url)
            await self.say(cap)
        else:
            try:
                cap, url = youtubeCaps.search(query)
                await self.say(url)
                await self.say(cap)
            except IndexError:
                await self.say('no results found for search "{}".'.format(query))


    @commands.command(pass_context=True)
    async def youtube_add(self, ctx, url, alias=None, *tags):
        '''Add a video to the list of tracked videos'''
        try:
            if url[0] == '<' and url[-1] == '>': url = url[1:-1]
            title, what = youtubeCaps.download_subs(url, alias, tags)
            aliastext = '' if alias is None else ' with alias "{}"'.format(alias)
            tagstext = '' if len(tags) == 0 else ', tags: ' + ', '.join(tags)
            await self.say('successfully saved {} for youtube video "{}"{}{}'.format(what, title, aliastext, tagstext))
        except ValueError as e:
            await self.say(e)
        except Exception as e:
            print(e)
            await self.say('something went wrong. make sure the url is correct.')


    @commands.command(aliases=['youtube_remove'])
    @permissions.check('owner')
    async def youtube_delete(self, identifier):
        '''Delete a video from the list of tracked videos'''
        try:
            title = youtubeCaps.delete(identifier)
            await self.say('successfully deleted captions for video "{}".'.format(title))
        except ValueError as e:
            await self.say(e)


    @commands.command()
    async def youtube_alias(self, ident, alias):
        '''Change a video's alias'''
        video = youtubeCaps.identify(ident)
        if video is None:
            await self.say('"{}" does not uniquely identify a video.'.format(ident))
            return
        oldAlias = video.alias
        video.alias = alias
        video.write()
        if oldAlias is None:
            await self.say('successfully set the alias for video "{}" to "{}".'.format(video.title, alias))
        else:
            await self.say('successfully changed the alias for video "{}" from "{}" to "{}".'.format(video.title, oldAlias, alias))


    @commands.command(aliases=['youtube_tag', 'youtube_add_tag'])
    async def youtube_add_tags(self, ident, *tags):
        '''Give a video new tags'''
        video = youtubeCaps.identify(ident)
        if video is None:
            await self.say('"{}" does not uniquely identify a video.'.format(ident))
            return
        video.tags = list(set(video.tags).union(tags))
        video.write()
        await self.say('tags successfully added, tags for "{}" are now: {}.'.format(video.title, ', '.join(video.tags)))


    @commands.command(aliases=['youtube_remove_tag', 'youtube_delete_tags', 'youtube_delete_tag'])
    async def youtube_remove_tags(self, ident, *tags):
        '''Remove tags from a video.'''
        video = youtubeCaps.identify(ident)
        if video is None:
            await self.say('"{}" does not uniquely identify a video.'.format(ident))
            return
        video.tags = list(set(video.tags) - set(tags))
        video.write()
        await self.say('tags successfully removed, tags for "{}" are now: {}.'.format(video.title, ', '.join(video.tags)))


    @commands.command(aliases=['youtube_info'])
    async def youtube_videos(self, ident=''):
        '''List all known youtube videos.'''
        if ident == '':
            info = '**Loaded videos:**\n'
            for id in youtubeCaps.videos:
                video = youtubeCaps.videos[id]
                info += '• **{}**'.format(video.title)
                if video.alias:
                    info += ' AKA "{}"'.format(video.alias)
                info += ', tags: `{}`\n'.format(', '.join(video.tags) if video.tags else '(None)')
            await self.say(info)
        else:
            video = youtubeCaps.identify(ident)
            if video is None:
                await self.say('"{}" does not uniquely identify a video.'.format(ident))
                return
            # TODO

# Commands cog
def setup(bot):
    bot.add_cog(YoutubeCommands(bot))