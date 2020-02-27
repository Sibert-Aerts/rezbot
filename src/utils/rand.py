import random

def chance(x, y=1):
    ''' Returns True with a chance x out of y. '''
    return random.random() * y <= x

def choose(population, n=None):
    ''' Uniformly choose n items from the population, allowing repeats. n = None for 1 item not in a list. '''
    if n is None: 
        return random.choice( population )
    if n < 0: 
        raise ValueError('Invalid sample size {}'.format(n))
    return [ random.choice( population ) for _ in range(n) ]

def sample(population, n):
    ''' Uniformly sample n items from the population; no repeats. n = -1 for the entire population. '''
    if n == -1 or n >= len(population):
        n = len(population)
    return random.sample(population, n)

def choose_slice(population, n):
    ''' Uniformly chooses a slice of length n from the population. n = -1 for the entire population. '''
    if n == -1 or n >= len(population):
        return population
    i = random.randint(0, len(population) - n)
    return population[i: i+n]


class Odds:
    '''
    A class that takes a list of (identifiers, weight) tuples
    and uses them to construct a probability switch.
    '''

    def __init__(self, oddsList):
        self.oddsMap = {}
        totalChance = sum( b for [a, b] in oddsList )

        s = 0
        for (key, weight) in oddsList:
            low = s
            s += weight
            self.oddsMap[key] = (low / totalChance, s / totalChance)

    def roll(self):
        self.r = random.random()

    def test(self, key):
        (low, high) = self.oddsMap[key]
        return low <= self.r < high