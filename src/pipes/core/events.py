import re
import os
import json
import traceback
from shutil import copyfile
from discord import Embed, Guild, TextChannel, Message, Client

from utils.util import normalize_name
from utils.texttools import block_format


def DIR(filename=''):
    return os.path.join(os.path.dirname(__file__), '..', 'macros', filename)


###############################################################
#                             Event                           #
###############################################################

class Event:
    CURRENT_VERSION = 6

    targets_current_message = False

    def __init__(self, *, name: str, desc: str='', author_id: int, channels: list[int]=None, script: str):
        self.name: str = name
        self.desc: str = desc
        self.author_id: int = author_id
        self.channels: list[int] = channels or []
        self.script: str = script

    @staticmethod
    def from_trigger_str(**kwargs) -> 'Event':
        raise NotImplementedError()

    # ================ Usage ================

    def update(self, script):
        self.script = script

    def test(self, channel: TextChannel):
        return self.is_enabled(channel)

    def is_enabled(self, channel: TextChannel):
        # TODO: distinguish threads/channels?
        return channel.id in self.channels

    def disable_in_guild(self, guild: Guild):
        # Throw out all Channels belonging to the given guild
        guild_channels = [c.id for c in guild.channels]
        self.channels = [c for c in self.channels if not c in guild_channels]

    def embed(self, *, bot: Client=None, channel: TextChannel=None, **kwargs):
        ''' Make a Discord Embed. '''
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

    def get_static_errors(self):
        return ExecutableScript.from_string(self.script).get_static_errors()

    # ================ Serialization ================

    def serialize(self):
        return {
            '_version': Event.CURRENT_VERSION,
            '_type': type(self).__name__,
            'name': self.name,
            'desc': self.desc,
            'author_id': self.author_id,
            'channels': self.channels,
            'script': self.script,
        }

    @classmethod
    def deserialize(cls, values):
        # Delegate to one of the sub-classes' deserialize method
        type_map = {
            'OnMessage': OnMessage,
            'OnReaction': OnReaction,
            'OnYell': OnInvoke,
            'OnInvoke': OnInvoke,
        }
        EventType = type_map[values.pop('_type')]
        return EventType.deserialize(values)


class OnMessage(Event):
    patternstr: str
    pattern: re.Pattern

    def __init__(self, *, pattern: str, **kwargs):
        super().__init__(**kwargs)
        self.set_trigger(pattern)

    @staticmethod
    def from_trigger_str(*, trigger: str, **kwargs):
        return OnMessage(pattern=trigger, **kwargs)

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
        if version in (4, 5, 6):
            return OnMessage(**values)
        raise NotImplementedError()


class OnReaction(Event):
    emotes: list[str]

    targets_current_message = False

    def __init__(self, *, emotes: list[str]=None, **kwargs):
        super().__init__(**kwargs)
        self.emotes = emotes or []

    @staticmethod
    def from_trigger_str(*, trigger: str, **kwargs):
        event = OnReaction(**kwargs)
        event.set_trigger(trigger)
        return event

    def update(self, script: str, emotes: str):
        super().update(script)
        self.set_trigger(emotes)

    def get_trigger_str(self):
        return ','.join(self.emotes)

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
            'emotes': self.emotes,
        })
        return res

    @classmethod
    def deserialize(cls, values):
        version = values.pop('_version')
        if version == 4:
            emotes = values.pop('emotes')
            return OnReaction.from_trigger_str(trigger=emotes, **values)
        if version in (5, 6):
            return OnReaction(**values)
        raise NotImplementedError()


class OnInvoke(Event):
    command: str

    def __init__(self, *, command: str, **kwargs):
        super().__init__(**kwargs)
        self.set_trigger(command)

    @staticmethod
    def from_trigger_str(*, trigger: str, **kwargs):
        return OnInvoke(command=trigger, **kwargs)

    def update(self, script: str, command: str):
        super().update(script)
        self.set_trigger(command)

    def get_trigger_str(self):
        return self.command

    def set_trigger(self, command: str):
        self.command = command.lower()

    def test(self, channel: TextChannel, command: str):
        '''Test whether or not a given reaction-addition should trigger this Event.'''
        return super().test(channel) and command.lower() == self.command

    # ================ Display ================

    def __str__(self):
        return f'**{self.name}**: ON INVOKE `{self.command}`'

    def embed(self, **kwargs):
        embed = super().embed(**kwargs)
        return embed.insert_field_at(0, name='On Invoke', value=self.command, inline=True)

    # ================ Serialization ================

    def serialize(self):
        res = super().serialize()
        res.update({
            'command': self.command,
        })
        return res

    @classmethod
    def deserialize(cls, values):
        version = values.pop('_version')
        if version in (4, 5):
            values['command'] = values.pop('tone')
            return OnInvoke(**values)
        if version == 6:
            return OnInvoke(**values)
        raise NotImplementedError()


