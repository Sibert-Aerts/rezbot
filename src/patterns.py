import sys
import asyncio
import datetime
import random
import re

import discord
from discord.ext import commands

import utils.util as util
import utils.texttools as texttools
from utils.rand import *
from utils.attack import Attack

'''
This file is a bit of a mess, but what happens here is that the bot will scan all messages
looking for certain patterns to react to.

e.g. when a message contains "hi bot" the bot will automatically respond with a greeting

There's currently no way to disable this feature for, say, a specific channel/server without touching code.
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
            async for log in self.bot.logs_from(message.channel, limit=2):
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
                print('Recognised pattern \"{0}\".'.format(
                    pattern['function'].__name__))
                await pattern['function'](self, message)

        if matches(self.robotRegex, text):
            print('I may have been addressed: "{0}".'.format(text))
            for pattern in self.addressedPaterns:
                if matches(pattern['addressPattern'], text):
                    print('Reacting.')
                    await pattern['function'](self, message)
                    return

        if await self.implicitAddress(message):
            for pattern in self.addressedPaterns:
                if matches(pattern['pattern'], text):
                    print('I\'ve been implicitly addressed, reacting.')
                    await pattern['function'](self, message)
                    return

    async def reply(self, message, replyText):
        msg = await self.bot.send_message(message.channel, replyText)

    async def react(self, message, emote):
        await self.bot.add_reaction(message, emote)

    async def current_year(self, message):
        await self.reply(message, '`The current year is {0}.`'.format(datetime.datetime.now().year))


    # TODO: Pull all this stuff up to utils.attack
    odds = None

    def compile_odds(self):
        if self.odds != None:
            return

        self.odds = Odds([
            ('shoot', 50),
            ('noBullets', 10),
            ('knife', 10),
            ('tool', 10),
            ('punch', 10),
            ('hero', 10),
            ('time', 5),

            ('love', 10),
            ('shake', 10),
            
            ('kiss', 10),
            ('teleport', 10),
        ])

    weaponRegex = '([' + Attack.leftWeapons + Attack.rightWeapons + '])'
    corpses = [':skull_crossbones:', ':skull:', ':ghost:', ':cross:', ':coffin:']

    async def attack(self, message):
        '''This function is called when the bot recognises an "emoji fight" in a message.'''

        s = re.search('[^\\s]+\\s*' + self.weaponRegex + '.*', message.content)
        if s == None:
            print('Couldn\'t find victim...? "{0}"'.format(message.content))
            return
        s = s.group(0)
        l, w, r = re.split(self.weaponRegex, s, maxsplit=1)[:3]

        l = l.lstrip().rstrip()
        r = r.lstrip().rstrip()
        
        attack = Attack(l, w, r)
        
        # Don't uncomment this, linux doesn't like printing emoji
        # print('left: "%s"\t weapon: "%s"\t right: "%s"' % (attack.left, attack.weapon, attack.right))
        
        def corpse():
            return choose(self.corpses)
            
        if attack.attacker() == "":
            # Someone's attacking themselves
            if random.random() < 0.5:
                await self.reply(message, '`don\'t do it.`')
            else:
                await self.reply(message, '`do it.`')

        else:
            # Someone's attacking someone else
            async def post(x):
                await self.reply(message, x)

            self.compile_odds()

            # Loop until the fight ends somehow
            rolls = 0

            while True:
                self.odds.roll()
                rolls += 1

                if self.odds.test('shoot'):
                    await post(attack.attacking())
                    r = random.random()

                    if r < 0.3:
                        await post(attack.status_quo())
                        shrieks = ['`huh?!`', '`what?!`', '`nani?!`', '`...huh?!`', '`w-what?!`']
                        await post(choose(shrieks))

                        if r < 0.2:
                            continue

                        else:
                            disbeliefs = [
                                '`h-he\'s not even scratched !!`', 
                                '`t-this thing ain\'t human!`', 
                                '`i-it\'s invincible !`'
                            ]
                            await post(choose(disbeliefs))
                            break
                            
                    elif r < 0.7:
                        attack.target(corpse())
                        await post(attack.status_quo())
                    break

                elif self.odds.test('noBullets'):
                    if rolls == 1 or attack.weapon != '🔫':
                        continue
                    await post(attack.status_quo())
                    await post('`*click* *click* *click*`')
                    await post('`... out of bullets !!`')
                    break

                elif self.odds.test('knife'):
                    if not attack.leftFacing:
                        continue
                    oldWeapon = attack.weapon
                    attack.weapon = choose('🔪🗡')
                    await post(attack.status_quo())

                    acts = ['unsheathes', 'pulls out', 'reveals', 'whips out']
                    knives = ['katana', 'knife', 'kunai', 'dagger']
                    await post(texttools.bot_format('*' + choose(acts) + ' ' + choose(knives) + '*'))

                    await post(attack.attacking())
                    
                    quips = [
                        '`it was knife to know you.`',
                        '`now THIS is a knife.`',
                        '`I hope you got my point.`',
                    ]
                    if oldWeapon == '🔫': quips += ['`don\'t bring a gun to a knife fight.`']

                    if chance(0.5):
                        await post(choose(quips))
                    break

                elif self.odds.test('tool'):
                    if attack.leftFacing:
                        continue
                    attack.weapon = choose('🔨⛏')
                    await post(attack.status_quo())
                    await post(attack.attacking())
                    
                    quips = [
                        '`don\'t underestimate a craftsman.`',
                    ]
                    if attack.weapon == '🔨': 
                        quips += ['`hammer time!`', '`get hammered.`']
                    elif attack.weapon == '⛏': 
                        quips += ['`i learned this from mine craft.`']
                    
                    await post(choose(quips))
                    break

                elif self.odds.test('punch'):
                    attack.weapon = '🤜' if attack.leftFacing else '🤛'
                    await post(attack.attacking())
                    await post('`POW!`')
                    if chance(0.5):
                        await post(attack.left + (':point_left:' if attack.leftFacing else ':point_right:') + attack.right)
                        await post('`you are already dead.`')
                    attack.target(corpse())
                    await post(attack.no_weapon())
                    break

                elif self.odds.test('hero'):
                    if attack.weapon != '🔫':
                        continue
                    await post(attack.left + '          ' + attack.right + ':gun:')
                    await post('`I\'m fed up with this world.`')
                    r = random.random()
                    if r <= 1.0:
                        await post(attack.left + '          ' + ':boom::gun:')
                    break

                elif self.odds.test('love'):
                    await post(attack.left + ':bouquet:' + attack.right)
                    await post('`must we fight?`')
                    await post(attack.left + ':heart:' + attack.right)
                    await post('`love conquers all.`')
                    break

                elif self.odds.test('shake'):
                    await post(attack.no_weapon())
                    await post('`I\'m sorry. I can\'t do it.`')
                    await post(attack.left + ':handshake:' + attack.right)
                    await post('`let\'s put this behind us, pal.`')
                    break

                elif self.odds.test('time'):
                    if not attack.leftFacing:
                        continue
                    await post(attack.status_quo() + ':cyclone::cyclone:')
                    await post('`~bzoom~`')
                    await post(attack.status_quo() + attack.weapon + attack.left)
                    await post('`w-what?!`')
                    await post(attack.left + attack.weapon + ':boom:' + attack.weapon + attack.left)
                    await post(attack.left + attack.weapon + '                    ' + attack.left)
                    await post('`quick, take his weapon and my time machine.`')
                    await post(':cyclone::cyclone:' + '                    ' + attack.left)
                    await post('`~bzoom~`')
                    break

                elif self.odds.test('teleport'):
                    if rolls > 3:
                        continue
                    oldWeapon = attack.weapon
                    if attack.leftFacing:
                        await post(':dash:' + oldWeapon + attack.right)
                        await post('`*teleports behind you*`')
                        (attack.left, attack.right) = (attack.right, attack.left)
                        attack.weapon = choose(Attack.leftWeapons)
                        await post(oldWeapon + attack.left + attack.weapon + attack.right)
                    else:
                        await post(attack.left + oldWeapon + ':dash:')
                        await post('`*teleports behind you*`')
                        (attack.left, attack.right) = (attack.right, attack.left)
                        attack.weapon = choose(Attack.rightWeapons)
                        await post(attack.left + attack.weapon + attack.right + oldWeapon)

                    if chance(0.5):
                        await post('`psh, nothing personnel.`')

                    continue

                elif self.odds.test('kiss'):
                    if rolls > 4:
                        continue
                    kissing_faces = [':kissing_heart:', ':kissing:', ':kissing_smiling_eyes:', ':kissing_closed_eyes:']

                    oldTarget = attack.target()
                    attack.target(choose(kissing_faces))
                    await post(attack.left + ':kiss:' + attack.right)
                    await post('`mwah!`')
                    attack.target(oldTarget)

                    reaction_faces = [':blush:', ':flushed:', ':wink:', ':relieved:']
                    oldAttacker = attack.attacker()
                    attack.attacker(choose(reaction_faces))
                    await post(attack.status_quo())
                    if chance(0.5):
                        attack.attacker(oldAttacker)
                    continue

    def make_reply(reply):
        return lambda self, message: self.reply(message, reply)

    def make_react(emote, fallbackEmote='😊'):
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

    happyDayText = 'pls rember that wen u feel scare or frigten\nnever forget ttimes wen u feeled happy\n\nwen day is dark alway rember happy day'

    # Patterns that are always* executed
    generalPatterns = [
        #{ 'pattern' : (':yaranaika:'  , re.I),
        #  'function' : make_react(':yaranaika:245987292513173505') },
        #{ 'pattern' : ('\\bxd+\\b'  , re.I),
        #  'function' : make_react('😫') },
        {'pattern': ('(✋|up[-\\s]top|high[-\\s]five)', re.I),
         'function': make_react('🤚')},
        {'pattern': ('[^\\s]+\\s*' + weaponRegex + '.*', re.I),
         'function': attack},
        {'pattern': ('current ?year', re.I),
         'function': current_year},
        #{ 'pattern' : (':pe:', re.I),
        #  'function' : make_reply('`{0}.`'.format(happyDayText)) },
        {'pattern': ('^:pe:$', re.I),
         'function': make_react(':pe:245959018210656256')},
    ]

    # Patterns only applied when the bot recognises it's directly or implicitly addressed
    addressedPaterns = [
        {'pattern': ('\\b(hi(ya)?|h[aeu][lw]+o|hey|hoi|henlo)', re.I),
         'function': make_reply('`hello.`')},
        {'pattern': ('\\bthanks?( (yo)?u)?', re.I),
         'function': make_react(':yaranaika:245987292513173505', '🙂')},
        {'pattern': ('\\b(goo?d|nice|beautiful|amazing)( ?(j[oa]b|work))?', re.I), 
         'function': make_react(':yaranaika:245987292513173505', '🙂')},
        {'pattern': ('\\bi l[ou]ve? ((yo)?u|th(e|is))', re.I),
         'function': make_react(':yaranaika:245987292513173505', '🙂')},

        {'pattern': ('\\b(bad|stupid|dumb)', re.I),
         'function': make_react(':angery:245586525457350667', '😠')},
        {'pattern': ('\\bi h(ate?|8) ?((yo)?u|th(e|is))?', re.I),
         'function': make_react(':angery:245586525457350667', '😠')},
        {'pattern': ('\\bf[aou](g|c?k) ?((yu?o)?u|th(e|is)|off?)', re.I),
         'function': make_react(':angery:245586525457350667', '😠')},
    ]
