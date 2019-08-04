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


    @commands.command()
    async def upload(self, ctx):
        '''Upload a txt file for the bot to use.'''
        if not ctx.message.attachments:
            await ctx.send('Please attach a txt file with your message.'); return

        # Are there ever more than 1 attachments?
        attached = ctx.message.attachments[0]
        print(attached)

        async with aiohttp.ClientSession() as session:
            async with session.get(attached.url) as response:
                text = await response.text()

        author = ctx.author

        file = uploads.add_file(attached.filename, text, author.name, author.id)

        await ctx.send('File received! Saved %d lines as `%s`' % (len(file.lines), file.info.name))


    @commands.command()
    async def download(self, ctx, file):
        '''Download a txt file.'''
        if file not in uploads:
            await ctx.send('No file by name `%s` found!' % file); return
        file = uploads[file]
        discFile = discord.File(file.get_raw_path())
        await ctx.send(file=discFile)


    @commands.command(aliases=['file', 'uploads'])
    async def files(self, ctx, file=''):
        '''List all uploaded txt files, or show the contents of a specific file.'''
        if file == '':
            #### Print a list of all files
            text = 'Files: ' + ', '.join(f for f in uploads) + '\n'
            text += 'For more details on a specific file, use >file [name]'
            await ctx.send(text)
            return

        if file not in uploads:
            await ctx.send('No file by name `%s` found!' % file); return

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
        MAXCHARS = 600
        print_lines = []
        chars = 0
        for line in lines:
            if len(line) + chars > MAXCHARS:
                if not print_lines:
                    print_lines.append(line[:MAXCHARS - 40] + '(...)')
                if len(lines) > len(print_lines):
                    print_lines.append('...%d more lines omitted' % (len(lines) - len(print_lines)))
                break
            print_lines.append(line)
            chars += len(line)
            if len(print_lines) > MAXLINES:
                print_lines[MAXLINES:] = []
                print_lines.append('...%d more lines omitted' % (len(lines) - len(print_lines)))
                break
        
        text += texttools.block_format('\n'.join(print_lines))
        await ctx.send(text)


    # List of attributes modifiable by the below command
    str_attributes = ['name', 'splitter']
    bool_attributes = ['sequential', 'sentences']
    attributes = str_attributes + bool_attributes

    @commands.command(aliases=['set_file'])
    async def file_set(self, ctx, file, attribute, value):
        '''
        Set an attribute of an uploaded file.
        
        Available attributes:
        name: How the file is addressed.
        splitter: The regex that determines how the file is split into lines.
        sequential: Boolean determining whether or not the order of the lines in the file matters.
        sentences: Boolean determining whether the file should be split into sentences, rather than split on the regex splitter.

        e.g. >file_set filename name newname
        '''
        if file not in uploads:
            await ctx.send('No file by name `%s` found!' % file); return
        file = uploads[file]

        if attribute not in UploadCommands.attributes:
            await ctx.send('Second argument must be one of: %s' % ', '.join(UploadCommands.attributes)); return

        if attribute in UploadCommands.bool_attributes:
            value = parse_bool(value)
        elif attribute in UploadCommands.str_attributes:
            value = value.strip()
            if value == '':
                await ctx.send('Please use a less blank-y value.'); return

        oldVal = getattr(file.info, attribute)
        if attribute == 'name':
            # Special case because names of different files aren't allowed to overlap
            if value == oldVal: return
            if value in uploads:
                await ctx.send('That name is already in use.'); return
            # Everything seems in order to make this change
            del uploads[oldVal]
            uploads[value] = file
            file.info.name = value
        else:
            setattr(file.info, attribute, value)

        if attribute == 'splitter':
            # Special case, if the splitter changed we have to reload the split lines
            file.lines = None

        file.info.write()
        await ctx.send('Changed {} from `{}` to `{}`!'.format(attribute, str(oldVal), str(value)))



# Commands cog
def setup(bot):
    bot.add_cog(UploadCommands(bot))