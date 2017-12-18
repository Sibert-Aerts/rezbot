import requests
import re
from .rand import *

# Code nicked from https://www.pluralsight.com/guides/interesting-apis/build-a-simpsons-quote-bot-with-twilio-mms-frinkiac-and-python
# when they let their guard down for a split second, and I'd do it again.

def _get_image_url(frame):
    ep = frame['Episode']
    time = frame['Timestamp']
    return 'https://frinkiac.com/meme/{}/{}.jpg'.format(ep, time)

def random():
    '''Returns a pair (image_url, caption).'''
    r = requests.get('https://frinkiac.com/api/random')
    if r.status_code != 200: raise Exception('Status code {}!'.format(r.status_code))
    json = r.json()

    # Combine each line of subtitles into one string.
    image_url = _get_image_url(json['Frame'])
    caption = '\n'.join([subtitle['Content'] for subtitle in json['Subtitles']])
    return image_url, caption

def random_image():
    return random()[0]

def random_caption():
    return random()[1]

def search_image(query):
    query = re.sub('\s+', '+', query)
    r = requests.get('https://frinkiac.com/api/search?q='+query)
    if r.status_code != 200: raise Exception('Status code {}!'.format(r.status_code))
    results = r.json()
    if len(results) == 0: raise ValueError('No results for that query!')
    # results is a list of {id, episode, timestamp} pairs, pick a random one from the 8 first results (the rest is probably bogus)
    image = choose(results[:8])
    return _get_image_url(image)

def search_caption(query):
    query = re.sub('\s+', '+', query)
    r = requests.get('https://frinkiac.com/api/search?q='+query)
    if r.status_code != 200: raise Exception('Status code {}!'.format(r.status_code))
    results = r.json()
    if len(results) == 0: raise ValueError('No results for that query!')

    # results is a list of {id, episode, timestamp} pairs, pick a random one from the 4 first results (the rest is probably bogus)
    frame = choose(results[:4])
    ep = frame['Episode']
    time = frame['Timestamp']

    # Get the caption
    r = requests.get('https://frinkiac.com/api/caption?e={}&t={}'.format(ep, time))
    if r.status_code != 200: raise Exception('Status code {}!'.format(r.status_code))
    json = r.json()
    caption = '\n'.join([subtitle['Content'] for subtitle in json['Subtitles']])
    return caption

def search(query):
    query = re.sub('\s+', '+', query)
    r = requests.get('https://frinkiac.com/api/search?q='+query)
    if r.status_code != 200: raise Exception('Status code {}!'.format(r.status_code))
    results = r.json()
    if len(results) == 0: raise ValueError('No results for that query!')

    # results is a list of {id, episode, timestamp} pairs, pick a random one from the 8 first results (the rest is probably bogus)
    frame = choose(results[:8])
    ep = frame['Episode']
    time = frame['Timestamp']

    # Get the image
    url = 'https://frinkiac.com/meme/{}/{}.jpg'.format(ep, time)

    # Get the caption
    r = requests.get('https://frinkiac.com/api/caption?e={}&t={}'.format(ep, time))
    if r.status_code != 200: raise Exception('Status code {}!'.format(r.status_code))
    json = r.json()

    caption = '\n'.join([subtitle['Content'] for subtitle in json['Subtitles']])
    return url, caption