import os
import pickle


def _DIR(filename=''):
    return os.path.join(os.path.dirname(__file__), 'custom_pipes', filename)


class CustomPipe:
    def __init__(self, name, code, desc=None):
        self.version = 1
        self.name = name
        self.code = code
        self.desc = desc

    def info(self):
        # TODO: nicer formatting
        info = self.name + ':'
        if self.desc is not None:
            info += '\n\t' + self.desc
        info += '\nCode:'
        info += '\n\t' + self.code
        return info


class CustomPipes:
    def __init__(self, DIR, filename='custompipes.p'):
        self.pipes = {}
        self.DIR = DIR
        self.filename = filename

        try:
            if not os.path.exists(DIR()):
                os.mkdir(DIR())
            self.pipes = pickle.load(open(DIR(filename), 'rb+'))
            print('{} custom pipes loaded from "{}"!'.format(len(self.pipes), DIR(filename)))
        except Exception as e:
            print(e)
            print('Failed to load custom pipes from "{}"!'.format(DIR(filename)))

    def convert_v0(self, file):
        try:
            # newPipes is a dict: {name: {'desc': desc, 'code': code}}
            newPipes = pickle.load(open(file, 'rb'))
            count = 0
            for name in newPipes:
                if name in self.pipes: continue
                pipe = newPipes[name]
                self[name] = CustomPipe(name, pipe['code'], pipe['desc'])
                count += 1
            self.write()
            print('{} custom pipes successfully converted and added from "{}"!'.format(count, file))

        except Exception as e:
            print(e)
            print('Failed to convert custom pipes from "{}"!'.format(file))

    def __contains__(self, name):
        return name in self.pipes

    def __iter__(self):
        return (i for i in self.pipes)

    def __getitem__(self, name):
        return self.pipes[name]

    def __setitem__(self, name, val):
        if type(val).__name__ != 'CustomPipe':
            raise ValueError('CustomPipes should only contain items of class CustomPipe!')
        self.pipes[name] = val
        self.write()
        return val

    def __delitem__(self, name):
        del self.pipes[name]
        self.write()

    def __bool__(self):
        return len(self.pipes) > 0

    def __len__(self):
        return len(self.pipes)

    def write(self):
        pickle.dump(self.pipes, open(self.DIR(self.filename), 'wb+'))


custom_pipes = CustomPipes(_DIR)

# Comment out this line after the bot has ran once.
# custom_pipes.convert_v0('custompipes.p')