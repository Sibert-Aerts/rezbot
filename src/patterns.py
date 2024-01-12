import datetime
import random
import re

import discord

from utils.rand import chance, choose, RandomBranch
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


    # TODO: Pull all this stuff up to utils.emojifight
    odds = RandomBranch([
        ('attack',      50),
        ('noBullets',   10),
        ('knife',       10),
        ('tool',        10),
        ('punch',       10),
        ('hero',        10),
        ('time',        5),

        ('love',        10),
        ('shake',       10),

        ('kiss',        10),
        ('teleport',    10),
    ])

    fightRegex = re.compile( r'(\S*)\s*' + EmojiFight.weapons_regex.pattern + r'\s*(\S*)' )

    async def attack(self, message):
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

        async def post(*args):
            await message.channel.send(''.join(args))
        async def postRandom(*args):
            await message.channel.send(random.choice(args))

        if fight.weapon in EmojiFight.weapons_dual:
            ## Start the battle by having one side draw a random weapon
            fight.weapon = choose(EmojiFight.weapons_left) if chance(0.5) else choose(EmojiFight.weapons_right)
            await post(fight.status_quo())
            if chance(0.5):
                await postRandom('`en guarde!`', '`have at you!`', '`on your guard!`')

        # Loop until the fight ends somehow
        rollCount = 0
        while True:
            self.odds.roll()
            rollCount += 1

            if self.odds.test('attack'):
                await post(fight.attacking())
                r = random.random()

                if r < 0.3: # 30% chance the attack is unsuccessful
                    await post(fight.status_quo())
                    await postRandom('`huh?!`', '`what?!`', '`nani?!`', '`...huh?!`', '`w-what?!`')

                    if r < 0.2: # after which a 2/3 chance the fight continues
                        continue
                    else: # or a 1/3 chance the attacker gives up
                        await postRandom(
                            '`h-he\'s not even scratched !!`',
                            '`t-this thing ain\'t human!`',
                            '`i-it\'s invincible !`'
                        )
                        break

                elif r < 0.7: # 40% chance they're dead and their corpse is shown
                    fight.kill_target()
                    await post(fight.status_quo())

                # 30% chance they're dead and their corpse isn't shown
                break

            elif self.odds.test('noBullets'):
                if rollCount == 1 or fight.weapon != '🔫':
                    continue
                await post(fight.status_quo())
                await post('`*click* *click* *click*`')
                await post('`... out of bullets !!`')
                # Out of bullets ends the fight
                break

            elif self.odds.test('knife'):
                oldWeapon = fight.weapon
                fight.weapon = '🔪' if fight.facing_left else '🗡️'
                await post(fight.status_quo())

                acts = ['unsheathes', 'pulls out', 'reveals', 'whips out']
                knives = ['katana', 'knife', 'kunai', 'dagger']
                await post('`*', choose(acts), ' ', choose(knives), '*`')

                await post(fight.attacking())

                quips = [
                    '`it was knife knowing you.`',
                    '`now THIS is a knife.`',
                    '`I hope you got my point.`',
                ]
                if oldWeapon == '🔫': quips += ['`don\'t bring a gun to a knife fight.`']

                if chance(0.5):
                    await post(choose(quips))
                break

            elif self.odds.test('tool'):
                if fight.facing_left:
                    continue
                fight.weapon = choose('🔨⛏🪓🪚')
                await post(fight.status_quo())
                await post(fight.attacking())

                quips = [
                    '`don\'t underestimate a craftsman.`',
                ]
                if fight.weapon == '🔨':
                    quips += ['`hammer time!`', '`get hammered.`']
                elif fight.weapon == '⛏':
                    quips += ['`get minecrafted.`', 'get fortnited.', '(fortnite default dance)']
                elif fight.weapon == '🪓':
                    quips += ['get lumberjacked.', 'can I "axe" you a question?', 'hey Paul!']
                elif fight.weapon == '🪚':
                    quips += ['I bet you didn\'t saw that one coming.']

                await post(choose(quips))
                break

            elif self.odds.test('punch'):
                fight.weapon = '🤜' if fight.facing_left else '🤛'
                await post(fight.attacking())
                await post('`POW!`')
                if chance(0.5):
                    await post(fight.left, (':point_left:' if fight.facing_left else ':point_right:'), fight.right)
                    await post('`you are already dead.`')
                fight.kill_target()
                await post(fight.no_weapon())
                break

            elif self.odds.test('hero'):
                if fight.weapon != '🔫':
                    continue
                await post(fight.left, '   ', fight.right, ':gun:')
                await postRandom('`I\'m fed up with this world.`', '`I can\'t take it anymore.`', '`goodbye cruel world.`')
                await post(fight.left, '   ', ':boom::gun:')
                break

            elif self.odds.test('love'):
                await post(fight.left, ':bouquet:', fight.right)
                await postRandom('`must we fight?`', '`why do we fight?`')
                await post(fight.left, ':heart:', fight.right)
                await postRandom('`love conquers all.`', '`love trumps hate.`', '`we will hide our feelings no longer.`')
                break

            elif self.odds.test('shake'):
                await post(fight.no_weapon())
                await postRandom('`I\'m sorry. I can\'t do it.`', '`I\'m sorry, I can\'t do this.`', '`no, this is wrong.`')
                await post(fight.left, ':handshake:', fight.right)
                await postRandom('`let\'s put this behind us, pal.`', '`I hope you can forgive me.`', '`we can find a peaceful solution to our disagreement.`')
                break

            elif self.odds.test('time'):
                if not fight.facing_left:
                    continue
                await post(fight.status_quo(), ':cyclone::cyclone:')
                await post('`~bzoom~`')
                await post(fight.status_quo(), fight.weapon, fight.left)
                await post('`w-what?!`')
                await post(fight.left, fight.weapon, ':boom:', fight.weapon, fight.left)
                await post(fight.left, fight.weapon, '      ', fight.left)
                await post('`quick, take their weapon and my time machine.`')
                await post(':cyclone::cyclone:', '      ', fight.left)
                await post('`~bzoom~`')
                break

            elif self.odds.test('teleport'):
                if rollCount > 3: continue
                oldWeapon = fight.weapon
                kawarimi = chance(0.5)
                if kawarimi: await post(fight.attacking())

                if fight.facing_left:
                    await post((':wood:' if kawarimi else ':dash:'), oldWeapon, fight.right)
                    if kawarimi: await post('`Kawarimi no jutsu!`')
                    else: await post('`*teleports behind you*`')
                    (fight.left, fight.right) = (fight.right, fight.left)
                    fight.weapon = choose(EmojiFight.weapons_left)
                    await post(oldWeapon, fight.left, fight.weapon, fight.right)
                else:
                    await post(fight.left, oldWeapon, (':wood:' if kawarimi else ':dash:'))
                    if kawarimi: await post('`Kawarimi no jutsu!`')
                    else: await post('`*teleports behind you*`')
                    (fight.left, fight.right) = (fight.right, fight.left)
                    fight.weapon = choose(EmojiFight.weapons_right)
                    await post(fight.left, fight.weapon, fight.right, oldWeapon)

                if chance(0.5):
                    await postRandom('`nothing personnel.`', '`nothing personal, kid.`', '`psh, nothing personal.`')

                continue

            elif self.odds.test('kiss'):
                if rollCount > 4:
                    continue
                kissing_faces = [':kissing_heart:', ':kissing:', ':kissing_smiling_eyes:', ':kissing_closed_eyes:']

                oldTarget = fight.target
                fight.target = choose(kissing_faces)
                await post(fight.left, ':kiss:', fight.right)
                await post('`mwah!`')
                fight.target = oldTarget

                reaction_faces = [':blush:', ':flushed:', ':wink:', ':relieved:']
                oldAttacker = fight.attacker
                fight.attacker = choose(reaction_faces)
                await post(fight.status_quo())
                if chance(0.5):
                    fight.attacker = oldAttacker
                continue

            else:
                print(f'ERROR: encountered un-implemented branch: "{self.odds.get()}"')


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
