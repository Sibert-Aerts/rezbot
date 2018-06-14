import os
import random

def TXTDIR(filename=''):
    return os.path.join(os.path.dirname(__file__), 'txt', filename)


class File:
    def __init__(self, name):
        self.name = name
        self.lines = None

    def load_lines(self, text):
        self.lines = list(filter(lambda x: x.strip() != '', text.split('\n')))

    def _get(self):
        if self.lines == None:
            with open(TXTDIR(self.name + '.txt'), 'r', encoding='utf-8') as file:
                self.load_lines(file.read())
        return self.lines

    def get(self, count=1):
        return random.sample(self._get(), min(count, len(self.lines)))


class Files:
    def __init__(self):
        self.files = {}
        for file in os.listdir(TXTDIR()):
            name = file[:-4]
            self.files[name] = File(name)
        print('%d uploaded files found!' % len(self.files))

    def add_file(self, filename, content):
        if filename[-4:] != '.txt': filename += '.txt'
        name = filename[:-4]
        with open(TXTDIR(filename), 'w+', encoding='utf-8') as file:
            file.write(content)
        file = self.files[name] = File(name)
        file.load_lines(content)
        return file

    def __clean_name(name):
        return name if name[-4:] != '.txt' else name

    def __contains__(self, name):
        return (Files.__clean_name(name) in self.pipes)

    def __iter__(self):
        return (n for n in self.files)

    def __getitem__(self, name):
        return self.files[Files.__clean_name(name)]


uploads = Files()