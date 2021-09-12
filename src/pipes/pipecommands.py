import discord
from discord.ext import commands

from .pipe import Pipe, Source, Spout
from .pipes import pipes
from .sources import sources, SourceResources
from .spouts import spouts
from .macros import pipe_macros, source_macros
from .signature import Arguments
from .events import events
from .logger import ErrorLog
from mycommands import MyCommands
import utils.texttools as texttools
import utils.util as util

###############################################################
#            A module providing commands for pipes            #
###############################################################

class PipeCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command(aliases=['pipe_help', 'pipes_info', 'pipe_info', 'pipes_guide', 'pipe_guide'])
    async def pipes_help(self, ctx):
        '''Links the guide to using pipes.'''
        await ctx.send('https://github.com/Sibert-Aerts/rezbot/blob/master/PIPESGUIDE.md')

    @commands.command(aliases=['pipe'])
    async def pipes(self, ctx, name=''):
        '''Print a list of all pipes and their descriptions, or details on a specific pipe.'''
        name = name.lower()
        uname = name.upper()

        ## Info on a specific pipe, spout or source
        if name != '' and name in pipes or name in spouts or name in sources:
            embed = (pipes if name in pipes else spouts if name in spouts else sources)[name].embed()
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)
            await ctx.send(embed=embed)

        ## Info on a pipe macro or source macro
        elif name != '' and name in pipe_macros or name in source_macros:
            embed = (pipe_macros if name in pipe_macros	else source_macros)[name].embed(ctx)
            await ctx.send(embed=embed)

        ## List pipes in a specific category
        elif uname != '' and uname in pipes.categories:
            infos = []
            infos.append('Pipes in category {}:\n'.format(uname))
            
            category = pipes.categories[uname]
            colW = len(max((p.name for p in category), key=len)) + 3
            for pipe in category:
                info = pipe.name.ljust(colW)
                if pipe.doc: info += pipe.small_doc
                infos.append(info)

            infos.append('')
            infos.append('Use >pipes [pipe name] to see more info on a specific pipe.')
            infos.append('Use >pipe_macros for a list of user-defined pipes.\n')
            await ctx.send(texttools.block_format('\n'.join(infos)))

        ## List all categories
        else:
            infos = []
            infos.append('Categories:\n')
            
            colW = len(max(pipes.categories, key=len)) + 2
            for category in pipes.categories:
                info = category.ljust(colW)
                cat = pipes.categories[category]
                MAX_PRINT = 8
                if len(cat) > MAX_PRINT:
                    info += ', '.join(p.name for p in cat[:MAX_PRINT - 1]) + '... (%d more)' % (len(cat) - MAX_PRINT + 1)
                else:
                    info += ', '.join(p.name for p in cat)
                infos.append(info)
                
            infos.append('')
            infos.append('Use >pipes [category name] for the list of pipes in a specific category.')
            infos.append('Use >pipes [pipe name] to see more info on a specific pipe.')
            infos.append('Use >pipe_macros for a list of user-defined pipes.\n')
            await ctx.send(texttools.block_format('\n'.join(infos)))

    @commands.command(aliases=['source'])
    async def sources(self, ctx, name=''):
        '''Print a list of all sources and their descriptions, or details on a specific source.'''
        name = name.lower()
        uname = name.upper()

        # Info on a specific source
        if name != '' and name in sources:
            embed = sources[name].embed()
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)
            await ctx.send(embed=embed)

        # Info on a macro source
        elif name != '' and name in source_macros:
            await ctx.send(embed=source_macros[name].embed(ctx))

        # Sources in a specific category
        elif uname != '' and uname in sources.categories:
            infos = []
            infos.append('Sources in category {}:\n'.format(uname))
            
            category = sources.categories[uname]
            colW = len(max((s.name for s in category), key=len)) + 3
            for source in category:
                info = source.name.ljust(colW)
                if source.doc: info += source.small_doc
                infos.append(info)

            infos.append('')
            infos.append('Use >sources [source name] to see more info on a specific source.')
            infos.append('Use >source_macros for a list of user-defined sources.\n')
            await ctx.send(texttools.block_format('\n'.join(infos)))

        # List of categories
        else:
            infos = []
            infos.append('Categories:\n')
            
            colW = len(max(sources.categories, key=len)) + 2
            for category in sources.categories:
                info = category.ljust(colW)
                cat = sources.categories[category]
                MAX_PRINT = 8
                if len(cat) > MAX_PRINT:
                    info += ', '.join(s.name for s in cat[:MAX_PRINT - 1]) + '... (%d more)' % (len(cat) - MAX_PRINT + 1)
                else:
                    info += ', '.join(s.name for s in cat)
                infos.append(info)
                
            infos.append('')
            infos.append('Use >sources [category name] for the list of sources in a specific category.')
            infos.append('Use >sources [source name] to see more info on a specific source.')
            infos.append('Use >source_macros for a list of user-defined sources.\n')
            await ctx.send(texttools.block_format('\n'.join(infos)))

    @commands.command(aliases=['spout'])
    async def spouts(self, ctx, name=''):
        '''Print a list of all spouts and their descriptions, or details on a specific source.'''
        name = name.lower()

        # Info on a specific spout
        if name != '' and name in spouts or name in pipes:
            embed = (spouts if name in spouts else pipes)[name].embed()
            # bot takes credit for native spouts
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)
            await ctx.send(embed=embed)

        # Info on all spouts
        else:
            infos = []
            infos.append('Here\'s a list of spouts, use >spouts [spout name] to see more info on a specific one.')
            infos.append('')

            colW = len(max(spouts, key=len)) + 2
            for name in spouts:
                spout = spouts[name]
                info = name + ' ' * (colW-len(name))
                if spout.doc: info += spout.small_doc
                infos.append(info)

            text = texttools.block_format('\n'.join(infos))
            await ctx.send(text)


    ## EVENTS
    ### PUT IN OWN FILE STUPID

    @commands.command(aliases=['event'])
    async def events(self, ctx, name=''):
        ''' List all Events, active status and triggers. '''
        if not events:
            await ctx.send('No events registered.')
            return

        if not name:
            ## Print all events
            enabled = []; disabled = []
            for event in events.values():
                if ctx.channel.id in event.channels: enabled.append(event)
                else: disabled.append(event)
            infos = []
            if enabled:
                infos += ['**__Enabled:__**']
                infos += [ '• ' + str(e) for e in enabled ]
            if disabled:
                infos += ['**__Disabled:__**']
                infos += [ ', '.join( '**'+e.name+'**' for e in disabled ) ]
            await ctx.send('\n'.join(infos))
        
        else:
            ## Print info on a specific event
            if name not in events:
                await ctx.send('Event not found.')
                return
            await ctx.send(embed=events[name].embed(ctx))

    @commands.command(aliases=['enable_events'])
    @commands.guild_only()
    async def enable_event(self, ctx, *names):
        ''' Enables one or more events in the current channel, given as a list of names separated by spaces. '''
        fail = []; meh = []; succ = []

        for name in names:
            if name not in events:
                fail.append(name); continue
            event = events[name]
            if ctx.channel.id in event.channels:
                meh.append(name); continue
            event.channels.append(ctx.channel.id)
            succ.append(name)

        msg = []
        fmt = lambda l: '`' + '`, `'.join(l) + '`'
        if fail:
            msg.append('Event{} {} do{} not exist.'.format( 's' if len(fail)>1 else '', fmt(fail), '' if len(fail)>1 else 'es'))
        if meh:
            msg.append('Event{} {} {} already enabled in this channel.'.format( 's' if len(meh)>1 else '', fmt(meh), 'are' if len(meh)>1 else 'is'))
        if succ:
            msg.append('Event{} {} {} been enabled in {}.'.format( 's' if len(succ)>1 else '', fmt(succ), 'have' if len(succ)>1 else 'has', ctx.channel.mention))
            events.write()
        
        await ctx.send('\n'.join(msg))

    @commands.command(aliases=['disable_events'])
    @commands.guild_only()
    async def disable_event(self, ctx, *names):
        ''' Disables one or more events in the current channel, given as a list of names separated by spaces, or * to disable all events. '''
        if names and names[0] == '*':
            ## Disable ALL events in this channel
            for event in events.values():
                if ctx.channel.id in event.channels:
                    event.channels.remove(ctx.channel.id)
            await ctx.send('Disabled all events in {}'.format(ctx.channel.mention))
            return

        fail = []; meh = []; succ = []

        for name in names:
            if name not in events:
                fail.append(name); continue
            event = events[name]
            if ctx.channel.id not in event.channels:
                meh.append(name); continue
            event.channels.remove(ctx.channel.id)
            succ.append(name)

        msg = []
        fmt = lambda l: '`' + '`, `'.join(l) + '`'
        if fail:
            msg.append('Event{} {} do{} not exist.'.format( 's' if len(fail)>1 else '', fmt(fail), '' if len(fail)>1 else 'es'))
        if meh:
            msg.append('Event{} {} {} already disabled in this channel.'.format( 's' if len(meh)>1 else '', fmt(meh), 'are' if len(meh)>1 else 'is'))
        if succ:
            msg.append('Event{} {} {} been disabled in {}.'.format( 's' if len(succ)>1 else '', fmt(succ), 'have' if len(succ)>1 else 'has', ctx.channel.mention))
            events.write()
        
        await ctx.send('\n'.join(msg))

    @commands.command(aliases=['del_event'])
    @commands.guild_only()
    async def delete_event(self, ctx, name):
        ''' Deletes the specified event entirely. '''
        if name not in events:
            await ctx.send('No event "{}" found.'.format(name)); return
        e = events[name]
        del events[name]
        await ctx.send('Deleted event "{}"'.format(e.name))

    @commands.command(hidden=True)
    async def dump_events(self, ctx):
        ''' Uploads the source file containing all serialised Events, for backup/debug purposes. '''
        await ctx.send(file=discord.File(events.DIR(events.filename)))


    ## VARIABLES
    
    @commands.command(aliases=['list_persistent'])
    async def persistent_variables(self, ctx, pattern=None):
        await ctx.send( SourceResources.variables.list_names(pattern, True) )
    
    @commands.command(aliases=['list_transient'])
    async def transient_variables(self, ctx, pattern=None):
        await ctx.send( SourceResources.variables.list_names(pattern, False) )
    
    @commands.command(aliases=['list_all'])
    async def all_variables(self, ctx, pattern=None):
        await ctx.send( SourceResources.variables.list_names(pattern, True) +'\n'+ SourceResources.variables.list_names(pattern, False) )


