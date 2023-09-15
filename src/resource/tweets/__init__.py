import json
import random
import os
import re

import markovify

def _HERE(filename):
    return os.path.join(os.path.dirname(__file__), filename)

class TweetHistory:
    def __init__(self, file):
        try:
            self.data = json.loads(open(file, encoding='utf-8').read())
        except:
            print('(Did not find tweet store "{}" in resource/tweets/, but no big deal!)'.format(file))
            # Dummy data not to break stuff
            self.data = [{'text':'Tweet store not found!', 'href':'https://twitter.com'}]
        for t in self.data:
            t['search'] = t['text'].lower()

    def __len__(self):
        return len(self.data)

    def random(self):
        return random.choice(self.data)

    def sample(self, amount):
        if amount == -1: amount = len(self.data)
        else: amount = min( len(self.data), amount )
        return random.sample(self.data, amount)

    def search(self, query, amount=1):
        query = query.lower()
        # TODO: Make this fuzzy

        # Extract absolute matches "of this form" from the query
        a = query.split('"')
        absolutes = [a[i] for i in range(1, len(a), 2)]
        others = re.split('\s+', ' '.join([a[i] for i in range(0, len(a), 2)]).strip())
        queries = absolutes + others

        results = list(filter(lambda t: all([q in t['search'] for q in queries]), self.data))
        if amount == -1: amount = len(results)
        else: amount = min( len(results), amount )
        return random.sample(results, min(len(results), amount))

# TODO: Load these in lazily to save memory

print('Loading tweets... ', end='')
dril = TweetHistory(_HERE('dril.json'))
print('dril: %d' % len(dril), end='')
derek = TweetHistory(_HERE('derek.json'))
print(', derek: %d' % len(derek), end='')
trump = TweetHistory(_HERE('trump.json'))
print(', trump: %d' % len(trump), end='')

if os.path.isfile(_HERE('dril-model.json')):
    with open(_HERE('dril-model.json'), encoding='utf-8') as f:
        dril_model = markovify.NewlineText.from_json(f.read())
else:
    sentences = '\n'.join(p for t in dril.data for p in re.split('[.?!][.?!\s]*',t['text']) if p != '')
    dril_model = markovify.NewlineText(sentences)
    with open(_HERE('dril-model.json'), 'w+', encoding='utf-8') as f:
        f.write(dril_model.to_json())

print(', dril model: %d' % len(dril_model.parsed_sentences), end='')
print(', done!')