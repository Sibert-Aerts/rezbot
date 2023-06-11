import re
import os
import pickle
from discord import Embed, Guild, TextChannel

from utils.texttools import block_format
from pipes.pipeline import Pipeline
from pipes.processor import PipelineProcessor

# Save events to the same directory as macros... because they're essentially macros.
def DIR(filename=''):
    return os.path.join(os.path.dirname(__file__), 'macros', filename)

###############################################################
#                             Event                           #
###############################################################

class Event:
    def __init__(self, name, channel, script):
        self.name: str = name
        self.version: int = 2
        self.channels: list[int] = [channel.id]
        self.script: str = script

    def update(self, script):
        self.script = script

    def test(self, channel):
        return self.is_enabled(channel)

    def is_enabled(self, channel):
        # TODO: distinguish threads/channels?
        return channel.id in self.channels

    def disable_in_guild(self, guild: Guild):
        # Throw out all Channels belonging to the given guild
        guild_channels = [c.id for c in guild.channels]
        self.channels = [c for c in self.channels if not c in guild_channels]

    def embed(self, ctx=None, channel: TextChannel=None):
        channel = channel or ctx.channel
        guild = channel.guild

        desc = '{}abled in this channel'.format( 'En' if self.is_enabled(channel) else 'Dis' )
        embed = Embed(title='Event: ' + self.name, description=desc, color=0x7628cc)
        
        ### List of the current server's channels it's enabled in
        channels = [ ch.mention for ch in guild.text_channels if ch.id in self.channels ]
        embed.add_field(name='Enabled channels', value=', '.join(channels) or 'None', inline=True)

        ## Script
        embed.add_field(name='Script', value=block_format(self.script), inline=False)

        return embed


class OnMessage(Event):
    patternstr: str
    pattern: re.Pattern

    def __init__(self, name, channel, script, pattern):
        super().__init__(name, channel, script)
        self.set_trigger(pattern)

    def update(self, script, pattern):
        super().update(script)
        self.set_trigger(pattern)

    def get_trigger_str(self):
        return self.patternstr

    def set_trigger(self, pattern: str):
        self.patternstr = pattern
        self.pattern = re.compile(pattern, re.S)

    def test(self, message):
        '''Test whether or not the given message should trigger the Event's execution.'''
        return super().test(message.channel) and self.pattern.search(message.content)

    def __str__(self):
        return '**{}**: ON MESSAGE `{}`'.format(self.name, self.patternstr)

    def embed(self, ctx=None, **kwargs):
        embed = super().embed(ctx, **kwargs)
        return embed.insert_field_at(0, name='On message', value='`%s`' % self.patternstr, inline=True)
        

class OnReaction(Event):
    emotes: list[str]

    def __init__(self, name, channel, script: str, emotes: str):
        super().__init__(name, channel, script)
        self.set_trigger(emotes)

    def update(self, script: str, emotes: str):
        super().update(script)
        self.set_trigger(emotes)

    def get_trigger_str(self):
        return ''.join(self.emotes)

    def set_trigger(self, emotes: str):
        self.emotes = re.split('\s*,\s*', emotes)

    def test(self, channel, emoji):
        '''Test whether or not a given reaction-addition should trigger this Event.'''
        return super().test(channel) and emoji in self.emotes

    def __str__(self):
        return '**{}**: ON REACTION `{}`'.format(self.name, ','.join(self.emotes))

    def embed(self, ctx=None, **kwargs):
        embed = super().embed(ctx, **kwargs)
        return embed.insert_field_at(0, name='On reaction', value=','.join(self.emotes), inline=True)

###############################################################
#                             Events                          #
###############################################################

class Events:
    '''Dict-like wrapper for loading/holding/saving Events, mostly copy-pasted from the one in macros.py'''
    events: dict[str, Event]

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
                event = self.events[name] = eventType(name, channel, script, trigger)
            self.write()

        except Exception as e:
            ## Failed to register event (most likely regex could not parse)
            await channel.send('Failed to {} event:\n\t{}: {}'.format( 'register' if mode=='NEW' else 'update', type(e).__name__, e))
            raise e

        else:
            ## Mission complete
            msg = f'New event `{name}` registered.' if mode == 'NEW' else 'Event `{name}` updated.'
            view = EventView(event, self, channel)
            view.add_item(await channel.send(msg, embed=event.embed(channel=channel), view=view))
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
'The canonical object managing all Event instances, responsible for serialising and deserialising them.'


# Circular dependency
from pipes.views import EventView