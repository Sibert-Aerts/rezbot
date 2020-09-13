import re
import os
import pickle
from discord import Embed
from utils.texttools import block_format
from .processor import Pipeline, PipelineProcessor

# Save events to the same directory as macros... because they're essentially macros.
def DIR(filename=''):
    return os.path.join(os.path.dirname(__file__), 'macros', filename)

###############################################################
#                             Event                           #
###############################################################

class Event:
    def __init__(self, name, channel, script):
        self.name = name
        self.version = 2
        self.channels = [channel.id]
        self.script = script

    def update(self, script):
        self.script = script

    def test(self, channel):
        return channel.id in self.channels

    def embed(self, ctx):
        desc = '{}abled in this channel'.format( 'En' if ctx.channel.id in self.channels else 'Dis' )
        embed = Embed(title='Event: ' + self.name, description=desc, color=0x7628cc)
        
        ### List of the current server's channels it's enabled in
        channels = [ ch.mention for ch in ctx.guild.text_channels if ch.id in self.channels ]
        embed.add_field(name='Enabled channels', value=', '.join(channels) or 'None', inline=True)

        ## Script
        embed.add_field(name='Script', value=block_format(self.script), inline=False)

        return embed

class OnMessage(Event):
    def __init__(self, name, channel, script, pattern):
        super().__init__(name, channel, script)
        self.patternstr = pattern
        self.pattern = re.compile(pattern)

    def update(self, script, pattern):
        super().update(script)
        self.patternstr = pattern
        self.pattern = re.compile(pattern)

    def test(self, message):
        '''Test whether or not the given message should trigger the Event's execution.'''
        return super().test(message.channel) and self.pattern.search(message.content)

    def __str__(self):
        return '**{}**: ON MESSAGE `{}`'.format(self.name, self.patternstr)

    def embed(self, ctx):
        embed = super().embed(ctx)
        return embed.insert_field_at(0, name='On message', value='`%s`' % self.patternstr, inline=True)
        

class OnReaction(Event):
    def __init__(self, name, channel, script, emotes):
        super().__init__(name, channel, script)
        self.emotes = re.split('\s*,\s*', emotes)

    def update(self, script, emotes):
        super().update(script)
        self.emotes = re.split('\s*,\s*', emotes)

    def test(self, channel, emoji):
        '''Test whether or not a given reaction-addition should trigger this Event.'''
        return super().test(channel) and emoji in self.emotes

    def __str__(self):
        return '**{}**: ON REACTION `{}`'.format(self.name, ','.join(self.emotes))

    def embed(self, ctx):
        embed = super().embed(ctx)
        return embed.insert_field_at(0, name='On reaction', value=','.join(self.emotes), inline=True)

###############################################################
#                             Events                          #
###############################################################

class Events:
    '''Dict-like wrapper for loading/holding/saving Events, mostly copy-pasted from the one in macros.py'''
    def __init__(self, DIR, filename):
        self.events = {}
        self.DIR = DIR
        self.filename = filename
        try:
            if not os.path.exists(DIR()): os.mkdir(DIR())
            self.events = pickle.load(open(DIR(filename), 'rb+'))
            print('{} events loaded from "{}"!'.format(len(self.events), filename))
        except Exception as e:
            print(e)
            print('Failed to load events from "{}"!'.format(DIR(filename)))

    command_pattern = re.compile(r'\s*(NEW|EDIT) EVENT (\w[\w.]+) ON (MESSAGE|REACT(?:ION)?) (.*?)\s*::\s*(.*)'.replace(' ', '\s+'), re.I | re.S )
    #                                  ^^^^^^^^         ^^^^^^^^      ^^^^^^^^^^^^^^^^^^^^^   ^^^          ^^

    async def parse_command(self, string, channel):
        m = re.match(self.command_pattern, string)
        if m is None: return False

        mode, name, what, trigger, script = m.groups()
        mode = mode.upper()
        eventType = {'M': OnMessage, 'R': OnReaction}[what[0].upper()]
        name = name.lower()

        ## Check for naming conflicts
        if name in self.events and mode == 'NEW':
            await channel.send('An event by that name already exists. Use EDIT instead of NEW, or choose a different name.')
            return True
        if name not in self.events and mode == 'EDIT':
            await channel.send('An event by that name does not exist yet. Use NEW instead of EDIT, or choose an existing name.')
            return True

        ## Statically analyse the script for parsing errors and warnings
        _, pipeline = PipelineProcessor.split(script)
        errors = Pipeline(pipeline).parser_errors
        if errors.terminal:
            await channel.send('Failed to save event due to parsing errors:', embed=errors.embed())
            return True
        elif errors:
            await channel.send('Encountered warnings while parsing event:', embed=errors.embed())

        ## Register the event
        try:
            if mode == 'EDIT':
                event = self.events[name]
                if not isinstance(event, eventType):
                    # Is this error lame? we .update() events so that the list of channels isn't lost but maybe it could happen differently
                    await channel.send(f'Event "{name}" cannot be edited to be a different type. Try deleting it first.')
                    return True
                event.update(script, trigger)
            else:
                self.events[name] = eventType(name, channel, script, trigger)
            self.write()

        except Exception as e:
            ## Failed to register event (most likely regex could not parse)
            await channel.send('Failed to {} event:\n\t{}: {}'.format( 'register' if mode=='NEW' else 'update', e.__class__.__name__, e))
            raise e

        else:
            ## Mission complete
            await channel.send( ('New event "%s" registered.' if mode == 'NEW' else 'Event "%s" updated.') % name )
            return True

    def write(self):
        '''Write the list of events to a pickle file.'''
        pickle.dump(self.events, open(self.DIR(self.filename), 'wb+'))

    def __contains__(self, name):
        return name in self.events

    def __iter__(self):
        return (i for i in self.events)

    def values(self):
        return self.events.values()

    def __getitem__(self, name):
        return self.events[name]

    def __setitem__(self, name, val):
        self.events[name] = val
        self.write()
        return val

    def __delitem__(self, name):
        del self.events[name]
        self.write()

    def __bool__(self):
        return len(self.events) > 0

    def __len__(self):
        return len(self.events)

events = Events(DIR, 'events.p')