import re

class OnMessage:
    def __init__(self, pattern, channel, script):
        self.patternstr = pattern
        self.pattern = re.compile(pattern)
        self.channel = channel
        self.script = script

    def __str__(self):
        return 'on message ' + '`{}`'.format(self.patternstr) + ' **::** ' + '`{}`'.format(self.script[:40] + '...' if len(self.script) > 40 else self.script)

    def test(self, message):
        return message.channel == self.channel and self.pattern.search(message.content) is not None

async def parse_event(string, channel):
    try:
        # TODO: regex this lol
        condition, script = string.split('::', 1)
        _, name, args = condition.strip().split(' ', 2)
        args = args.strip()

        if name.upper() == 'MESSAGE':
            await channel.send('New event registered.')
            return OnMessage(args, channel, script)
        else:
            pass

    except Exception as e:
        await channel.send('Failed to register event:\n\t{}: {}'.format(e.__class__.__name__, e))
        raise e