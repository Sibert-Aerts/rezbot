from .rand import *

'''
Helper class for processing/drawing emoji fights.
'''

class Attack:
    leftWeapons = '🔨⛏️🪓🪚🗡️🪡🪠🪒📌🔫🤛🏹'
    rightWeapons = '🔪🤜'

    def __init__(self, left, weapon, right):
        self.left = left
        self.weapon = weapon
        self.right = right

    def update_facing(self):
        self.leftFacing = (self.weapon in self.leftWeapons)

    def target(self, val=None):
        self.update_facing()
        if val is not None:
            if self.leftFacing:
                self.left = val
            else:
                self.right = val
        return self.left if self.leftFacing else self.right

    def attacker(self, val=None):
        self.update_facing()
        if val is not None:
            if self.leftFacing:
                self.right = val
            else:
                self.left = val
        return self.right if self.leftFacing else self.left

    def no_weapon(self):
        return self.left + '          ' + self.right

    def status_quo(self):
        return self.left + self.weapon + self.right

    def attacking(self):
        self.update_facing()
        if self.leftFacing:
            return ':boom:' + self.weapon + self.right
        return self.left + self.weapon + ':boom:'