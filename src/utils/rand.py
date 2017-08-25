import random

def chance(x, y=1):
    '''Has a chance x out of y to return True.'''
    return random.random() <= x

# I just like this name better.
choose = random.choice

# this class is a bit odd and could be put to work better
class Odds:
    '''
    A class that takes a list of (identifiers, weight) tuples
    and uses them to construct a probability switch.
    '''

    def __init__(self, oddsList):
        self.oddsMap = {}

        totalChance = sum([b for [a, b] in oddsList])

        s = 0
        for (key, weight) in oddsList:
            low = s
            s += weight
            self.oddsMap[key] = (low / totalChance, s / totalChance)

    def roll(self):
        self.r = random.random()

    def test(self, key):
        (low, high) = self.oddsMap[key]
        return self.r <= high and (self.r > low or low == 0)