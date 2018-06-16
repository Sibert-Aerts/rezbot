import os
import re
import random

def TXTDIR(filename=''):
    return os.path.join(os.path.dirname(__file__), 'txt', filename)

searchify_regex = re.compile(r'[^a-z0-9\s]')
def searchify(text):
    return searchify_regex.sub('', text.lower()).strip()

class File:
    def __init__(self, name):
        self.name = name
        self.lines = None
        self.search_lines = None

    def load_lines(self, text):
        self.lines = list(filter(lambda x: x != '', (x.strip() for x in text.split('\n'))))

    def _get_search_lines(self):
        # search_lines is a list of (index, searchified_line) tuples
        if self.search_lines is None:
            self.search_lines = [(i, searchify(self.lines[i])) for i in range(len(self.lines))]
        return self.search_lines

    def _get_lines(self):
        if self.lines == None:
            with open(TXTDIR(self.name + '.txt'), 'r', encoding='utf-8') as file:
                self.load_lines(file.read())
        return self.lines

    def _search(self, query):
        '''Returns an iterable (with len!) of INDICES that match the query (all indices if query is empty)'''
        lines = self._get_lines()

        if query == '': return range(len(lines))

        # Extract absolute matches "of this form" from the query as "exact matches"
        a = searchify(query).split('"')
        exact = [a[i] for i in range(1, len(a), 2)]
        others = re.split('\s+', ''.join([a[i] for i in range(0, len(a), 2)]).strip())
        queries = exact + others

        search_lines = self._get_search_lines()
        results = list(filter(lambda l: all([q in l[1] for q in queries]), search_lines))
        return [r[0] for r in results]

    def get_random(self, count, query):
        indices = self._search(query)
        count = min(count, len(indices))
        indices = random.sample(indices, count)
        lines = self._get_lines()
        return [lines[i] for i in indices]

    def get_sequential(self, count, query):
        indices = self._search(query)
        index = random.choice(indices)
        lines = self._get_lines()
        # min ( random starting index containing index , biggest index that doesnt go out of bounds)
        index = max(0, min( index-random.randint(0, count-1) , len(lines)-count))
        return lines[index: index + count]


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