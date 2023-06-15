import os
import re
import json
from typing import Any, List

def this_dir(filename=''):
    return os.path.join(os.path.dirname(__file__), filename)

class VariableStore:
    ''' Class for getting and setting json representable variables. '''
    def __init__(self, filename:str):
        self.filename = filename
        self.vars = {}
        self.persistent_names = set()
        ## Read persistent variables from file
        try:
            size = os.path.getsize(this_dir(self.filename))
            file = open(this_dir(self.filename), 'r+')
            self.vars = json.load(file)
            self.persistent_names = set(self.vars.keys())
            print('{} variables loaded totalling {} KB from "{}"!'.format(len(self.vars), size//1000, filename))
        except:
            print('Could not open variable store {}, making an empty one!'.format(filename))

    def get(self, name:str, default: Any=None) -> Any:
        try:
            return self.vars[name]
        except:
            if default is None:
                raise KeyError('No variable "{}" found.'.format(name))
            return default

    def set(self, name:str, value: Any, persistent: bool=False) -> None:
        self.vars[name] = value
        if persistent:
            self.persistent_names.add(name)
            self.write()

    def delete(self, name:str) -> None:
        del self.vars[name]
        if name in self.persistent_names:
            self.persistent_names.remove(name)
            self.write()

    def list_names(self, pattern=None, persistent=True) -> List[str]:
        if persistent: names = list(self.persistent_names)
        else: names = [name for name in self.vars.keys() if name not in self.persistent_names]
        if pattern:
            pattern = re.compile(pattern)
            names = [name for name in names if pattern.search(name)]
        names.sort()
        if names:
            return '{} variables: '.format('Persistent' if persistent else 'Transient') + ', '.join(names)
        else:
            return 'No {} variables.'.format('persistent' if persistent else 'transient')

    def write(self) -> None:
        # Write persistent variables to file
        # TODO: instead of rebuilding this dict each time, actually keep a dict of only persistent variables the entire time?
        # Would require more logical juggling around of different situations...
        persistent = {p : self.vars[p] for p in self.persistent_names}
        json.dump(persistent, open(this_dir(self.filename), 'w+'))
