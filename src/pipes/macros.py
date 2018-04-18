import os
import pickle
from shutil import copyfile


def DIR(filename=''):
    return os.path.join(os.path.dirname(__file__), 'macros', filename)


class Macro:
    def __init__(self, name, code, authorName, authorId, authorAvatarURL, desc=None):
        self.version = 1
        self.name = name
        self.code = code
        self.authorName = authorName
        self.authorId = authorId
        self.authorAvatarURL = authorAvatarURL
        self.desc = desc

    def info(self):
        # TODO: nicer formatting
        info = self.name + ':'
        if self.desc is not None:
            info += '\n\t' + self.desc
        info += '\nAuthor: ' + self.authorName
        info += '\nCode:'
        info += '\n\t' + self.code
        return info


class Macros:
    def __init__(self, DIR, filename):
        self.macros = {}
        self.DIR = DIR
        self.filename = filename
        try:
            if not os.path.exists(DIR()): os.mkdir(DIR())
            self.macros = pickle.load(open(DIR(filename), 'rb+'))
            print('{} macros loaded from "{}"!'.format(len(self.macros), DIR(filename)))
        except Exception as e:
            print(e)
            print('Failed to load macros from "{}"!'.format(DIR(filename)))

    # def convert_(self, file):
    #     try:
    #         copyfile(self.DIR(file), self.DIR(self.filename))
    #         newMacros = pickle.load(open(self.DIR(self.filename), 'rb+'))
    #         count = 0
    #         for name in newMacros:
    #             if name in self.macros: continue
    #             macro = newMacros[name]
    #             self[name] = Macro(macro.name, macro.code, 'Rezuaq', '154597714619793408', macro.desc)
    #             count += 1
    #         self.write()
    #         print('{} macros successfully converted and added from "{}"!'.format(count, file))

    #     except Exception as e:
    #         print(e)
    #         print('Failed to convert macros from "{}"!'.format(file))

    def __contains__(self, name):
        return name in self.macros

    def __iter__(self):
        return (i for i in self.macros)

    def __getitem__(self, name):
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

    def write(self):
        '''Write the list of macros to a pickle file.'''
        pickle.dump(self.macros, open(self.DIR(self.filename), 'wb+'))


pipe_macros = Macros(DIR, 'pipe_macros.p')
source_macros = Macros(DIR, 'source_macros.p')

# Comment out this line after the bot has ran once.
# pipe_macros.convert_v1_to_v2('custompipes.p')