from functools import wraps
import pickle

import discord
from discord.ext import commands

from .pipes import pipes
from .sources import sources
from .spouts import spouts
from .macros import pipe_macros, source_macros
from .processor import PipelineProcessor, SourceProcessor
from .events import events
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

        # Info on a specific pipe
        if name != '' and name in pipes:
            embed = pipes[name].embed()
            # bot takes credit for native pipes
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)
            await ctx.send(embed=embed)

        # Info on a macro pipe
        elif name != '' and name in pipe_macros:
            await ctx.send(embed=pipe_macros[name].embed())

        # Pipes in a specific category
        elif uname != '' and uname in pipes.categories:
            infos = []
            infos.append('Pipes in category {}:\n'.format(uname))
            
            colW = len(max(pipes, key=len)) + 2
            for pipe in pipes.categories[uname]:
                info = pipe.name.ljust(colW)
                if pipe.doc: info += pipe.small_doc
                infos.append(info)

            infos.append('')
            infos.append('Use >pipes [pipe name] to see more info on a specific pipe.')
            infos.append('Use >pipe_macros for a list of user-defined pipes.\n')
            await ctx.send(texttools.block_format('\n'.join(infos)))

        # List of categories
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
            # bot takes credit for native sources
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)
            await ctx.send(embed=embed)

        # Info on a macro source
        elif name != '' and name in source_macros:
            await ctx.send(embed=source_macros[name].embed())

        # Sources in a specific category
        elif uname != '' and uname in sources.categories:
            infos = []
            infos.append('Sources in category {}:\n'.format(uname))
            
            colW = len(max(sources, key=len)) + 2
            for source in sources.categories[uname]:
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
        if name != '' and name in spouts:
            embed = spouts[name].embed()
            # bot takes credit for native spouts
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)
            await ctx.send(embed=embed)

        # Info on all spouts
        else:
            infos = []
            infos.append('Here\'s a list of spouts, use >spouts [spout name] to see more info on a specific one.\nUse >spout_macros for a list of user-defined spouts.\n')
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
        if not events:
            await ctx.send('No events registered.')
            return

        if not name:
            ## Print all events
            active = []; inactive = []
            for event in events.values():
                if ctx.channel in event.channels: active.append(event)
                else: inactive.append(event)
            infos = []
            if active:
                infos += ['**__Active:__**']
                infos += [ '• ' + str(e) for e in active ]
            if inactive:
                infos += ['**__Inactive:__**']
                infos += [ '• ' + str(e) for e in inactive ]
            await ctx.send('\n'.join(infos))
        
        else:
            ## Print info on a specific event
            if name not in events:
                await ctx.send('Event not found.')
                return
            await ctx.send(embed=events[name].embed(ctx))

    @commands.command()
    @commands.guild_only()
    async def activate_event(self, ctx, name):
        if name not in events:
            await ctx.send('No event "{}" found.'.format(name)); return
        event = events[name]
        if ctx.channel in event.channels:
            await ctx.send('Event is already active in this channel.'); return
        event.channels.append(ctx.channel)
        await ctx.send('Activated event "{}" in #{}'.format(event.name, ctx.channel.name))

    @commands.command()
    @commands.guild_only()
    async def deactivate_event(self, ctx, name):
        if name not in events:
            await ctx.send('No event "{}" found.'.format(name)); return
        event = events[name]
        if ctx.channel not in event.channels:
            await ctx.send('Event is already inactive in this channel.'); return
        event.channels.remove(ctx.channel)
        await ctx.send('Deactivated event "{}" in #{}'.format(event.name, ctx.channel.name))

    @commands.command(aliases=['del_event'])
    @commands.guild_only()
    async def delete_event(self, ctx, name):
        if name not in events:
            await ctx.send('No event "{}" found.'.format(name)); return
        e = events[name]
        del events[name]
        await ctx.send('Deleted event "{}"'.format(e.name))


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

    def pipe_to_func(pipe):
        async def func(self, ctx):
            text = util.strip_command(ctx)
            proc = SourceProcessor(ctx.message)
            text = await proc.evaluate_composite_source(text)
            text = '\n'.join(pipe.as_command(text))
            await ctx.send(text)
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

    def source_to_func(source):
        async def func(self, ctx):
            text = util.strip_command(ctx)
            proc = SourceProcessor(ctx.message)
            text = await proc.evaluate_composite_source(text)
            text = '\n'.join(await source(ctx.message, text))
            await ctx.send(text)
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

    def spout_to_func(spout):
        async def func(self, ctx):
            text = util.strip_command(ctx)
            proc = SourceProcessor(ctx.message)
            text = await proc.evaluate_composite_source(text)
            await spout.as_command(self.bot, ctx.message, text)
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