import os
import json
import traceback
from shutil import copyfile
from lru import LRU

from discord import Embed, TextChannel, Client
from .signature import ArgumentError
from .pipeline import Pipeline
from .executable_script import ExecutableScript
from .logger import ErrorLog
import utils.texttools as texttools
import permissions


def DIR(filename=''):
    return os.path.join(os.path.dirname(__file__), '..', 'macros', filename)


class MacroParam:
    CURRENT_VERSION = 5

    def __init__(self, name: str, default: str=None, desc: str=None):
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

    # ================ Serialization ================

    def serialize(self):
        return {
            '_version': MacroParam.CURRENT_VERSION,
            'name': self.name,
            'default': self.default,
            'desc': self.desc,
        }

    @classmethod
    def deserialize(cls, values):
        version = values.pop('_version')
        if version == 5:
            return MacroParam(**values)
        raise NotImplementedError()


class Macro:
    CURRENT_VERSION = 5
    SIMPLE_ATTRS = [
        'kind', 'name', 'code', 'authorName', 'authorId', 'desc', 'visible', 'command'
    ]

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
        self.signature: dict[str, MacroParam] = {}

    def embed(self, bot: Client=None, channel: TextChannel=None, **kwargs):
        title = self.name + (' `hidden`' if not self.visible else '')
        embed = Embed(title=self.kind + ' Macro: ' + title, description=self.desc, color=0x06ff83)

        ### Parameter list
        if self.signature:
            argstr = '\n'.join(str(self.signature[s]) for s in self.signature)
            embed.add_field(name='Parameters', value=argstr, inline=False)

        ### Script box
        script_disp = self.code
        if len(script_disp) > 900:
            # Embed fields have 1024 char limit
            script_disp = script_disp[:900] + ' (...)'
        embed.add_field(name='Script', value=texttools.block_format(script_disp), inline=False)

        ### Author credit footer
        author = None
        if channel and channel.guild:
            author = channel.guild.get_member(self.authorId)
        if not author and bot:
            author = bot.get_user(self.authorId)

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

    def authorised(self, user):
        '''Test whether or not the given user is authorised to modify this macro.'''
        return permissions.has(user.id, permissions.owner) or user.id == int(self.authorId)

    # ========================================= Validation =========================================

    def get_static_errors(self) -> ErrorLog:
        if self.kind == "Pipe":
            return Pipeline.from_string(self.code).get_static_errors()
        elif self.kind == "Source":
            return ExecutableScript.from_string(self.code).get_static_errors()

    # ======================================== Serialization =======================================

    def serialize(self):
        return {
            '_version': Macro.CURRENT_VERSION,
            'attrs': {a: getattr(self, a) for a in Macro.SIMPLE_ATTRS},
            'signature': [v.serialize() for v in self.signature.values()],
        }

    @classmethod
    def deserialize(cls, values):
        version = values.pop('_version')
        if version == 5:
            macro = Macro(**values['attrs'])
            sigs = [MacroParam.deserialize(v) for v in values['signature']]
            macro.signature = {sig.name: sig for sig in sigs}
            return macro
        raise NotImplementedError()


class Macros:
    macros: dict[str, Macro]

    def __init__(self, DIR, kind, filename):
        self.macros = {}
        self.DIR = DIR
        self.kind = kind
        self.json_filename = filename + '.json'
        self.read_macros_from_file()

    # ================ Reading/writing ================

    def read_macros_from_file(self):
        try:
            # Ensure the macros directory exists
            if not os.path.exists(DIR()): os.mkdir(DIR())

            # Deserialize Macros from JSON data
            with open(DIR(self.json_filename), 'r+') as file:
                data = json.load(file)
                upgrade_needed = (
                    any(d['_version'] != Macro.CURRENT_VERSION for d in data)
                    or any(p['_version'] != MacroParam.CURRENT_VERSION for d in data for p in d['signature'])
                )
                if upgrade_needed:
                    new_filename = self.json_filename + '.v{}_backup'.format(Macro.CURRENT_VERSION-1)
                    print(f'Deserializing Macros that require upgrading, backing up pre-upgraded data in {new_filename}')
                    copyfile(self.DIR(self.json_filename), self.DIR(new_filename))
                self.deserialize(data)

            print(f'{len(self.macros)} macros loaded from "{self.json_filename}"!')

        except Exception as e:
            print(f'Failed to load macros from "{self.json_filename}"!')
            print(traceback.format_exc())
            print()

    def write(self):
        '''Write the list of macros to a json file.'''
        with open(self.DIR(self.json_filename), 'w+') as file:
            json.dump(self.serialize(), file)

    # ================ Serialization ================

    def serialize(self):
        return [v.serialize() for v in self.macros.values()]

    def deserialize(self, data):
        # NOTE: Deserializes in-place, does not create a new object.
        macros = [Macro.deserialize(d) for d in data]
        self.macros = {macro.name: macro for macro in macros}

    # ================ Interface ================

    def visible(self):
        return [i for i in self.macros if self.macros[i].visible]

    def hidden(self):
        return [i for i in self.macros if not self.macros[i].visible]

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


MACRO_PIPES = Macros(DIR, 'Pipe', 'pipe_macros')
MACRO_SOURCES = Macros(DIR, 'Source', 'source_macros')