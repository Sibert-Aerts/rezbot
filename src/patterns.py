import datetime
import re

import discord

from utils.rand import chance
from utils.emojifight import EmojiFight

'''
This file is ancient.

This file is a bit of a mess, but what happens here is that the bot will scan all messages
looking for certain patterns to react to.

e.g. when a message contains "hi bot" the bot will automatically respond with a greeting

It can be disabled in specific channels or severs by editing config.ini.
'''


def matches(pattern, text):
    return pattern.search(text) != None

class Patterns:
    def __init__(self, bot):
        self.bot = bot
        self.compile_patterns()

    def compile_patterns(self):
        # Compile the patterns into regex objects
        # This is called once when the bot boots up, and is just an optimization
        for p in self.generalPatterns:
            p['pattern'] = re.compile(p['pattern'][0], p['pattern'][1])

        for p in self.addressedPaterns:
            p['addressPattern'] = re.compile(
                self.addresses_bot(p['pattern'][0]), p['pattern'][1])
            p['pattern'] = re.compile(p['pattern'][0] + '\\b', p['pattern'][1])

    async def implicitAddress(self, message):
        # Check if the bot may have been addressed implicitly:
        # i.e. if the previous message (before the one we're testing) was posted by the bot
        try:
            i = 0
            async for log in message.channel.history(limit=2):
                if i == 1:
                    return log.author.id == self.bot.user.id
                i += 1
        except IndexError:
            return False

    async def process_patterns(self, message):
        # Run through all the patterns and apply their respective functions when needed.

        text = message.content

        for pattern in self.generalPatterns:
            if matches(pattern['pattern'], text):
                name = pattern['function'].__name__
                print(f'Recognised pattern "{name}".')
                await pattern['function'](self, message)

        if matches(self.robotRegex, text):
            print(f'I may have been addressed: "{text}".')
            for pattern in self.addressedPaterns:
                if matches(pattern['addressPattern'], text):
                    print('Reacting.')
                    await pattern['function'](self, message)
                    return

        elif await self.implicitAddress(message):
            for pattern in self.addressedPaterns:
                if matches(pattern['pattern'], text):
                    print('I\'ve been implicitly addressed, reacting.')
                    await pattern['function'](self, message)
                    return

    async def reply(self, message, text):
        await message.channel.send(text)

    async def react(self, message, emote):
        await message.add_reaction(emote)

    async def current_year(self, message):
        await message.channel.send('`The current year is {0}.`'.format(datetime.datetime.now().year))

    fightRegex = re.compile(r'(\S*)\s*' + EmojiFight.weapons_regex.pattern + r'\s*(\S*)')

    async def attack(self, message: discord.Message):
        '''This function is called when the bot recognises an "emoji fight" in a message.'''
        match = re.search(Patterns.fightRegex, message.content)
        l, w, r = match.groups()
        fight = EmojiFight(l, w, r)
        # print(f'({fight.attacker}) attacking ({fight.target}) with ({fight.weapon})')

        if not fight.target:
            ## No target, no fight
            return
        elif not fight.attacker:
            ## No attacker: interpret it as the target is threatening themselves
            await message.channel.send('`don\'t do it.`' if chance(0.5) else '`do it.`')
            return

        ## Someone's attacking someone else: Fight!
        fight.perform_fight()
        for line in fight.pop_emit():
            await message.channel.send(line)

    def do_reply(text):
        return lambda self, message: message.channel.send(text)

    def do_react(emote, fallbackEmote='😊'):
        async def try_react(self, message):
            try:
                await self.react(message, emote)
            except discord.errors.HTTPException:
                await self.react(message, fallbackEmote)

        return try_react

    robotRegexRaw = '\\b(m(iste)?r\\.? ?)?(ro|rez)?bot\\b'
    robotRegex = re.compile(robotRegexRaw, re.I)

    def addresses_bot(self, pattern):
        return '(' + self.robotRegexRaw + '\s*[,.]* ' + pattern + '|' + pattern + "[,.]* ((yo)?u )?([^\s]+ )?" + self.robotRegexRaw + ')'

    # Patterns that are always* executed
    generalPatterns = [
        {'pattern': ('(✋|up[-\\s]top|high[-\\s]five)', re.I),
         'function': do_react('🤚')},
        {'pattern': (fightRegex.pattern, re.I),
         'function': attack},
        {'pattern': ('current ?year', re.I),
         'function': current_year},
        {'pattern': ('\\byou\'?re? a big bot\\b', re.I),
         'function': do_reply('for you.')},
        {'pattern': ('^<:pe:245959018210656256>$', re.I),
         'function': do_react(':pe:245959018210656256')},
    ]

    # Patterns only applied when the bot recognises it's directly or implicitly addressed
    addressedPaterns = [
        {'pattern': ('\\b(hi(ya)?|h[aeu][lw]+o|hey|hoi|henlo)', re.I),
         'function': do_reply('`hello.`')},
        {'pattern': ('\\bthanks?( (yo)?u)?', re.I),
         'function': do_react('<:rezbot:1128733363860144229>', '🙂')},
        {'pattern': ('\\b(goo?d|nice|beautiful|amazing)( ?(j[oa]b|work))?', re.I),
         'function': do_react('<:rezbot:1128733363860144229>', '🙂')},
        {'pattern': ('\\bi l[ou]ve? ((yo)?u|th(e|is))', re.I),
         'function': do_react('<:rezbot:1128733363860144229>', '🙂')},

        {'pattern': ('\\b(bad|stupid|dumb)', re.I),
         'function': do_react(':angery:382295067299151893', '😠')},
        {'pattern': ('\\bi h(ate?|8) ?((yo)?u|th(e|is))?', re.I),
         'function': do_react(':angery:382295067299151893', '😠')},
        {'pattern': ('\\bf[aou](g|c?k) ?((yu?o)?u|th(e|is)|off?)', re.I),
         'function': do_react(':angery:382295067299151893', '😠')},
    ]
