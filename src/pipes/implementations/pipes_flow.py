import random
import math

from .pipes import make_pipe, many_to_one, set_category
from ..signature import Par, Option
from utils.rand import choose_slice
from utils.util import parse_bool


#####################################################
#                   Pipes : FLOW                    #
#####################################################
set_category('FLOW')

@make_pipe({
    'times': Par(int, None, 'Number of times repeated'),
    'max'  : Par(int, -1, 'Maximum number of outputs produced, -1 for unlimited.')
})
def repeat_pipe(input, times, max):
    '''Repeats each row a given number of times.'''
    if max == -1:
        return input * times
    else:
        times = min(times, math.ceil(max/len(input))) # Limit how many unnecessary items the [:max] in the next line shaves off
        return (input*times)[:max]


REMOVE_WHAT = Option('all', 'empty', 'whitespace')

@make_pipe({ 
    'what': Par(REMOVE_WHAT, REMOVE_WHAT.all, 'What to filter: all/empty/whitespace') 
})
def remove_pipe(items, what):
    '''
    Removes all items (or specific types of items) from the flow.

    all: Removes every item
    whitespace: Removes items that only consist of whitespace (including empty ones)
    empty: Only removes items equal to the empty string ("")
    '''
    if what == REMOVE_WHAT.all:
        return []
    if what == REMOVE_WHAT.whitespace:
        return [x for x in items if x.strip()]
    if what == REMOVE_WHAT.empty:
        return [x for x in items if x]


@make_pipe({})
def sort_pipe(input):
    '''Sorts the input values lexicographically.'''
    # IMPORTANT: `input` is passed BY REFERENCE, so we are NOT supposed to mess with it!
    out = input[:]
    out.sort()
    return out


@make_pipe({})
def reverse_pipe(input):
    '''Reverses the order of input items.'''
    return input[::-1]


@make_pipe({})
def shuffle_pipe(input):
    '''Randomly shuffles input values.'''
    # IMPORTANT NOTE: `input` is passed BY REFERENCE, so we are NOT supposed to mess with it!
    out = input[:]
    random.shuffle(out)
    return out


@make_pipe({
    'number' : Par(int, 1, 'The number of values to choose.', lambda x: x>=0)
})
def choose_pipe(input, number):
    '''Chooses random values with replacement (i.e. may return repeated values).'''
    return random.choices(input, k=number)


@make_pipe({
    'length' : Par(int, None, 'The desired slice length.', lambda x: x>=0),
    'cyclical': Par(parse_bool, False, 'Whether or not the slice is allowed to "loop back" to cover both some first elements and last elements. ' +
            'i.e. If False, elements at the start and end of the input have lower chance of being selected, if True all elements have an equal chance.')
})
def choose_slice_pipe(input, length, cyclical):
    '''Chooses a random contiguous sequence of inputs.'''
    return choose_slice(input, length, cyclical=cyclical)


@make_pipe({
    'number' : Par(int, 1, 'The number of values to sample.', lambda x: x>=0) 
})
def sample_pipe(input, number):
    '''
    Chooses random values without replacement.
    Never produces more values than the number it receives.
    '''
    return random.sample(input, min(len(input), number))


@make_pipe({
    'count' : Par(parse_bool, False, 'Whether each unique item should be followed by an item counting its number of occurrences')
})
def unique_pipe(input, count):
    '''Leaves only the first unique occurence of each item.'''
    if not count: return [*{*input}]

    values = []
    counts = []
    for value in input:
        try:
            counts[values.index(value)] += 1
        except:
            values.append(value)
            counts.append(1)
    counts = map(str, counts)
    return [x for tup in zip(values, counts) for x in tup]


@make_pipe({})
@many_to_one
def count_pipe(input):
    '''Counts the number of input items.'''
    return [str(len(input))]

