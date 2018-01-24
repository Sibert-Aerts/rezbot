import requests
import re
from .rand import *

# Code nicked from https://www.pluralsight.com/guides/interesting-apis/build-a-simpsons-quote-bot-with-twilio-mms-frinkiac-and-python
# when they let their guard down for a split second, and I'd do it again.

class _Frinkiac:
    def __init__(self, url):
        self.url = url

    def _get_image_url(self, frame):
        ep = frame['Episode']
        time = frame['Timestamp']
        return self.url + 'meme/{}/{}.jpg'.format(ep, time)

    def random(self):
        '''Returns a pair (image_url, caption).'''
        r = requests.get(self.url + 'api/random')
        if r.status_code != 200: raise Exception('Status code {}!'.format(r.status_code))
        json = r.json()

        # Combine each line of subtitles into one string.
        image_url = self._get_image_url(json['Frame'])
        caption = '\n'.join([subtitle['Content'] for subtitle in json['Subtitles']])
        return image_url, caption

    def random_image(self):
        return self.random()[0]

    def random_caption(self):
        return self.random()[1]

    def search_image(self, query):
        query = re.sub('\s+', '+', query)
        r = requests.get(self.url + 'api/search?q='+query)
        if r.status_code != 200: raise Exception('Status code {}!'.format(r.status_code))
        results = r.json()
        if len(results) == 0: raise ValueError('No results for that query!')
        # results is a list of {id, episode, timestamp} pairs, pick a random one from the 8 first results (the rest is probably bogus)
        image = choose(results[:8])
        return self._get_image_url(image)

    def search_caption(self, query):
        query = re.sub('\s+', '+', query)
        r = requests.get(self.url + 'api/search?q='+query)
        if r.status_code != 200: raise Exception('Status code {}!'.format(r.status_code))
        results = r.json()
        if len(results) == 0: raise ValueError('No results for that query!')

        # results is a list of {id, episode, timestamp} pairs, pick a random one from the 4 first results (the rest is probably bogus)
        frame = choose(results[:4])
        ep = frame['Episode']
        time = frame['Timestamp']

        # Get the caption
        r = requests.get(self.url + 'api/caption?e={}&t={}'.format(ep, time))
        if r.status_code != 200: raise Exception('Status code {}!'.format(r.status_code))
        json = r.json()
        caption = '\n'.join([subtitle['Content'] for subtitle in json['Subtitles']])
        return caption

    def search(self, query):
        query = re.sub('\s+', '+', query)
        r = requests.get(self.url + 'api/search?q='+query)
        if r.status_code != 200: raise Exception('Status code {}!'.format(r.status_code))
        results = r.json()
        if len(results) == 0: raise ValueError('No results for that query!')

        # results is a list of {id, episode, timestamp} pairs, pick a random one from the 8 first results (the rest is probably bogus)
        frame = choose(results[:8])
        ep = frame['Episode']
        time = frame['Timestamp']

        # Get the image
        url = self.url + 'meme/{}/{}.jpg'.format(ep, time)

        # Get the caption
        r = requests.get(self.url + 'api/caption?e={}&t={}'.format(ep, time))
        if r.status_code != 200: raise Exception('Status code {}!'.format(r.status_code))
        json = r.json()

        caption = '\n'.join([subtitle['Content'] for subtitle in json['Subtitles']])
        return url, caption

simpsons = _Frinkiac('https://frinkiac.com/')

futurama = _Frinkiac('https://morbotron.com/')