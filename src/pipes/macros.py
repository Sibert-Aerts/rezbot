import os
import pickle
import re
from lru import LRU

from shutil import copyfile
from discord import Embed
import utils.texttools as texttools
import permissions

def DIR(filename=''):
    return os.path.join(os.path.dirname(__file__), 'macros', filename)

class MacroSig:
    def __init__(self, name, default=None, desc=None):
        self.name = name
        self.default = default
        self.desc = desc

    def __str__(self):
        out = '__' + self.name + ':__ '
        if self.desc:
            out += self.desc
        if self.default:
            out += ' (Default: ' + self.default + ')'
        else:
            out += ' **Required**'
        return out


class Macro:
    def __init__(self, name, code, authorName, authorId, authorAvatarURL, desc=None, visible=True, command=False):
        self.version = 3
        self.name = name
        self.code = code
        self.authorName = authorName
        self.authorId = authorId
        self.authorAvatarURL = authorAvatarURL
        self.desc = desc
        self.visible = visible
        self.command = command
        self.signature = {}

    def v2_to_v3(m):
        if m.version != 2: return m
        m.version = 3
        m.signature = {}
        return m

    def embed(self):
        title = self.name + (' `hidden`' if not self.visible else '')
        embed = Embed(title='Macro: ' + title, description=(self.desc or ''), color=0x06ff83)
        
        ### Parameters
        if self.signature:
            argstr = '\n'.join(str(self.signature[s]) for s in self.signature)
            embed.add_field(name='Parameters', value=argstr, inline=False)

        ### Script
        embed.add_field(name='Script', value=texttools.block_format(self.code), inline=False)

        ### Footer
        embed.set_footer(text=self.authorName, icon_url=self.authorAvatarURL)
        return embed

    # Regex partially identical to the one in signature.py
    arg_finder = re.compile(r'\b(\w+)=("[^"]*"|\'[^\']*\'|\S+)\s*')

    def apply_args(self, argstr: str):
        # TODO: required args?
        # Load the defaults
        args = {s: self.signature[s].default for s in self.signature}

        if argstr is not None:
            # Interpret the argstring:
            for name, value in re.findall(Macro.arg_finder, argstr):
                if value[0] == value[-1] and value[0] in ['"', "'"]: value = value[1:-1]
                args[name] = value

        code = self.code
        for arg in args:
            code = code.replace('$' + arg + '$', args[arg])
        return code

    def authorised(self, user):
        '''Test whether or not the given user is authorised to modify this macro.'''
        return permissions.has(user.id, permissions.owner) or user.id == int(self.authorId)


class Macros:
    def __init__(self, DIR, filename):
        self.macros = {}
        self.DIR = DIR
        self.filename = filename
        self.pipeline_cache = LRU(20)
        try:
            if not os.path.exists(DIR()): os.mkdir(DIR())
            self.macros = pickle.load(open(DIR(filename), 'rb+'))
            self.convert_v2_to_v3()
            print('{} macros loaded from "{}"!'.format(len(self.macros), filename))
        except Exception as e:
            print(e)
            print('Failed to load macros from "{}"!'.format(DIR(filename)))

    def convert_v2_to_v3(self):
        FROM_VERSION = 2
        if not [name for name in self.macros if self.macros[name].version == FROM_VERSION]: return
        try:
            copyfile(self.DIR(self.filename), self.DIR(self.filename + '.v{}_backup'.format(FROM_VERSION)))
            count = 0
            for name in self.macros:
                m = self.macros[name]
                if m.version == FROM_VERSION:
                    self.macros[name] = Macro.v2_to_v3(m)
                    count += 1
            self.write()
            if count: print('{} macros successfully converted and added from "{}"!'.format(count, self.filename))
        except Exception as e:
            print(e)
            print('Failed to convert macros from "{}"!'.format(self.filename))

    def visible(self):
        return [i for i in self.macros if self.macros[i].visible]

    def hidden(self):
        return [i for i in self.macros if not self.macros[i].visible]

    def write(self):
        '''Write the list of macros to a pickle file.'''
        pickle.dump(self.macros, open(self.DIR(self.filename), 'wb+'))

    def __contains__(self, name):
        return name in self.macros

    def __iter__(self):
        return (i for i in self.macros)

    def __getitem__(self, name) -> Macro:
        return self.macros[name]

    def __setitem__(self, name, val):
        if type(val).__name__ != 'Macro':
            raise ValueError('Macros should only contain items of class Macro!')
        self.macros[name] = val
        self.write()
        return val

    def __delitem__(self, name):
        del self.macros[name]
        self.write()

    def __bool__(self):
        return len(self.macros) > 0

    def __len__(self):
        return len(self.macros)


pipe_macros = Macros(DIR, 'pipe_macros.p')
source_macros = Macros(DIR, 'source_macros.p')