import json
import random
import os

class TweetHistory:
    def __init__(self, file):
        self.data = json.loads(open(file, encoding='utf-8').read())

    def random(self):
        return random.choice(self.data)

    def sample(self, amount):
        return random.sample(self.data, amount)

    def search(self, query, amount=1):
        results = list(filter(lambda t: query in t['text'], self.data))
        return random.sample(results, min(len(results), amount))

dril = TweetHistory(os.path.join(os.path.dirname(__file__), 'dril.json'))