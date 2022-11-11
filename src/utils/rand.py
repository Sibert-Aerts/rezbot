import random
from typing import List, Tuple

def chance(x, y=1):
    ''' Returns True with a chance x out of y. '''
    return random.random() * y <= x

def choose(population, n=None):
    ''' Uniformly choose n items from the population, allowing repeats. n=None for 1 item, not wrapped in a list. '''
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

def choose_slice(population, n, cyclical=False):
    '''
    Uniformly chooses a slice of length n from the population. n = -1 for the entire population.
    
    If `cyclical` is True it may also select a slice that covers both some last few and first few elements, as if the list of elements was a cycle.
    If this is False, the first (n-1) elements have a lower chance of being in the selected slice, if it is True all the elements have the same chance.
    '''
    length = len(population)
    if not cyclical:
        if n == -1 or n >= length:
            return population
        i = random.randint(0, length - n)
        return population[i: i+n]
    else:
        if n == -1 or n >= length:
            n = length
        i = random.randint(0, length - 1)
        if i + n >= length:
            return population[i:] + population[:i+n-length]
        else:
            return population[i: i+n]



class RandomBranch:
    '''
    A class that takes a list of (name, weight) tuples
    and uses them to construct a probability switch.
    '''

    def __init__(self, nameList : List[Tuple[str, float]]):
        self.oddsMap = {}
        totalChance = sum( b for [a, b] in nameList )

        s = 0
        for (key, weight) in nameList:
            low = s
            s += weight
            self.oddsMap[key] = (low / totalChance, s / totalChance)

    def roll(self):
        self.r = random.random()

    def test(self, key):
        (low, high) = self.oddsMap[key]
        return low <= self.r < high

    def get(self):
        for (key, (low, high)) in self.oddsMap.items():
            if low <= self.r < high: return key