# Load the bot cog
def setup(bot):
    # This part is icky but basically, take the pipes/sources/spouts from this library and
    # shoe-horn them into Discord.py's command module thingamajig
    # This may break some kind of weird use case for command modules but I don't care...
    #
    # But by doing this we get that discord.py does the command parsing for us,
    # and the commands show up in the "help" menu automatically, and behave nicely like
    # regular discord commands. Cool!

    ###############################################################
    #                  Turn pipes into commands!                  #
    ###############################################################

    newCommands = []

    def pipe_to_func(pipe: Pipe):
        async def func(self, ctx):
            text = util.strip_command(ctx)

            # Parse and process arguments from the command string
            args, text, err = Arguments.from_string(text, pipe.signature, greedy=False)
            if err.terminal: await ctx.send(embed=err.embed(f'`{pipe.name}`')); return
            args, err2 = await args.determine(ctx.message)
            text, err3 = await text.evaluate(ctx.message)
            err.extend(err2, 'arguments'); err.extend(err3, 'input string')
            if err.terminal: await ctx.send(embed=err.embed(f'`{pipe.name}`')); return

            try:
                # Apply the pipe to what remains of the command string
                text = '\n'.join(pipe([text], **args))
                await ctx.send(text)
            except Exception as e:
                err = ErrorLog()
                err(f'With args {" ".join( f"`{p}`={args[p]}" for p in args )}:\n\t{e.__class__.__name__}: {e}', True)
                await ctx.send(embed=err.embed(f'`{pipe.name}`'))

        func.__name__ = pipe.name
        func.__doc__ = pipe.command_doc()
        return func

    # Turn those pipes into discord.py bot commands!
    for pipe in pipes.command_pipes:
        func = pipe_to_func(pipe)
        # manually call the function decorator to make func into a command
        command = commands.command()(func)
        newCommands.append(command)

    ###############################################################
    #                 Turn sources into commands!                 #
    ###############################################################

    def source_to_func(source: Source):
        async def func(self, ctx):
            text = util.strip_command(ctx)

            # Parse and process arguments from the command string
            args, _, err = Arguments.from_string(text, source.signature, greedy=True)
            if err.terminal: await ctx.send(embed=err.embed(f'`{source.name}`')); return
            args, err2 = await args.determine(ctx.message)
            err.extend(err2, 'arguments')
            if err.terminal: await ctx.send(embed=err.embed(f'`{source.name}`')); return

            try:
                # Apply the source with the given arguments
                text = '\n'.join(await source(ctx.message, args))
                await ctx.send(text)
            except Exception as e:
                err = ErrorLog()
                err(f'With args {" ".join( f"`{p}`={args[p]}" for p in args )}:\n\t{e.__class__.__name__}: {e}', True)
                await ctx.send(embed=err.embed(f'`{source.name}`'))

        func.__name__ = source.name
        func.__doc__ = source.command_doc()
        return func

    # Turn those sources into discord.py bot commands!
    for source in sources.command_sources:
        func = source_to_func(source)
        # manually call the function decorator to make func into a command
        command = commands.command()(func)
        newCommands.append(command)

    ###############################################################
    #                  Turn spouts into commands!                 #
    ###############################################################

    def spout_to_func(spout: Spout):
        async def func(self, ctx):
            text = util.strip_command(ctx)

            # Parse and process arguments from the command string
            args, text, err = Arguments.from_string(text, spout.signature, greedy=False)
            if err.terminal: await ctx.send(embed=err.embed(f'`{spout.name}`')); return
            args, err2 = await args.determine(ctx.message)
            text, err3 = await text.evaluate(ctx.message)
            err.extend(err2, 'arguments'); err.extend(err3, 'input string')
            if err.terminal: await ctx.send(embed=err.embed(f'`{spout.name}`')); return

            try:
                # Apply the spout to what remains of the argstr
                await spout.function(self.bot, ctx.message, [text], **args)
            except Exception as e:
                err = ErrorLog()
                err(f'With args {" ".join( f"`{p}`={args[p]}" for p in args )}:\n\t{e.__class__.__name__}: {e}', True)
                await ctx.send(embed=err.embed(f'`{spout.name}`'))

        func.__name__ = spout.name
        func.__doc__ = spout.command_doc()
        return func

    # Turn those spouts into discord.py bot commands!
    for spout in spouts.command_spouts:
        func = spout_to_func(spout)
        # manually call the function decorator to make func into a command
        command = commands.command()(func)
        newCommands.append(command)

    cog = PipeCommands(bot)
    cog.__cog_commands__ = (*newCommands, *cog.__cog_commands__)
    bot.add_cog(cog)