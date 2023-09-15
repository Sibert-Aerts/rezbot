from collections import defaultdict

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pipes.pipe import Spout


class SpoutState:
    '''
    Represents a script's "outgoing information", collected as the script is being executed.
    Conceptually, propagates information "upwards", where the Context object propagates information "downwards".
    '''
    print_values: list[list[str]]
    explicit_print: bool = False # TODO: print hook should set this one instead of putting a callback
    suppressed_print: bool = False # TODO: suppress_print hook should set this one instead of putting a callback

    callbacks: list[tuple['Spout', dict, list]]

    aggregated: defaultdict[str, list[tuple]]
    aggregated_spouts: set['Spout']

    def __init__(self):
        self.print_values = []
        self.callbacks = []
        self.aggregated = defaultdict(list)
        self.aggregated_spouts = set()

    def add_simple_callback(self, spout: 'Spout', values, args):
        self.callbacks.append((spout, values, args))

    def add_aggregated_callback(self, spout: 'Spout', values, args):
        self.aggregated[spout.name].append((values, args))
        self.aggregated_spouts.add(spout)

    def extend(self, other: 'SpoutState', extend_print=False):
        '''Absorb another SpoutState into this one.'''
        # Extending print is opt-in because it only makes sense sometimes
        if extend_print:
            self.print_values.extend(other.print_values)
        
        self.callbacks.extend(other.callbacks)

        for key, values in other.aggregated.items():
            self.aggregated[key].extend(values)
        self.aggregated_spouts |= other.aggregated_spouts

    def anything(self):
        '''Whether anything has been explicitly spouted.'''
        return bool(self.print_values) or bool(self.callbacks) or bool(self.aggregated_spouts)