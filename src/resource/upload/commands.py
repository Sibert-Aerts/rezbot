import aiohttp

import discord
from discord.ext import commands

import permissions
from rezbot_commands import RezbotCommands, command_with_signature, Par
from resource.upload import uploads, Files
import utils.texttools as texttools
from utils.util import parse_bool


class UploadCommands(RezbotCommands):

    @commands.command()
    async def upload(self, ctx):
        '''Upload a txt file for the bot to use.'''
        # Are there ever more than 1 attachments?
        attached = ctx.message.attachments
        if len(attached) != 1:
            return await ctx.send('Please attach exactly one txt file with your message.')

        attached = attached[0]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attached.url) as response:
                    text = await response.text(encoding='utf-8')
        except Exception as e:
            await ctx.send('Failed to parse text contents of file... make sure you upload a txt file.')
            raise e

        author = ctx.author

        try:
            file = uploads.add_file(attached.filename, text, author.name, author.id)
            await ctx.send('File received! Saved %d lines as `%s`' % (len(file.lines), file.info.name))
        except Exception as e:
            await ctx.send('Failed to add file! {}'.format(e))


    @commands.command()
    async def download(self, ctx, file):
        '''Download a txt file.'''
        if file not in uploads:
            return await ctx.send('No file by name `%s` found!' % file)
        file = uploads[file]
        discFile = discord.File(file.get_raw_path())
        await ctx.send(file=discFile)


    @commands.command(aliases=['file', 'uploads'])
    async def files(self, ctx, name:str=None):
        '''List all uploaded txt files, or show the contents of a specific file.'''

        categories = uploads.get_categories()

        #### Print a list of all categories
        if not name:
            lines = ['Categories:\n']

            colW = len(max(categories, key=len)) + 2
            for category in categories:
                line = category.ljust(colW)
                line += ', '.join(file.info.name for file in categories[category])
                lines.append(line)

            lines.append('')
            lines.append('Use >file [name] for details on a specific file.')
            lines.append('Use >file [CATEGORY] for the list of files in that category.')

            for block in texttools.block_chunk_lines(lines): await ctx.send(block)
            return


        #### Print a list of files in a specific category
        if name.isupper() and name in categories:
            files = categories[name]
            lines = [f'Files under category {name}:']

            described = [ file for file in files if file.info.description ]
            undescribed = [ file for file in files if not file.info.description ]

            if described:
                lines.append('')
                colW = len(max(described, key=lambda f: len(f.info.name)).info.name) + 2
                for file in described:
                    line = file.info.name.ljust(colW)
                    desc = file.info.description.split('\n', 1)[0]
                    line += desc if len(desc) <= 80 else desc[:75] + '(...)'
                    lines.append(line)

            if undescribed:
                lines.append('\nWithout descriptions:')
                lines += texttools.line_chunk_list([file.info.name for file in undescribed])

            lines.append('')
            lines.append('Use >file [name] for details on a specific file.')

            for block in texttools.block_chunk_lines(lines): await ctx.send(block)
            return


        #### Print info on a specific file
        if name not in uploads:
            return await ctx.send(f'No file by name `{name}` found!')
        name = uploads[name]
        info = name.info
        lines = name.get()

        # TODO: make this a little File.embed() ?
        # TODO: make this a little view, even?
        text = '**File:** ' + info.name
        text += ', **Uploader:** ' + info.author_name + '\n'
        text += '**Order:** ' + ('Sequential' if info.sequential else 'Random')
        text += ', **Split on:** ' + (('`' + repr(info.splitter)[1:-1] + '`') if not info.sentences else 'Sentences')
        text += ', **Entries:** ' + str(len(lines)) + '\n'
        text += '**Categories:** ' + (', '.join(info.categories) if info.categories else "(none)")
        text += ', **Editable:** ' + str(info.editable) + '\n'

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


    @commands.command(aliases=['set_file'])
    @command_with_signature(
        file = Par(str, None, 'The file whose attributes to update.'),
        # File attributes
        name = Par(Files.clean_name, None, 'How the file is addressed.', required=False),
        splitter = Par(str, None, 'The regex that determines how the raw file is split into entries.', required=False),
        categories = Par(str, None, 'Comma-separated list of categories which the file should be filed under.', required=False),
        sequential = Par(parse_bool, None, 'Boolean determining whether or not the order of the entries in the file matters.', required=False),
        sentences = Par(parse_bool, None, 'Boolean determining whether the file should be split into sentences, rather than split on the regex splitter.', required=False),
        editable = Par(parse_bool, None, 'Boolean determining whether the file\'s contents should be able to be edited.', required=False),
    )
    async def file_set(self, ctx, *, file, name, splitter, categories, sequential, sentences, editable):
        '''
        Update one or more attributes of an uploaded file.

        e.g. >file_set my_file.txt sequential=True name=new_name.txt
        '''
        if file not in uploads:
            return await ctx.send(f'No file by name `{file}` found!')
        file = uploads[file]

        if name and name != file.info.name:
            # Make sure the name doesn't overlap some other existing file
            if name in uploads:
                return await ctx.send('That name is already in use.')
            # Rename the file, including changing its key
            del uploads[file.info.name]
            uploads[name] = file
            file.info.name = name

        if categories is not None:
            file.info.categories = file.info.normalize_categories(categories)

        if sequential is not None:
            file.info.sequential = sequential
        if sentences is not None:
            file.info.sentences = sentences
        if editable is not None:
            file.info.editable = editable

        if splitter is not None:
            if not splitter:
                return await ctx.send('Please give a nonempty splitter.')
            file.info.splitter = splitter
            # Special case, if the splitter changed we have to reload the split lines
            file.lines = None

        file.info.write()
        await ctx.send(f'Updated {file.info.name}!')


    @commands.command(aliases=['categorise_files'])
    async def categorize_files(self, ctx, category: str, *files: str):
        ''' Add multiple files to a given category '''
        category = category.upper()
        succ = []; neut = []; fail = []

        for name in files:
            if name not in uploads:
                fail.append(name)
            file = uploads[name]

            if category in file.info.categories:
                neut.append(name)
            else:
                file.info.categories.append(category)
                file.info.write()
                succ.append(name)

        msg = []
        fmt = lambda l: '`' + '`, `'.join(l) + '`'
        if fail:
            msg.append('File{} {} do{} not exist.'.format( 's' if len(fail)>1 else '', fmt(fail), '' if len(fail)>1 else 'es'))
        if neut:
            msg.append('File{} {} {} already in category {}.'.format( 's' if len(neut)>1 else '', fmt(neut), 'are' if len(neut)>1 else 'is', category))
        if succ:
            msg.append('File{} {} {} been added to category {}.'.format( 's' if len(succ)>1 else '', fmt(succ), 'have' if len(succ)>1 else 'has', category))

        await ctx.send('\n'.join(msg))

    @commands.command(aliases=['decategorise_files'])
    async def decategorize_files(self, ctx, category: str, *files: str):
        ''' Remove multiple files from a given category. '''
        category = category.upper()
        succ = []; neut = []; fail = []

        for name in files:
            if name not in uploads:
                fail.append(name)
            file = uploads[name]

            if category not in file.info.categories:
                neut.append(name)
            else:
                file.info.categories.remove(category)
                file.info.write()
                succ.append(name)

        msg = []
        fmt = lambda l: '`' + '`, `'.join(l) + '`'
        if fail:
            msg.append('File{} {} do{} not exist.'.format( 's' if len(fail)>1 else '', fmt(fail), '' if len(fail)>1 else 'es'))
        if neut:
            msg.append('File{} {} {} not in category {}.'.format( 's' if len(neut)>1 else '', fmt(neut), 'are' if len(neut)>1 else 'is', category))
        if succ:
            msg.append('File{} {} {} been removed from category {}.'.format( 's' if len(succ)>1 else '', fmt(succ), 'have' if len(succ)>1 else 'has', category))

        await ctx.send('\n'.join(msg))


    @commands.command(aliases=['file_delete'])
    async def delete_file(self, ctx, filename):
        ''' Delete an uploaded file. Can only be done by owners of the bot or the file. '''

        if filename not in uploads:
            return await ctx.send('No file by name `%s` found!' % filename)
        file = uploads[filename]

        if permissions.has(ctx.author.id, permissions.owner) or ctx.author.id == file.info.author_id:
            uploads.delete_file(filename)
            await ctx.send('File `%s` successfully deleted.' % file.info.name)
        else:
            await ctx.send('Files can only be deleted by bot owners or the owner of the file.')


# Commands cog
async def setup(bot):
    await bot.add_cog(UploadCommands(bot))