import aiohttp
import discord
from discord.ext import commands
from resource.upload import uploads
from mycommands import MyCommands
import utils.texttools as texttools
from utils.util import parse_bool

class UploadCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)


    @commands.command(pass_context=True)
    async def upload(self, ctx):
        '''Upload a txt file for the bot to use.'''
        if not ctx.message.attachments:
            await self.say('Please attach a txt file with your message.'); return

        # Are there ever more than 1 attachments?
        attached = ctx.message.attachments[0]
        r = await aiohttp.get(attached['url'])
        text = await r.text()
        author = ctx.message.author

        file = uploads.add_file(attached['filename'], text, author.name, author.id)

        await self.say('File received! Saved %d lines as `%s`' % (len(file.lines), file.info.name))


    @commands.command(aliases=['file', 'uploads'])
    async def files(self, file=''):
        '''List all uploaded txt files, or show the contents of a specific file.'''
        if file == '':
            #### Print a list of all files
            text = 'Files: ' + ', '.join(f for f in uploads) + '\n'
            text += 'For more details on a specific file, use >file [name]'
            await self.say(text)
            return

        if file not in uploads:
            await self.say('No file by name `%s` found!' % file); return

        #### Print info on the specific file
        file = uploads[file]
        info = file.info
        lines = file.get()

        # TODO: make this a little File.embed() ?
        text = '**File:** ' + info.name + '\n'
        text += '**Uploader:** ' + info.author_name + '\n'
        text += '**Order:** ' + ('Sequential' if info.sequential else 'Random')
        text += ', **Split on:** ' + (('`' + repr(info.splitter)[1:-1] + '`') if not info.sentences else 'Sentences') + '\n'

        MAXLINES = 8
        if len(lines) > MAXLINES:
            text += texttools.block_format('\n'.join(lines[:MAXLINES-1]) + '\n...%d more lines omitted' % (len(lines) - MAXLINES + 1))
        else:
            text += texttools.block_format('\n'.join(lines))
        await self.say(text)

    # List of attributes modifiable by the below command
    str_attributes = ['name', 'splitter']
    bool_attributes = ['sequential', 'sentences']
    attributes = str_attributes + bool_attributes


    @commands.command(aliases=['set_file'])
    async def file_set(self, file, attribute, value):
        '''
        Set an attribute of an uploaded file.
        
        Available attributes:
        name: How the file is addressed.
        splitter: The regex that determines how the file is split into lines.
        sequential: Boolean determining whether or not the order of the lines in the file matters.
        sentences: Boolean determining whether the file should be split into sentences, rather than split on the regex splitter.
        '''
        if file not in uploads:
            await self.say('No file by name `%s` found!' % file); return
        file = uploads[file]

        if attribute not in UploadCommands.attributes:
            await self.say('Second argument must be one of: %s' % ', '.join(UploadCommands.attributes)); return

        if attribute in UploadCommands.bool_attributes:
            value = parse_bool(value)
        elif attribute in UploadCommands.str_attributes:
            value = value.strip()
            if value == '':
                await self.say('Please use a less blank-y value.'); return

        oldVal = getattr(file.info, attribute)
        if attribute == 'name':
            # Special case because names of different files aren't allowed to overlap
            if value == oldVal: return
            if value in uploads:
                await self.say('That name is already in use.'); return
            # Everything seems in order to make this change
            del uploads[oldVal]
            uploads[value] = file
            file.info.name = value
        else:
            setattr(file.info, attribute, value)

        if attribute == 'splitter':
            # Special case, if the splitter changed we have to reload the split lines
            file.lines = None
            file.get_lines()

        file.info.write()
        await self.say('Changed {} from "{}" to "{}"!'.format(attribute, str(oldVal), str(value)))



# Commands cog
def setup(bot):
    bot.add_cog(UploadCommands(bot))