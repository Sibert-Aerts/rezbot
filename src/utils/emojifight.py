import random
import re

'''
Helper class for processing/drawing emoji fights.
'''

class EmojiFight:
    leftWeapons = ['🔨', '⛏️', '🪓', '🪚', '🗡️', '🪡', '🪠', '🪒', '📌', '🔫', '🤛', '🏹']
    rightWeapons = ['🔪', '🤜' '💉']
    dualWeapons = ['⚔️', '⚒️', '🛠️']

    weaponRegex = re.compile('(' + '|'.join(leftWeapons + rightWeapons + dualWeapons) + ')')

    corpses = [':skull_crossbones:', ':skull:', ':bone:', ':ghost:', ':headstone:', ':urn:', ':coffin:']

    def __init__(self, left, weapon, right):
        self.left = left
        self.weapon = weapon
        self.right = right

    @property
    def leftFacing(self) -> bool:
        return (self.weapon in self.leftWeapons)

    @property
    def target(self) -> str:
        return self.left if self.leftFacing else self.right
    @target.setter
    def target(self, value: str) -> str:
        if self.leftFacing: self.left = value
        else: self.right = value

    @property
    def attacker(self) -> str:
        return self.right if self.leftFacing else self.left
    @attacker.setter
    def attacker(self, value: str) -> str:
        if self.leftFacing: self.right = value
        else: self.left = value

    def killTarget(self) -> None:
        self.target = random.choice(self.corpses)

    def no_weapon(self) -> str:
        return self.left + '   ' + self.right

    def status_quo(self) -> str:
        return self.left + self.weapon + self.right

    def attacking(self) -> str:
        if self.leftFacing:
            return ':boom:' + self.weapon + self.right
        return self.left + self.weapon + ':boom:'