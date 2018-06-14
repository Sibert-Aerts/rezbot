import aiohttp
import discord
from discord.ext import commands
from resource.upload import uploads
from mycommands import MyCommands
import utils.texttools as texttools

class UploadCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command(pass_context=True)
    async def upload(self, ctx):
        '''Upload a txt file for the bot to use.'''
        if not ctx.message.attachments:
            await self.say('Please attach a txt file with your message.')
            return

        # Are there ever more than 1 attachments?
        a = ctx.message.attachments[0]
        r = await aiohttp.get(a['url'])
        text = await r.text()
        file = uploads.add_file(a['filename'], text)
        await self.say('File received! Saved %d lines as `%s.txt`' % (len(file.lines), file.name))

    @commands.command(aliases=['txt', 'files'])
    async def uploads(self, file=''):
        '''List all uploaded txt files, or show the contents of a specific file.'''
        if file == '':
            await self.say('Files: ' + ', '.join(f for f in uploads))
        else:
            f = uploads[file]
            text = 'Contents of **%s**:' % file + '\n'
            lines = f._get()
            MAXLINES = 8
            if len(lines) > MAXLINES:
                text += texttools.block_format('\n'.join(lines[:9]) + '\n...%d more lines omitted' % (len(lines) - MAXLINES + 1))
            else:
                text += texttools.block_format('\n'.join(lines))
            await self.say(text)


# Commands cog
def setup(bot):
    bot.add_cog(UploadCommands(bot))