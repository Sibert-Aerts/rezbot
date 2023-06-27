import os
import re
import pickle
import random
from datetime import datetime

import nltk
import markovify
import spacy

from utils.util import normalize_name
spacy.LOADED_NLP = None

def DIR(filename=''):
    return os.path.join(os.path.dirname(__file__), 'files', filename)

searchify_regex = re.compile(r'[^\w-\s]')
def searchify(text):
    return searchify_regex.sub('', text.lower()).strip()


class FileInfo:
    '''Metadata class for a File. These are pickled and don't store any of the file's actual contents.'''
    def __init__(self, name, author_name, author_id, editable=False, sequential=True, sentences=False, splitter=None, categories=''):
        # File metadata:
        self.version = 2
        self.name = name
        self.author_name = author_name
        self.author_id = author_id

        self.description = None
        self.upload_date = datetime.now()
        self.last_modified = datetime.now()

        # Configuration
        self.editable = editable
        self.sentences = sentences
        self.splitter = splitter or '\n+'
        self.sequential = sequential
        self.categories = categories.upper().split(',')

        # TODO: Making some assumptions here that these are available filenames
        self.pickle_file = name + '.p'
        self.raw_file = name + '.txt'

    def write(self):
        # Write contents to a pickle file so that we can find all this info again next boot
        pickle.dump(self, open(DIR(self.pickle_file), 'wb+'))

    def delete(self):
        # Remove the pickle file, the raw file, and all created files
        for file in [self.pickle_file, self.raw_file]:
            try:
                os.remove(DIR(file))
            except:
                print('Failed to delete file "{}", it may have already been deleted.'.format(DIR(file)))

    def __repr__(self):
        return '\n'.join(str(x) for x in [self.name, self.author_name, self.author_id, self.raw_file])


class File:
    '''
    Class representing an uploaded File as it is stored in memory.
    File.info contains all metadata and is loaded on startup.
    The file's actual contents and derived contents are only read/loaded/generated the first time they're requested.
    '''
    def __init__(self, info):
        '''Constructor used when a file is loaded at startup.'''
        self.info: FileInfo = info
        # NOTE: None of these should be accessed from outside the class, use File.get_xyz() instead
        self.lines = None
        self.search_lines = None
        self.sentences = None
        self.search_sentences = None
        self.markov_model = None
        self.pos_buckets = None

    # ========================================= Life cycle =========================================
    
    @staticmethod
    def new(name, author_name, author_id, raw, **kwargs):
        '''Constructor used when a file is first created.'''
        info = FileInfo(name, author_name, author_id, **kwargs)
        info.write()
        file = File(info)
        file.process_raw(raw)
        file.write_raw(raw)
        return file

    def delete(self):
        self.info.delete()

    # ====================================== Raw file handling =====================================

    def get_raw_path(self):
        return DIR(self.info.raw_file)

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
        lines = [x for x in lines if x]
        self.lines = lines

    # ======================================== Line getters ========================================

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
        if self.sentences is None:
            # Get the raw file data, before any splitting
            raw = self.read_raw()
            sentences = nltk.sent_tokenize(raw)
            # Sentences can still have line breaks in them, get rid of em first
            self.sentences = [re.sub(r'\s*\n[\n\s]*', ' ', s) for s in sentences]
        return self.sentences

    def _get_search_sentences(self):
        # search_sentences is a list of (index, searchified_line) tuples
        if self.search_sentences is None:
            sentences = self.get_sentences()
            self.search_sentences = [(i, searchify(sentences[i])) for i in range(len(sentences))]
        return self.search_sentences

    def get(self, sentences=None):
        ''' Gets either Lines or Sentences depending on the given boolean or the default setting. '''
        if sentences is None:
            sentences = self.info.sentences
        return self.get_lines() if not sentences else self.get_sentences()

    def _search(self, sentences: bool, query=None, regex=None):
        '''Returns an indexable iterable containing the indices which match the search filters'''
        lines = self.get(sentences)

        if query:
            search_items = self._get_search_lines() if not sentences else self._get_search_sentences()

            # Extract absolute matches "of this form" from the query as "exact matches"
            a = [ searchify(s) for s in query.split('"') ]
            exact = [ a[i] for i in range(1, len(a), 2) ]
            others = re.split( '\s+', ' '.join( a[i] for i in range(0, len(a), 2) ).strip() )
            queries = exact + others

            ## Filter the items based on whether they contain every single of the queried terms
            search_items = filter( lambda item: all( q in item[1] for q in queries ), search_items )
            indices = [ r[0] for r in search_items ]

        else:
            indices = range(len(lines))

        if regex:
            regex = re.compile(regex)
            indices = list( filter( lambda i: re.search(regex, lines[i]) is not None, indices ) )

        return indices

    def get_random(self, count, sentences:bool, query=None, regex=None):
        indices = self._search(sentences, query=query, regex=regex)
        ## Nothing found: Return nothing
        if not indices: return []

        count = min(count, len(indices))
        ## Special case: We want all matching lines
        if count == -1: count = len(indices)

        indices = random.sample(indices, count)
        lines = self.get(sentences)
        return [lines[i] for i in indices]

    def get_sequential(self, count, sentences:bool, query=None, regex=None):
        indices = self._search(sentences, query=query, regex=regex)
        ## Nothing found: Return nothing
        if not indices: return []
        ## Special case: Return all lines
        if count == -1: return self.get(sentences)

        index = random.choice(indices)
        lines = self.get(sentences)
        # min ( <random starting index containing index> , <biggest index that doesnt go out of bounds> )
        index = max(0, min( index-random.randint(0, count-1) , len(lines)-count))
        return lines[index: index + count]

    # =========================================== Markov ===========================================

    def get_markov_model(self):
        if self.markov_model is None:
            # Make a markov model from whatever the default line split mode is
            sentences = '\n'.join(self.get())
            self.markov_model = markovify.NewlineText(sentences)
        return self.markov_model

    def get_markov_lines(self, count=1, length=0, start=None):
        model = self.get_markov_model()
        # Start overrides (ignores) length
        if start:
            return [model.make_sentence_with_start(start, strict=False, tries=20) or model.make_sentence_with_start(start, strict=False, test_output=False) for _ in range(count) ]
        elif length == 0:
            return [model.make_sentence(tries=20) or model.make_sentence(test_output=False) for _ in range(count)]
        else:
            return [model.make_short_sentence(length, tries=20) or model.make_sentence(length, test_output=False) for _ in range(count)]

    # ============================================= POS ============================================

    def get_pos_buckets(self):
        if self.pos_buckets is None:
            if spacy.LOADED_NLP is None: spacy.LOADED_NLP = spacy.load('en_core_web_sm')
            # TODO: Oops, this raises an error for huge input!
            doc = spacy.LOADED_NLP(' '.join(self.get_lines()))

            buckets = {}
            # buckets is {tag: {word: count}}
            for token in doc:
                if token.pos_ not in buckets:
                    buckets[token.pos_] = { token.text: 1 }
                elif token.text not in buckets[token.pos_]:
                    buckets[token.pos_][token.text] = 1
                else:
                    buckets[token.pos_][token.text] += 1

            class Bucket:
                def __init__(self, words, cum_weights):
                    self.words = words; self.cum_weights = cum_weights

            # Turn sets into tuples so we can easily sample them
            for t in buckets:
                bucket = buckets[t]
                words = tuple(bucket.keys())
                cum_weights = []
                cum = 0
                for word in words:
                    cum += bucket[word]
                    cum_weights.append(cum)
                buckets[t] = Bucket(words, cum_weights)
            self.pos_buckets = buckets
        return self.pos_buckets


