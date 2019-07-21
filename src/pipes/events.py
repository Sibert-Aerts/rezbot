import re
from discord import Embed
from utils.texttools import block_format

events = {}

class Event:
    def __init__(self, name, channel, script):
        self.name = name
        self.channels = [channel]
        self.script = script

class OnMessage(Event):
    def __init__(self, name, channel, script, pattern):
        super().__init__(name, channel, script)
        self.patternstr = pattern
        self.pattern = re.compile(pattern)

    def __str__(self):
        return '**{}**: ON MESSAGE `{}`'.format(self.name, self.patternstr)

    def embed(self, ctx):
        desc = '{} in this channel'.format( 'Active' if ctx.channel in self.channels else 'Not active' )
        embed = Embed(title='Event: ' + self.name, description=desc, color=0x592bff)

        ## On message
        embed.add_field(name='On message', value='`%s`' % self.patternstr, inline=True)

        ### List of the current server's channels it's active in
        channels = [ '#'+ch.name for ch in self.channels if ch in ctx.guild.text_channels]
        embed.add_field(name='Active channels', value=', '.join(channels) or 'None', inline=True)

        ## Script
        embed.add_field(name='Script', value=block_format(self.script), inline=False)

        return embed

    def test(self, message):
        return message.channel in self.channels and self.pattern.search(message.content) is not None


event_pattern = re.compile(r'\s*(NEW|EDIT) EVENT (\w+) ON MESSAGE (.*?)\s*::\s*(.*)'.replace(' ', '\s+'), re.I)
#                                ^^^^^^^^         ^^^              ^^^          ^^

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
        events[name] = OnMessage(name, channel, script, pattern)

    except Exception as e:
        await channel.send('Failed to register event:\n\t{}: {}'.format(e.__class__.__name__, e))
        raise e

    finally:
        await channel.send('New event registered.' if mode == 'NEW' else 'Event updated.')
        return True