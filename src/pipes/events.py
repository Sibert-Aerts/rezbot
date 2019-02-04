import re

class OnMessage:
    def __init__(self, pattern, channel, script):
        self.pattern = re.compile(pattern)
        self.channel = channel
        self.script = script

    def test(self, message):
        return message.channel == self.channel and self.pattern.search(message.content) is not None

def parse_event(string):
    condition, script = string.split('::', 1)
    _, name, args = condition.split(' ', 2)
    args = args.strip()
    print('ENCOUNTERED A CONDITION: ON "{}" WITH ARGS "{}"'.format(name, args))
    if name.lower() == 'message':
        return OnMessage(args, channel, script)