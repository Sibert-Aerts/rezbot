import re
import os
import pickle
from shutil import copyfile
from discord import Embed, Guild, TextChannel, Message, Client

from utils.util import normalize_name
from utils.texttools import block_format
from pipes.pipeline_with_origin import PipelineWithOrigin

# Save events to the same directory as macros... because they're essentially macros.
def DIR(filename=''):
    return os.path.join(os.path.dirname(__file__), 'macros', filename)

###############################################################
#                             Event                           #
###############################################################

class Event:
    def __init__(self, name, desc, author, channel, script):
        self.version = 3
        self.name: str = name
        self.desc: str = desc
        self.author_id: int = author.id
        self.channels: list[int] = [channel.id]
        self.script: str = script

    def v2_to_v3(self):
        if self.version != 2:
            return self
        self.version = 3
        self.desc = None
        self.author_id = 154597714619793408 # Rezuaq
        return self

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

    def embed(self, *, bot: Client=None, channel: TextChannel=None, **kwargs):
        
        ## Description
        desc_lines = []
        if self.desc:
            desc_lines.append(self.desc)
        if channel:
            desc_lines.append('{}abled in this channel'.format( 'En' if self.is_enabled(channel) else 'Dis' ))

        embed = Embed(title='Event: ' + self.name, description='\n'.join(desc_lines), color=0x7628cc)

        ### List of channels it's enabled in within this guild
        if channel:
            channels = [ ch.mention for ch in channel.guild.text_channels if ch.id in self.channels ]
            embed.add_field(name='Enabled channels', value=', '.join(channels) or 'None', inline=True)

        ## Script box
        script_disp = self.script
        if len(script_disp) > 900:
            # Embed fields have a 1024 char limit, but play it safe
            script_disp = script_disp[:900] + ' (...)'
        embed.add_field(name='Script', value=block_format(script_disp), inline=False)

        ### Author credit footer
        author = None
        if channel and channel.guild:
            author = channel.guild.get_member(self.author_id)
        if not author and bot:
            author = bot.get_user(self.author_id)
        if author:
            embed.set_footer(text=author.display_name, icon_url=author.avatar)

        return embed


class OnMessage(Event):
    patternstr: str
    pattern: re.Pattern

    def __init__(self, name, desc, author, channel, script, pattern):
        super().__init__(name, desc, author, channel, script)
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

    def embed(self, **kwargs):
        embed = super().embed(**kwargs)
        return embed.insert_field_at(0, name='On message', value='`%s`' % self.patternstr, inline=True)
        

class OnReaction(Event):
    emotes: list[str]

    def __init__(self, name, desc, author, channel, script: str, emotes: str):
        super().__init__(name, desc, author, channel, script)
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

    def embed(self, **kwargs):
        embed = super().embed(**kwargs)
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
            self.convert_v2_to_v3()
            print('{} events loaded from "{}"!'.format(len(self.events), filename))
        except Exception as e:
            print(e)
            print('Failed to load events from "{}"!'.format(DIR(filename)))

    def convert_v2_to_v3(self):
        FROM_VERSION = 2
        TO_VERSION = 3
        if not any(e for e in self.events if self.events[e].version != TO_VERSION): return
        try:
            copyfile(self.DIR(self.filename), self.DIR(self.filename + f'.v{FROM_VERSION}_backup'))
            count = 0
            for name in self.events:
                event = self.events[name]
                if event.version == FROM_VERSION:
                    self.events[name] = event.v2_to_v3()
                    count += 1
                elif event.version != TO_VERSION:
                    print('! ULTRA-OUTDATED EVENT COULD NOT BE CONVERTED:', name, event.version)
        except Exception as e:
            print(e)
            print('Failed to convert events from "{}"!'.format(self.filename))
        else:
            self.write()
            if count: print('{} events successfully converted and added from "{}"!'.format(count, self.filename))


    command_pattern = re.compile(r'\s*(NEW|EDIT) EVENT (\w[\w.]+) ON ?(MESSAGE|REACT(?:ION)?) (.*?)\s*::\s*(.*)'.replace(' ', '\s+'), re.I | re.S )
    #                                  ^^^^^^^^         ^^^^^^^^       ^^^^^^^^^^^^^^^^^^^^^   ^^^          ^^

    async def parse_command(self, bot, string, message: Message):
        m = re.match(self.command_pattern, string)
        if m is None: return False

        channel = message.channel

        mode, name, what, trigger, script = m.groups()
        mode = mode.upper()
        EventType: type[OnMessage|OnReaction]  = {'M': OnMessage, 'R': OnReaction}[what[0].upper()]
        name = normalize_name(name)

        ## Check for naming conflicts
        if name in self.events and mode == 'NEW':
            await channel.send('An event by that name already exists. Use EDIT instead of NEW, or choose a different name.')
            return True
        if name not in self.events and mode == 'EDIT':
            await channel.send('An event by that name does not exist yet. Use NEW instead of EDIT, or choose an existing name.')
            return True

        ## Statically analyse the script for parsing errors and warnings
        pipeline_with_origin = PipelineWithOrigin.from_string(script)
        errors = pipeline_with_origin.pipeline.parser_errors
        if errors.terminal:
            await channel.send('Failed to save event due to parsing errors:', embed=errors.embed())
            return True
        elif errors:
            await channel.send('Encountered warnings while parsing event:', embed=errors.embed())

        ## Edit or create the event
        try:
            if mode == 'EDIT':
                event = self.events[name]
                if not isinstance(event, EventType):
                    await channel.send(f'Event "{name}" cannot be edited to be a different type. Try deleting it first.')
                    return True
                event.update(script, trigger)
            else:
                event = self.events[name] = EventType(name, None, message.author, channel, script, trigger)
            self.write()

        except Exception as e:
            ## Failed to register event (e.g. OnMessage regex could not parse)
            await channel.send('Failed to {} event:\n\t{}: {}'.format('register' if mode=='NEW' else 'update', type(e).__name__, e))
            return True

        else:
            ## Mission complete
            msg = f'New event `{name}` registered.' if mode == 'NEW' else f'Event `{name}` updated.'
            view = EventView(bot, event, self, channel)
            view.set_message(await channel.send(msg, embed=event.embed(bot=bot, channel=channel), view=view))
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