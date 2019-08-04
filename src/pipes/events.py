import re
from discord import Embed
from utils.texttools import block_format

events = {}

class Event:
    def __init__(self, name, channel, script):
        self.name = name
        self.channels = [channel]
        self.script = script

    def update(self, script):
        self.script = script

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
        return message.channel in self.channels and self.pattern.search(message.content) is not None

    def __str__(self):
        return '**{}**: ON MESSAGE `{}`'.format(self.name, self.patternstr)

    def embed(self, ctx):
        desc = '{} in this channel'.format( 'Enabled' if ctx.channel in self.channels else 'Disabled' )
        embed = Embed(title='Event: ' + self.name, description=desc, color=0x7628cc)

        ## On message
        embed.add_field(name='On message', value='`%s`' % self.patternstr, inline=True)

        ### List of the current server's channels it's enabled in
        channels = [ ch.mention for ch in self.channels if ch in ctx.guild.text_channels]
        embed.add_field(name='Enabled channels', value=', '.join(channels) or 'None', inline=True)

        ## Script
        embed.add_field(name='Script', value=block_format(self.script), inline=False)

        return embed


event_pattern = re.compile(r'\s*(NEW|EDIT) EVENT (\w[\w.]+) ON MESSAGE (.*?)\s*::\s*(.*)'.replace(' ', '\s+'), re.I | re.S )
#                                ^^^^^^^^         ^^^^^^^^              ^^^          ^^

async def parse_event(string, channel):
    m = re.match(event_pattern, string)
    if m is None: return False

    mode, name, pattern, script = m.groups()
    mode = mode.upper()
    name = name.lower()

    if name in events and mode == 'NEW':
        await channel.send('An event by that name already exists. Use EDIT instead of NEW, or choose a different name.')
        return True

    if name not in events and mode == 'EDIT':
        await channel.send('An event by that name does not exist yet. Use NEW instead of EDIT, or choose an existing name.')
        return True

    try:
        if mode == 'EDIT':
            events[name].update(script, pattern)
        else:
            events[name] = OnMessage(name, channel, script, pattern)

    except Exception as e:
        await channel.send('Failed to {} event:\n\t{}: {}'.format( 'register' if mode=='NEW' else 'update', e.__class__.__name__, e))
        raise e

    else:
        await channel.send( ('New event "%s" registered.' if mode == 'NEW' else 'Event "%s" updated.') % name )
        return True