class Files:
    '''
    Dict-like object containing and cataloguing all uploaded files.
    '''
    def __init__(self):
        self.files: dict[str, File] = {}

        ## Load pickled FileInfo files from the /files directory
        for filename in os.listdir(DIR()):
            if not filename.endswith('.p'):
                continue
            file_info = pickle.load(open(DIR(filename), 'rb'))

            # Upgrade v1's to v2
            if file_info.version == 1:
                file_info.version = 2
                file_info.description = None
                file_info.editable = False
                file_info.upload_date = datetime.fromtimestamp(1577836800)
                file_info.last_modified = datetime.fromtimestamp(1577836800)
                file_info.categories = []
                file_info.write()
 
            self.files[file_info.name] = File(file_info)

        print('%d uploaded files found!' % len(self.files))

    @staticmethod
    def clean_name(name):
        if name[-4:] == '.txt':
            name = name[:-4]
        return normalize_name(name)

    # ========================================== Interface =========================================

    def get_categories(self):
        ''' Get a {category: List[File]} dict. (Files may be in multiple categories!) '''
        categories = {'NONE': []}
        for file in self:
            file = self[file]
            if not file.info.categories:
                categories['NONE'].append(file)
            for cat in file.info.categories:
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(file)
        return categories

    def add_file(self, filename, content, author_name, author_id, **kwargs):
        name = Files.clean_name(filename)
        if name in self.files:
            raise ValueError('A file called `{}` already exists!'.format(name))

        file = self.files[name] = File.new(name, author_name, author_id, content, **kwargs)
        return file

    def delete_file(self, filename):
        '''Delete a file from disk.'''
        self.files[filename].delete()
        del self.files[filename]

    # ========================================= Data Model =========================================

    def __contains__(self, name):
        return (Files.clean_name(name) in self.files)

    def __iter__(self):
        return self.files.__iter__()

    def __getitem__(self, name) -> File:
        name = Files.clean_name(name)
        if not name in self.files:
            raise KeyError('No file "%s" loaded! Check >files for a list of files.' % name)
        return self.files[name]

    def __setitem__(self, name, value):
        self.files[Files.clean_name(name)] = value

    def __delitem__(self, name):
        del self.files[Files.clean_name(name)]


uploads = Files()