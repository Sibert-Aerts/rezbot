import os
import re
import pickle
import random
import nltk
import markovify

def DIR(filename=''):
    return os.path.join(os.path.dirname(__file__), 'files', filename)

searchify_regex = re.compile(r'[^a-z0-9\s]')
def searchify(text):
    return searchify_regex.sub('', text.lower()).strip()


class FileInfo:
    '''Metadata class for a File, doesn't store any actual data.'''
    def __init__(self, name, author_name, author_id, sequential=False, sentences=False, splitter='\n+'):
        self.version = 1
        self.name = name
        self.author_name = author_name
        self.author_id = author_id

        self.sequential = sequential
        self.sentences = sentences
        self.splitter = splitter

        # Making some assumptions here that these are available filenames
        self.pickle_file = name + '.p'
        self.raw_file = name + '.txt'
        self.sentences_file = None
        self.markov_file = None

    def write(self):
        pickle.dump(self, open(DIR(self.pickle_file), 'wb+'))

    def __repr__(self):
        return '\n'.join(str(x) for x in [self.name, self.author_name, self.author_id, self.raw_file, self.sentences_file, self.markov_file])


class File:
    def __init__(self, info):
        '''Constructor used when a file is loaded at startup.'''
        self.info = info
        self.lines = None
        self.search_lines = None
        self.sentences = None
        self.search_sentences = None
        self.markov_model = None

    def new(name, author_name, author_id, raw):
        '''Constructor used when a file is uploaded.'''
        info = FileInfo(name, author_name, author_id)
        info.write()
        file = File(info)
        file.process_raw(raw)
        file.write_raw(raw)
        return file

    def write_raw(self, raw):
        '''Only called once the very first time the file is uploaded.'''
        with open(DIR(self.info.raw_file), 'w+', encoding='utf-8') as file:
            file.write(raw)

    def read_raw(self):
        '''Called the first time the file is actually accessed since the bot booted.'''
        with open(DIR(self.info.raw_file), 'r', encoding='utf-8') as file:
            return file.read()

    def process_raw(self, raw):
        '''Called either when the file is read from disk, or when the file is first uploaded.'''
        lines = [x.strip() for x in re.split(self.info.splitter, raw)]
        lines = list(filter(lambda x: x != '', lines))
        self.lines = lines

    def get_lines(self):
        if self.lines is None:
            self.process_raw(self.read_raw())
        return self.lines

    def _get_search_lines(self):
        # search_lines is a list of (index, searchified_line) tuples
        if self.search_lines is None:
            lines = self.get_lines()
            self.search_lines = [(i, searchify(lines[i])) for i in range(len(lines))]
        return self.search_lines

    def get_sentences(self):
        if self.sentences is not None:
            return self.sentences
        elif self.info.sentences_file is not None:
            # We've already split the file into sentences once, just read it
            with open(DIR(self.info.sentences_file), 'r', encoding='utf-8') as file:
                self.sentences = file.read().split('\n')
            return self.sentences
        else:
            # We've never sentence split this file before
            # Get the raw file and split it
            raw = self.read_raw()
            sentences = nltk.sent_tokenize(raw)
            # Sentences can still have line breaks in them, get rid of em first
            sentences = [re.sub('\n+', ' ', s) for s in sentences]
            self.sentences = sentences
            # Write them to a file
            filename = self.info.name + '__sentences.txt'
            with open(DIR(filename), 'w+', encoding='utf-8') as file:
                file.write('\n'.join(sentences))
            self.info.sentences_file = filename
            self.info.write()
            return self.sentences

    def _get_search_sentences(self):
        # search_sentences is a list of (index, searchified_line) tuples
        if self.search_sentences is None:
            sentences = self.get_sentences()
            self.search_sentences = [(i, searchify(sentences[i])) for i in range(len(sentences))]
        return self.search_sentences

    def get(self, sentences=None):
        if sentences is None: sentences = self.info.sentences
        return self.get_lines() if not sentences else self.get_sentences()

    def _search(self, query, sentences):
        '''Returns an iterable (with known length!) of INDICES that match the query (all indices if query is empty)'''
        lines = self.get(sentences)
        if query == '': return range(len(lines))

        # Extract absolute matches "of this form" from the query as "exact matches"
        a = searchify(query).split('"')
        exact = [a[i] for i in range(1, len(a), 2)]
        others = re.split('\s+', ''.join([a[i] for i in range(0, len(a), 2)]).strip())
        queries = exact + others

        search_lines = self._get_search_lines() if not sentences else self._get_search_sentences()
        results = list(filter(lambda l: all([q in l[1] for q in queries]), search_lines))
        return [r[0] for r in results]

    def get_random(self, count, query, sentences):
        indices = self._search(query, sentences)
        count = min(count, len(indices))
        indices = random.sample(indices, count)
        lines = self.get(sentences)
        return [lines[i] for i in indices]

    def get_sequential(self, count, query, sentences):
        indices = self._search(query, sentences)
        index = random.choice(indices)
        lines = self.get(sentences)
        # min ( random starting index containing index , biggest index that doesnt go out of bounds)
        index = max(0, min( index-random.randint(0, count-1) , len(lines)-count))
        return lines[index: index + count]

    def get_markov_model(self):
        if self.markov_model is not None:
            return self.markov_model
        elif self.info.markov_file is not None:
            with open(DIR(self.info.markov_file), encoding='utf-8') as file:
                self.markov_model = markovify.NewlineText.from_json(file.read())
            return self.markov_model
        else:
            # We've never made a markov model for this file before
            # Make a markov model from whatever the default line split mode is!
            sentences = '\n'.join(self.get())
            self.markov_model = markovify.NewlineText(sentences)
            filename = self.info.name + '__markov.json'
            with open(DIR(filename), 'w+', encoding='utf-8') as file:
                file.write(self.markov_model.to_json())

            self.info.markov_file = filename
            self.info.write()
            return self.markov_model

    def get_markov_lines(self, count=1, length=0):
        model = self.get_markov_model()
        if length == 0:
            return [model.make_sentence(tries=20) or '' for _ in range(count)]
        else:
            return [model.make_short_sentence(length, tries=20) or '' for _ in range(count)]



class Files:
    def __init__(self):
        self.files = {}

        for filename in os.listdir(DIR()):
            if filename[-2:] != '.p':
                continue
            file_info = pickle.load(open(DIR(filename), 'rb'))
            self.files[file_info.name] = File(file_info)

        print('%d uploaded files found!' % len(self.files))

    def _clean_name(name):
        return name[:-4] if name[-4:]=='.txt' else name

    def add_file(self, filename, content, author_name, author_id):
        name = Files._clean_name(filename)
        file = self.files[name] = File.new(name, author_name, author_id, content)
        return file

    def __contains__(self, name):
        return (Files._clean_name(name) in self.files)

    def __iter__(self):
        return (n for n in self.files)

    def __getitem__(self, name):
        return self.files[Files._clean_name(name)]

    def __setitem__(self, name, value):
        self.files[Files._clean_name(name)] = value

    def __delitem__(self, name):
        del self.files[Files._clean_name(name)]


uploads = Files()