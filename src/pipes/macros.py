import os
import pickle
import re
from lru import LRU

from shutil import copyfile
from discord import Embed
from .signature import ArgumentError
import utils.texttools as texttools
import permissions

def DIR(filename=''):
    return os.path.join(os.path.dirname(__file__), 'macros', filename)

class MacroSig:
    # NOTE: Serialized; do not rename.
    def __init__(self, name, default=None, desc=None):
        self.name = name
        self.default = default
        self.desc = desc

    def __str__(self):
        out = '* **' + self.name + ':**'
        if self.desc:
            out += ' ' + self.desc or ''
        if self.default:
            out += ' (default: "' + self.default + '")'
        else:
            out += ' (REQUIRED)'
        return out


class Macro:
    def __init__(self, kind, name, code, authorName, authorId, desc=None, visible=True, command=False):
        self.version = 4
        self.kind: str = kind
        self.name: str = name
        self.code: str = code
        self.authorName: str = authorName
        self.authorId: int = authorId
        self.desc: str = desc
        self.visible: bool = visible
        self.command: bool = command
        self.signature: dict[str, MacroSig] = {}

    def v3_to_v4(self, kind):
        if self.version != 3: return self
        self.kind = kind
        self.authorId = int(self.authorId)
        self.version = 4
        return self

    def embed(self, ctx=None):
        title = self.name + (' `hidden`' if not self.visible else '')
        embed = Embed(title=self.kind + ' Macro: ' + title, description=self.desc, color=0x06ff83)

        ### Parameter list
        if self.signature:
            argstr = '\n'.join(str(self.signature[s]) for s in self.signature)
            embed.add_field(name='Parameters', value=argstr, inline=False)

        ### Script box
        embed.add_field(name='Script', value=texttools.block_format(self.code), inline=False)

        ### Author credit footer
        author = None
        if ctx:
            # Look for the author in the current Guild first
            if ctx.guild: author = ctx.guild.get_member(self.authorId)
            if not author: author = ctx.bot.get_user(self.authorId)        

        if author: embed.set_footer(text=author.display_name, icon_url=author.avatar)
        else: embed.set_footer(text=self.authorName)
    
        return embed
    
    def apply_signature(self, args: dict[str, str]) -> dict[str, str]:
        '''Use the Macro's signature to insert default arguments and check for missing arguments.'''
        # Important: Do not modify args
        result_args = {s: self.signature[s].default for s in self.signature if s not in args}
        result_args.update(args)
        # Ensure no required arguments are missing
        missing = [s for s in args if args[s] is None]
        if missing:
            raise ArgumentError(f'Missing required parameter{"s" if len(missing)>1 else ""}: {" ".join("`%s`"%p for p in missing)}')
        return result_args

    def apply_args(self, args: dict) -> str:
        '''Insert arguments into macro code by replacing instances of '$arg$' with its value in `args`.'''
        code = self.code
        for arg in args:
            code = code.replace('$'+arg+'$', args[arg])
        return code

    def authorised(self, user):
        '''Test whether or not the given user is authorised to modify this macro.'''
        return permissions.has(user.id, permissions.owner) or user.id == int(self.authorId)


class Macros:
    macros: dict[str, Macro]

    def __init__(self, DIR, kind, filename):
        self.macros = {}
        self.DIR = DIR
        self.kind = kind
        self.filename = filename
        self.pipeline_cache = LRU(60)
        try:
            if not os.path.exists(DIR()): os.mkdir(DIR())
            self.macros = pickle.load(open(DIR(filename), 'rb+'))
            self.convert_v3_to_v4()
            print('{} macros loaded from "{}"!'.format(len(self.macros), filename))
        except Exception as e:
            print(e)
            print('Failed to load macros from "{}"!'.format(DIR(filename)))

    def convert_v3_to_v4(self):
        FROM_VERSION = 3
        if not [name for name in self.macros if self.macros[name].version == FROM_VERSION]: return
        try:
            copyfile(self.DIR(self.filename), self.DIR(self.filename + '.v{}_backup'.format(FROM_VERSION)))
            count = 0
            for name in self.macros:
                m = self.macros[name]
                if m.version == FROM_VERSION:
                    self.macros[name] = m.v3_to_v4(self.kind)
                    count += 1
        except Exception as e:
            print(e)
            print('Failed to convert macros from "{}"!'.format(self.filename))
        else:
            self.write()
            if count: print('{} macros successfully converted and added from "{}"!'.format(count, self.filename))

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

    def values(self):
        return self.macros.values()

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


pipe_macros = Macros(DIR, 'Pipe', 'pipe_macros.p')
source_macros = Macros(DIR, 'Source', 'source_macros.p')