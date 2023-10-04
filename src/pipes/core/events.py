import re
import os
import json
import traceback
import pickle
from shutil import copyfile
from discord import Embed, Guild, TextChannel, Message, Client

from utils.util import normalize_name
from utils.texttools import block_format
from .pipeline_with_origin import PipelineWithOrigin


def DIR(filename=''):
    return os.path.join(os.path.dirname(__file__), '..', 'macros', filename)


###############################################################
#                             Event                           #
###############################################################

class Event:
    def __init__(self, name, desc, author_id, channels, script):
        self.version = 4
        self.name: str = name
        self.desc: str = desc
        self.author_id: int = author_id
        self.channels: list[int] = channels
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

    # ================ Serialization ================

    def serialize(self):
        return {
            '_version': 4,
            '_type': type(self).__name__,
            'name': self.name,
            'desc': self.desc,
            'author_id': self.author_id,
            'channels': self.channels,
            'script': self.script
        }
    
    @classmethod
    def deserialize(cls, values):
        # Delegate to one of the sub-classes' deserialize method
        type_map = {
            'OnMessage': OnMessage,
            'OnReaction': OnReaction,
            'OnYell': OnYell,
        }
        EventType = type_map[values.pop('_type')]
        return EventType.deserialize(values)


class OnMessage(Event):
    patternstr: str
    pattern: re.Pattern

    def __init__(self, name, desc, author_id, channels, script, pattern):
        super().__init__(name, desc, author_id, channels, script)
        self.set_trigger(pattern)

    def update(self, script: str, pattern: str):
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

    # ================ Display ================

    def __str__(self):
        return '**{}**: ON MESSAGE `{}`'.format(self.name, self.patternstr)

    def embed(self, **kwargs):
        embed = super().embed(**kwargs)
        return embed.insert_field_at(0, name='On message', value='`%s`' % self.patternstr, inline=True)

    # ================ Serialization ================

    def serialize(self):
        res = super().serialize()
        res.update({
            'pattern': self.patternstr,
        })
        return res

    @classmethod
    def deserialize(cls, values):
        version = values.pop('_version')
        if version == 4:
            return OnMessage(**values)
        raise NotImplementedError()


class OnReaction(Event):
    emotes: list[str]

    def __init__(self, name, desc, author_id, channels, script: str, emotes: str):
        super().__init__(name, desc, author_id, channels, script)
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

    # ================ Display ================

    def __str__(self):
        return '**{}**: ON REACTION `{}`'.format(self.name, ','.join(self.emotes))

    def embed(self, **kwargs):
        embed = super().embed(**kwargs)
        return embed.insert_field_at(0, name='On reaction', value=','.join(self.emotes), inline=True)

    # ================ Serialization ================

    def serialize(self):
        res = super().serialize()
        res.update({
            'emotes': self.get_trigger_str(),
        })
        return res

    @classmethod
    def deserialize(cls, values):
        version = values.pop('_version')
        if version == 4:
            return OnReaction(**values)
        raise NotImplementedError()


class OnYell(Event):
    tone: str

    def __init__(self, name, desc, author_id, channels, script: str, tone: str):
        super().__init__(name, desc, author_id, channels, script)
        self.set_trigger(tone)

    def update(self, script: str, tone: str):
        super().update(script)
        self.set_trigger(tone)

    def get_trigger_str(self):
        return self.tone

    def set_trigger(self, tone: str):
        self.tone = tone.lower()

    def test(self, channel, tone):
        '''Test whether or not a given reaction-addition should trigger this Event.'''
        return super().test(channel) and tone.lower() == self.tone

    # ================ Display ================

    def __str__(self):
        return f'**{self.name}**: ON YELL `{self.tone}`'

    def embed(self, **kwargs):
        embed = super().embed(**kwargs)
        return embed.insert_field_at(0, name='On yell', value=self.tone, inline=True)

    # ================ Serialization ================

    def serialize(self):
        res = super().serialize()
        res.update({
            'tone': self.tone,
        })
        return res

    @classmethod
    def deserialize(cls, values):
        version = values.pop('_version')
        if version == 4:
            return OnYell(**values)
        raise NotImplementedError()


###############################################################
#                             Events                          #
###############################################################

class Events:
    '''Dict-like wrapper for loading/holding/saving Events, mostly copy-pasted from the one in macros.py'''
    events: dict[str, Event]
    on_message_events: list[OnMessage]
    on_reaction_events: list[OnReaction]
    on_yell_events: list[OnYell]
    on_yell_tones: set[str]

    def __init__(self, DIR, filename):
        self.events = {}
        self.DIR = DIR
        self.pickle_filename = filename + '.p'
        self.json_filename = filename + '.json'
        self.read_events_from_file()
        self.refresh_indexes()

    # ================ Reading/writing ================

    def read_events_from_file(self):
        try:
            if not os.path.exists(DIR()): os.mkdir(DIR())

            if os.path.isfile(DIR(self.json_filename)):
                # Deserialize Events from JSON data
                file_used = self.json_filename
                with open(DIR(self.json_filename), 'r+') as file:
                    self.deserialize(json.load(file))
            else:
                # DEPRECATED/FALLBACK: Pickle file
                file_used = self.pickle_filename
                with open(DIR(self.pickle_filename), 'rb+') as file:
                    self.events = pickle.load(file)
                self.write()

            # self.attempt_version_upgrade()
            print(f'{len(self.events)} events loaded from "{file_used}"!')

        except Exception as e:
            print(f'Failed to load events from "{file_used}"!')
            print(traceback.format_exc())
            print()

    def refresh_indexes(self):
        self.on_message_events = []
        self.on_reaction_events = []
        self.on_yell_events = []
        self.on_yell_tones = set()
        for event in self.events.values():
            if isinstance(event, OnMessage):
                self.on_message_events.append(event)
            elif isinstance(event, OnReaction):
                self.on_reaction_events.append(event)
            elif isinstance(event, OnYell):
                self.on_yell_events.append(event)
                self.on_yell_tones.add(event.tone)

    def write(self):
        '''Write the list of events to a json file.'''
        self.refresh_indexes()
        with open(self.DIR(self.json_filename), 'w+') as file:
            json.dump(self.serialize(), file)

    # ================ Serialization ================

    def serialize(self):
        return [v.serialize() for v in self.events.values()]

    def deserialize(self, data):
        # NOTE: Deserializes in-place, does not create a new Events object.
        events = [Event.deserialize(d) for d in data]
        self.events = {event.name: event for event in events}

    # ================ Parse event create/edit command ================

    command_pattern = re.compile(r'\s*(NEW|EDIT) EVENT (\w[\w.]+) ON ?(MESSAGE|REACT(?:ION)?|YELL) (.*?)\s*::\s*(.*)'.replace(' ', '\s+'), re.I | re.S )
    #                                  ^^^^^^^^         ^^^^^^^^       ^^^^^^^^^^^^^^^^^^^^^^^^^^   ^^^          ^^

    async def parse_command(self, bot, string, message: Message):
        m = re.match(self.command_pattern, string)
        if m is None: return False

        channel = message.channel

        mode, name, what, trigger, script = m.groups()
        mode = mode.upper()
        EventType: type[OnMessage|OnReaction|OnYell] = {'M': OnMessage, 'R': OnReaction, 'Y': OnYell}[what[0].upper()]
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
                self.write()
            else:
                event = self[name] = EventType(name, None, message.author.id, [channel.id], script, trigger)

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

    # ================ Interface ================

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


events = Events(DIR, 'events')
'The canonical object managing all Event instances, responsible for serialising and deserialising them.'


# Circular dependency
from pipes.views import EventView