###############################################################
#                             Events                          #
###############################################################

class Events:
    '''Dict-like wrapper for loading/holding/saving Events, mostly copy-pasted from the one in macros.py'''
    events: dict[str, Event]
    on_message_events: list[OnMessage]
    on_reaction_events: list[OnReaction]
    on_invoke_events: list[OnInvoke]
    on_invoke_commands: set[str]

    def __init__(self, DIR, filename):
        self.events = {}
        self.DIR = DIR
        self.json_filename = filename + '.json'
        self.read_events_from_file()
        self.refresh_indexes()

    # ================ Reading/writing ================

    def read_events_from_file(self):
        try:
            # Ensure the events directory exists
            if not os.path.exists(DIR()): os.mkdir(DIR())

            # Deserialize Events from JSON data
            file_used = self.json_filename
            with open(DIR(self.json_filename), 'r+') as file:
                data = json.load(file)
                upgrade_needed = any(d['_version'] != Event.CURRENT_VERSION for d in data)
                if upgrade_needed:
                    new_filename = self.json_filename + '.v{}_backup'.format(Event.CURRENT_VERSION-1)
                    print(f'Deserializing Events that require upgrading, backing up pre-upgraded data in {new_filename}')
                    copyfile(self.DIR(self.json_filename), self.DIR(new_filename))
                self.deserialize(data)

            print(f'{len(self.events)} events loaded from "{file_used}"!')

        except Exception as e:
            print(f'Failed to load events from "{file_used}"!')
            print(traceback.format_exc())
            print()

    def refresh_indexes(self):
        self.on_message_events = []
        self.on_reaction_events = []
        self.on_invoke_events = []
        self.on_invoke_commands = set()
        for event in self.events.values():
            if isinstance(event, OnMessage):
                self.on_message_events.append(event)
            elif isinstance(event, OnReaction):
                self.on_reaction_events.append(event)
            elif isinstance(event, OnInvoke):
                self.on_invoke_events.append(event)
                self.on_invoke_commands.add(event.command)

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

    command_pattern = re.compile(r'\s*(NEW|EDIT) EVENT (\w[\w.]+) ON ?(MESSAGE|REACT(?:ION)?|INVOKE) (.*?)\s*::\s*(.*)'.replace(' ', '\s+'), re.I | re.S )
    #                                  ^^^^^^^^         ^^^^^^^^       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^   ^^^          ^^

    async def parse_command(self, bot, string, message: Message):
        m = re.match(self.command_pattern, string)
        if m is None: return False

        channel = message.channel

        mode, name, what, trigger, script = m.groups()
        mode = mode.upper()
        EventType: type[OnMessage|OnReaction|OnInvoke] = {'M': OnMessage, 'R': OnReaction, 'I': OnInvoke}[what[0].upper()]
        name = normalize_name(name)

        ## Check for naming conflicts
        if name in self.events and mode == 'NEW':
            await channel.send('An event by that name already exists. Use EDIT instead of NEW, or choose a different name.')
            return True
        if name not in self.events and mode == 'EDIT':
            await channel.send('An event by that name does not exist yet. Use NEW instead of EDIT, or choose an existing name.')
            return True

        ## Statically analyse the script for parsing errors and warnings
        errors = ExecutableScript.from_string(script).get_static_errors()
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
                event = self[name] = EventType.from_trigger_str(name=name, author_id=message.author.id, channels=[channel.id], script=script, trigger=trigger)

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


ALL_EVENTS = Events(DIR, 'events')
'The canonical object managing all Event instances, responsible for serialising and deserialising them.'


# Circular dependency
from pipes.views.event_views import EventView
from .executable_script import ExecutableScript