from typing import Literal
from numpy.random import choice
import random
import re

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
    emit_history = None
    emit_stack = None

    def __init__(self, left, weapon, right, odds=None, rigged=None):
        # State
        self.left = left
        self.weapon = weapon
        self.right = right
        # Config
        self.rigged = rigged
        # History
        self.state_history = []
        self.emit_history = []
        self.emit_stack = []
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

    def push_emit(self, *s: list[str]):
        if len(s):
            s = choice(s)
        self.emit_history.append(s)
        self.emit_stack.append(s)

    def pop_emit(self):
        res = self.emit_stack
        self.emit_stack = []
        return res

    def perform_fight(self):
        emit = self.push_emit

        if self.weapon in EmojiFight.weapons_dual:
            ## Start the battle by having one side draw a random weapon
            self.weapon = choice(EmojiFight.weapons_left) if chance(0.5) else choice(EmojiFight.weapons_right)
            emit(self.status_quo())
            if chance(0.5):
                emit('`en guarde!`', '`have at you!`', '`on your guard!`')

        # Loop until the fight ends somehow
        while True:
            self.push_state()
            branch = choice(self.branches, p=self.probs)

            if branch == 'attack':
                if (self.rigged == 'left' and self.facing_left) or (self.rigged == 'right' and not self.facing_left):
                    continue

                emit(self.attacking())
                r = random.random()

                if r < 0.3 or self.rigged == 'both': # 30% chance the attack is unsuccessful
                    emit(self.status_quo())
                    emit('`huh?!`', '`what?!`', '`nani?!`', '`...huh?!`', '`w-what?!`')

                    if r < 0.1 and (not self.rigged or self.rigged == 'both'):
                        # Of which a 1/3 chance the fight ends here
                        emit(
                            '`h-he\'s not even scratched !!`',
                            '`t-this thing ain\'t human!`',
                            '`i-it\'s invincible !`'
                        )
                        break
                    else:
                        continue

                elif r < 0.7: # 40% chance they're dead and their corpse is shown
                    self.kill_target()
                    emit(self.status_quo())

                # 30% chance they're dead and their corpse isn't shown
                break

            elif branch == 'noBullets':
                # The fight ends with both alive
                if self.rigged and self.rigged != 'both':
                    continue

                if len(self.state_history) == 1 or self.weapon != '🔫':
                    continue
                emit(self.status_quo())
                emit('`*click* *click* *click*`')
                emit('`... out of bullets !!`')
                # Out of bullets ends the fight
                break

            elif branch == 'knife':
                # The attacker gets eliminated
                if (self.rigged == 'right' and self.facing_left) or (self.rigged == 'left' or not self.facing_left):
                    continue

                old_weapon = self.weapon
                self.weapon = '🔪' if self.facing_left else '🗡️'
                emit(self.status_quo())

                acts = ['unsheathes', 'pulls out', 'reveals', 'whips out']
                knives = ['katana', 'knife', 'kunai', 'dagger']
                emit('`*' + choice(acts) + ' ' + choice(knives) + '*`')

                emit(self.attacking())

                quips = [
                    '`it was knife knowing you.`',
                    '`now THIS is a knife.`',
                    '`I hope you got my point.`',
                ]
                if old_weapon == '🔫': quips += ['`don\'t bring a gun to a knife fight.`']

                if chance(0.5):
                    emit(choice(quips))
                break

            elif branch == 'tool':
                if self.facing_left:
                    # These weapons are all left-facing, and we want them to be pulled out in self-defense
                    continue
                if self.rigged == 'left':
                    continue
                self.weapon = choice(['🔨', '⛏', '🪓', '🪚'])
                emit(self.status_quo())
                emit(self.attacking())

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

                emit(*quips)
                break

            elif branch == 'punch':
                # The attacker gets eliminated
                if (self.rigged == 'right' and self.facing_left) or (self.rigged == 'left' or not self.facing_left):
                    continue
                self.weapon = '🤜' if self.facing_left else '🤛'
                emit(self.attacking())
                emit('`POW!`')
                if chance(0.5):
                    emit(self.left + (':point_left:' if self.facing_left else ':point_right:') + self.right)
                    emit('`you are already dead.`')
                self.kill_target()
                emit(self.no_weapon())
                break

            elif branch == 'hero':
                if self.rigged == 'right':
                    continue
                if self.weapon != '🔫':
                    continue
                emit(self.left + '   ' + self.right + ':gun:')
                emit('`I\'m fed up with this world.`', '`I can\'t take it anymore.`', '`goodbye cruel world.`')
                emit(self.left + '   ' + ':boom::gun:')
                break

            elif branch == 'love':
                # The fight ends with both alive
                if self.rigged and self.rigged != 'both':
                    continue
                emit(self.left + ':bouquet:' + self.right)
                emit('`must we fight?`', '`why do we fight?`')
                emit(self.left + ':heart:' + self.right)
                emit('`love conquers all.`', '`love trumps hate.`', '`we will hide our feelings no longer.`')
                break

            elif branch == 'shake':
                # The fight ends with both alive
                if self.rigged and self.rigged != 'both':
                    continue
                emit(self.no_weapon())
                emit('`I\'m sorry. I can\'t do it.`', '`I\'m sorry, I can\'t do this.`', '`no, this is wrong.`')
                emit(self.left + ':handshake:' + self.right)
                emit('`let\'s put this behind us, pal.`', '`I hope you can forgive me.`', '`we can find a peaceful solution to our disagreement.`')
                break

            elif branch == 'time':
                if not self.facing_left:
                    continue
                if self.rigged == 'right':
                    continue
                emit(self.status_quo() + ':cyclone::cyclone:')
                emit('`~bzoom~`')
                emit(self.status_quo() + self.weapon + self.left)
                emit('`w-what?!`')
                emit(self.left + self.weapon + ':boom:' + self.weapon + self.left)
                emit(self.left + self.weapon + '      ' + self.left)
                emit('`quick, take their weapon and my time machine.`')
                emit(':cyclone::cyclone:' + '      ' + self.left)
                emit('`~bzoom~`')
                break

            elif branch == 'teleport':
                if not self.rigged and len(self.state_history) > 3: continue
                old_weapon = self.weapon
                kawarimi = chance(0.5)
                if kawarimi: emit(self.attacking())

                if self.facing_left:
                    emit((':wood:' if kawarimi else ':dash:') + old_weapon + self.right)
                    if kawarimi: emit('`Kawarimi no jutsu!`')
                    else: emit('`*teleports behind you*`')
                    self.swap_subjects()
                    self.weapon = choice(EmojiFight.weapons_left)
                    emit(old_weapon + self.left + self.weapon + self.right)
                else:
                    emit(self.left + old_weapon + (':wood:' if kawarimi else ':dash:'))
                    if kawarimi: emit('`Kawarimi no jutsu!`')
                    else: emit('`*teleports behind you*`')
                    self.swap_subjects()
                    self.weapon = choice(EmojiFight.weapons_right)
                    emit(self.left + self.weapon + self.right + old_weapon)

                if chance(0.5):
                    emit('`nothing personnel.`', '`nothing personal, kid.`', '`psh, nothing personal.`')

                continue

            elif branch == 'kiss':
                if len(self.state_history) > 4:
                    continue
                kissing_faces = [':kissing_heart:', ':kissing:', ':kissing_smiling_eyes:', ':kissing_closed_eyes:']

                old_target = self.target
                self.target = choice(kissing_faces)
                emit(self.left + ':kiss:' + self.right)
                emit('`mwah!`')
                self.target = old_target

                reaction_faces = [':blush:', ':flushed:', ':wink:', ':relieved:']
                old_attacker = self.attacker
                self.attacker = choice(reaction_faces)
                emit(self.status_quo())
                if chance(0.5):
                    self.attacker = old_attacker
                continue

            else:
                raise Exception(f'Encountered un-implemented branch: "{branch}"')