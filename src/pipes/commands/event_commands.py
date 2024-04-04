import discord
from discord.ext import commands

from pipes.core.events import events
from pipes.views import EventView
from rezbot_commands import RezbotCommands
from utils.texttools import chunk_lines
import permissions

###############################################################
#            A module providing commands for pipes            #
###############################################################

class EventCommands(RezbotCommands):

    @commands.command(aliases=['event'], hidden=True)
    async def events(self, ctx: commands.Context, name=''):
        ''' List all Events, active status and triggers. '''
        if not events:
            await ctx.send('No events registered.')
            return

        if not name or name in ['enabled', 'disabled']:
            ## Print all events
            enabled = []; disabled = []
            for event in events.values():
                if ctx.channel.id in event.channels: enabled.append(event)
                else: disabled.append(event)

            infos = []
            if enabled and name != 'disabled':
                infos += ['**__Enabled:__**'] + [ '• ' + str(e) for e in enabled ]
            if disabled and name != 'enabled':
                infos += ['**__Disabled:__**'] + [ ', '.join(e.name for e in disabled) ]
            for chunk in chunk_lines(infos):
                await ctx.send(chunk)

        else:
            ## Print info on a specific event
            if name not in events:
                await ctx.send('Event not found.')
                return
            event = events[name]
            view = EventView(self.bot, event, events, ctx.channel)
            view.set_message(await ctx.send(embed=event.embed(bot=ctx.bot, channel=ctx.channel), view=view))

    @commands.command(aliases=['enable_events'], hidden=True)
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

    @commands.command(aliases=['disable_events'], hidden=True)
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

    @commands.command(aliases=['del_event'], hidden=True)
    @commands.guild_only()
    @permissions.check(permissions.owner)
    async def delete_event(self, ctx, name):
        ''' Deletes the specified event entirely. '''
        if name not in events:
            await ctx.send('No event "{}" found.'.format(name)); return
        e = events[name]
        del events[name]
        await ctx.send('Deleted event "{}"'.format(e.name))

    @commands.command(aliases=['event_set_author'], hidden=True)
    @commands.guild_only()
    @permissions.check(permissions.owner)
    async def set_event_author(self, ctx: commands.Context, name: str, author_id: int):
        ''' Assigns an Event's author by ID. '''
        if name not in events:
            return await ctx.send(f'No event "{name}" found.')
        event = events[name]
        author = ctx.guild.get_member(author_id) or self.bot.get_user(author_id)
        if not author:
            return await ctx.send(f'Invalid author ID "{author_id}".')
        event.author_id = author.id
        events.write()
        await ctx.send(f'Assigned {author.display_name} as author of event "{event.name}".')

    @commands.command(hidden=True)
    async def dump_events(self, ctx):
        ''' Uploads the source file containing all serialised Events, for backup/debug purposes. '''
        await ctx.send(file=discord.File(events.DIR(events.json_filename)))


# Load the bot cog
async def setup(bot: commands.Bot):
    await bot.add_cog(EventCommands(bot))
