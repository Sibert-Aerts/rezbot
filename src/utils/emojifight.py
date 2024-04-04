from typing import Literal
from numpy.random import choice
import random
import re

import discord

from .rand import chance


DEFAULT_ODDS = [
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
]


class EmojiOutput:
    lines: list[tuple[bool, str]]
    def __init__(self):
        self.lines = []
    def add_text(self, text: str):
        self.lines.append((False, text))
    def add_emoji(self, emoji: str):
        self.lines.append((True, emoji))
    def get_clustered(self):
        res = []
        current_state = None
        for state, string in self.lines:
            if state != current_state:
                res.append([])
                current_state = state
            res[-1].append(string)
        return ['\n'.join(r) for r in res]
    def concat(self, other: 'EmojiOutput'):
        self.lines.concat(other.lines)
    def __iadd__(self, other: 'EmojiOutput'):
        self.lines += other.lines
        return self


class EmojiFight:
    '''
    Helper class for storing the state of an "emoji fight" (see: patterns.py).
    '''
    # Global fight info
    weapons_left = ['🔨', '⛏', '🪓', '🪚', '🗡️', '🪡', '🪠', '🪒', '📌', '🔫', '🤛', '🏹']
    weapons_right = ['🔪', '🤜', '💉']
    weapons_dual = ['⚔️', '⚒️', '🛠️']

    weapons_regex = re.compile('(' + '|'.join(weapons_left + weapons_right + weapons_dual) + ')')

    corpses = [':skull_crossbones:', ':skull:', ':bone:', ':ghost:', ':headstone:', ':urn:', ':coffin:']

    # Fight-specific configuration
    rigged: Literal['left', 'right', 'both'] = None

    # State
    left: str
    weapon: str
    right: str

    done = False
    winner: Literal['left', 'right', 'both'] = None

    # History
    state_history = None
    output: EmojiOutput

    def __init__(self, left, weapon, right, odds=None, rigged=None):
        # State
        self.left = left
        self.weapon = weapon
        self.right = right
        # Config
        self.rigged = rigged
        # History
        self.state_history = []
        self.output = EmojiOutput()
        # Branching config, given as (branch_name, weight) pairs
        odds = odds or DEFAULT_ODDS
        self.branches, self.weights = tuple(zip(*odds))
        weight_sum = sum(self.weights)
        self.probs = tuple(w / weight_sum for w in self.weights)

    # ================================== State-related properties ==================================

    @property
    def facing_left(self) -> bool:
        return (self.weapon in self.weapons_left)
    @property
    def facing_right(self) -> bool:
        return not self.facing_left

    @property
    def target(self) -> str:
        return self.left if self.facing_left else self.right
    @target.setter
    def target(self, value: str) -> str:
        if self.facing_left: self.left = value
        else: self.right = value

    @property
    def attacker(self) -> str:
        return self.right if self.facing_left else self.left
    @attacker.setter
    def attacker(self, value: str) -> str:
        if self.facing_left: self.right = value
        else: self.left = value

    # ==================================== State-related actions ===================================

    def may_die(self, subj: Literal['left', 'right', 'both']):
        if subj == 'left':
            return self.rigged not in ('left', 'both')
        if subj == 'right':
            return self.rigged not in ('right', 'both')
        if subj == 'both':
            return not self.rigged

    def may_tie(self):
        return not self.rigged or self.rigged == "both"

    def swap_subjects(self) -> None:
        (self.left, self.right) = (self.right, self.left)
        if self.rigged == 'left':
            self.rigged = 'right'
        elif self.rigged == 'right':
            self.rigged = 'left'

    def kill_target(self) -> None:
        self.target = choice(self.corpses)

    # ======================================== State output ========================================

    def status_quo(self) -> str:
        return self.left + self.weapon + self.right

    def no_weapon(self) -> str:
        return self.left + '   ' + self.right

    def attacking(self) -> str:
        if self.facing_left:
            return ':boom:' + self.weapon + self.right
        return self.left + self.weapon + ':boom:'

    # ======================================== State output ========================================

    def push_state(self):
        self.state_history.append((self.left, self.weapon, self.right))

    def output_text(self, *lines: list[str]):
        self.output.add_text(choice(lines))

    def output_emoji(self, emoji: str):
        self.output.add_emoji(emoji)

    def perform_fight(self):
        output_text = self.output_text
        output_emoji = self.output_emoji

        if self.weapon in EmojiFight.weapons_dual:
            ## Start the battle by having one side draw a random weapon
            self.weapon = choice(EmojiFight.weapons_left) if chance(0.5) else choice(EmojiFight.weapons_right)
            output_emoji(self.status_quo())
            if chance(0.5):
                output_text('`en guarde!`', '`have at you!`', '`on your guard!`')

        # Loop until the fight ends somehow
        while True:
            self.push_state()
            branch = choice(self.branches, p=self.probs)

            if branch == 'attack':
                if (self.facing_left and not self.may_die('left')) or (self.facing_right and not self.may_die('right')):
                    continue

                output_emoji(self.attacking())
                r = random.random()

                if r < 0.3 or self.rigged == 'both': # 30% chance the attack is unsuccessful
                    output_emoji(self.status_quo())
                    output_text('`huh?!`', '`what?!`', '`nani?!`', '`...huh?!`', '`w-what?!`')

                    if r < 0.1 and self.may_tie():
                        # Of which a 1/3 chance the fight ends here
                        output_text(
                            '`h-he\'s not even scratched !!`',
                            '`t-this thing ain\'t human!`',
                            '`i-it\'s invincible !`'
                        )
                        break
                    else:
                        continue

                elif r < 0.7: # 40% chance they're dead and their corpse is shown
                    self.kill_target()
                    output_emoji(self.status_quo())

                # 30% chance they're dead and their corpse isn't shown
                break

            elif branch == 'noBullets':
                # The fight ends with both alive
                if not self.may_tie():
                    continue

                if len(self.state_history) == 1 or self.weapon != '🔫':
                    continue
                output_emoji(self.status_quo())
                output_text('`*click* *click* *click*`')
                output_text('`... out of bullets !!`')
                # Out of bullets ends the fight
                break

            elif branch == 'knife':
                # The attacker gets eliminated
                if (self.facing_left and not self.may_die('right')) or (self.facing_right and not self.may_die('left')):
                    continue

                old_weapon = self.weapon
                self.weapon = '🔪' if self.facing_left else '🗡️'
                output_emoji(self.status_quo())

                acts = ['unsheathes', 'pulls out', 'reveals', 'whips out']
                knives = ['katana', 'knife', 'kunai', 'dagger']
                output_text('`*' + choice(acts) + ' ' + choice(knives) + '*`')

                output_emoji(self.attacking())

                quips = [
                    '`it was knife knowing you.`',
                    '`now THIS is a knife.`',
                    '`I hope you got my point.`',
                ]
                if old_weapon == '🔫': quips += ['`don\'t bring a gun to a knife fight.`']

                if chance(0.5):
                    output_text(*quips)
                break

            elif branch == 'tool':
                if self.facing_left:
                    # These weapons are all left-facing, and we want them to be pulled out in self-defense
                    continue
                if not self.may_die('left'):
                    # The left subject gets eliminated
                    continue
                self.weapon = choice(['🔨', '⛏', '🪓', '🪚'])
                output_emoji(self.status_quo())
                output_emoji(self.attacking())

                quips = [
                    '`don\'t underestimate a craftsman.`',
                ]
                if self.weapon == '🔨':
                    quips += ['`hammer time!`', '`get hammered.`']
                elif self.weapon == '⛏':
                    quips += ['`get minecrafted.`', '`get fortnited.`', '`(fortnite default dance)`']
                elif self.weapon == '🪓':
                    quips += ['`get lumberjacked.`', '`can I "axe" you a question?`', '`hey Paul!`']
                elif self.weapon == '🪚':
                    quips += ['`I bet you didn\'t saw that one coming.`']

                output_text(*quips)
                break

            elif branch == 'punch':
                # The attacker gets eliminated
                if (self.facing_left and not self.may_die('right')) or (self.facing_right and not self.may_die('left')):
                    continue
                self.weapon = '🤜' if self.facing_left else '🤛'
                output_emoji(self.attacking())
                output_text('`POW!`')
                if chance(0.5):
                    output_emoji(self.left + (':point_left:' if self.facing_left else ':point_right:') + self.right)
                    output_text('`you are already dead.`')
                self.kill_target()
                output_emoji(self.no_weapon())
                break

            elif branch == 'hero':
                # Right attacker defeats themselves with their gun
                if not self.may_die('right'):
                    continue
                if self.weapon != '🔫':
                    continue
                output_emoji(self.left + '   ' + self.right + ':gun:')
                output_text('`I\'m fed up with this world.`', '`I can\'t take it anymore.`', '`goodbye cruel world.`')
                output_emoji(self.left + '   ' + ':boom::gun:')
                break

            elif branch == 'love':
                # The fight ends with both alive
                if not self.may_tie():
                    continue
                output_emoji(self.left + ':bouquet:' + self.right)
                output_text('`must we fight?`', '`why do we fight?`')
                output_emoji(self.left + ':heart:' + self.right)
                output_text('`love conquers all.`', '`love trumps hate.`', '`we will hide our feelings no longer.`')
                break

            elif branch == 'shake':
                # The fight ends with both alive
                if not self.may_tie():
                    continue
                output_emoji(self.no_weapon())
                output_text('`I\'m sorry. I can\'t do it.`', '`I\'m sorry, I can\'t do this.`', '`no, this is wrong.`')
                output_emoji(self.left + ':handshake:' + self.right)
                output_text('`let\'s put this behind us, pal.`', '`I hope you can forgive me.`', '`we can find a peaceful solution to our disagreement.`')
                break

            elif branch == 'time':
                if not self.facing_left:
                    continue
                if not self.may_die('right'):
                    continue
                output_emoji(self.status_quo() + ':cyclone::cyclone:')
                output_text('`~bzoom~`')
                output_emoji(self.status_quo() + self.weapon + self.left)
                output_text('`w-what?!`')
                output_emoji(self.left + self.weapon + ':boom:' + self.weapon + self.left)
                output_emoji(self.left + self.weapon + '      ' + self.left)
                output_text('`quick, take their weapon and my time machine.`')
                output_emoji(':cyclone::cyclone:' + '      ' + self.left)
                output_text('`~bzoom~`')
                break

            elif branch == 'teleport':
                if not self.rigged and len(self.state_history) > 3: continue
                old_weapon = self.weapon
                kawarimi = chance(0.5)
                if kawarimi: output_emoji(self.attacking())

                if self.facing_left:
                    output_emoji((':wood:' if kawarimi else ':dash:') + old_weapon + self.right)
                    if kawarimi: output_text('`Kawarimi no jutsu!`')
                    else: output_text('`*teleports behind you*`')
                    self.swap_subjects()
                    self.weapon = choice(EmojiFight.weapons_left)
                    output_emoji(old_weapon + self.left + self.weapon + self.right)
                else:
                    output_emoji(self.left + old_weapon + (':wood:' if kawarimi else ':dash:'))
                    if kawarimi: output_text('`Kawarimi no jutsu!`')
                    else: output_text('`*teleports behind you*`')
                    self.swap_subjects()
                    self.weapon = choice(EmojiFight.weapons_right)
                    output_emoji(self.left + self.weapon + self.right + old_weapon)

                if chance(0.5):
                    output_text('`nothing personnel.`', '`nothing personal, kid.`', '`psh, nothing personal.`')

                continue

            elif branch == 'kiss':
                if len(self.state_history) > 4:
                    continue
                kissing_faces = [':kissing_heart:', ':kissing:', ':kissing_smiling_eyes:', ':kissing_closed_eyes:']

                old_target = self.target
                self.target = choice(kissing_faces)
                output_emoji(self.left + ':kiss:' + self.right)
                output_text('`mwah!`')
                self.target = old_target

                reaction_faces = [':blush:', ':flushed:', ':wink:', ':relieved:']
                old_attacker = self.attacker
                self.attacker = choice(reaction_faces)
                output_emoji(self.status_quo())
                if chance(0.5):
                    self.attacker = old_attacker
                continue

            else:
                raise Exception(f'Encountered un-implemented branch: "{branch}"')


class EmojiBattle:
    # Config
    name: str
    contestants: list[str]

    # State
    winners: list[str]
    competing: list[str]
    losers: list[str]

    current_left: str
    current_right: str
    current_solo: str
    current_round_message: discord.Message
    current_round_state = None

    def __init__(self, name, contestants):
        self.name = name
        self.contestants = contestants

        # Initialize state
        self.winners = []
        self.competing = contestants[:]
        self.losers = []
        self.reset_round()

    def reset_round(self):
        self.current_left = None
        self.current_right = None
        self.current_solo = None
        self.current_round_message = None
        self.current_round_state = None

    def next_round(self, tier=None):
        if len(self.competing) == 0:
            raise Exception('No more competitors left.')
        if self.current_round_state not in (None, 'done'):
            raise Exception('A round is ongoing')

        self.reset_round()
        self.current_round_state = 'started'

        if len(self.competing) == 1:
            self.current_solo = self.competing[-1]
            self.competing.remove(self.current_solo)
            # ...
            return

        left, right = random.sample(self.competing, 2)
        self.current_left = left
        self.current_right = right
        self.competing.remove(left)
        self.competing.remove(right)