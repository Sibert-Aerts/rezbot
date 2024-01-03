import random
import re


class EmojiFight:
    '''
    Helper class for storing the state of an "emoji fight" (see: patterns.py).
    '''
    weapons_left = ['🔨', '⛏️', '🪓', '🪚', '🗡️', '🪡', '🪠', '🪒', '📌', '🔫', '🤛', '🏹']
    weapons_right = ['🔪', '🤜', '💉']
    weapons_dual = ['⚔️', '⚒️', '🛠️']

    weapons_regex = re.compile('(' + '|'.join(weapons_left + weapons_right + weapons_dual) + ')')

    corpses = [':skull_crossbones:', ':skull:', ':bone:', ':ghost:', ':headstone:', ':urn:', ':coffin:']

    def __init__(self, left, weapon, right):
        self.left = left
        self.weapon = weapon
        self.right = right

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

    def kill_target(self) -> None:
        self.target = random.choice(self.corpses)

    def status_quo(self) -> str:
        return self.left + self.weapon + self.right

    def no_weapon(self) -> str:
        return self.left + '   ' + self.right

    def attacking(self) -> str:
        if self.facing_left:
            return ':boom:' + self.weapon + self.right
        return self.left + self.weapon + ':boom:'