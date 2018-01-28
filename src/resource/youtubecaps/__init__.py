import requests
import os
import random
import youtube_dl
from webvtt import WebVTT


def _SUBSDIR(filename=''):
    return os.path.join(os.path.join(os.path.dirname(__file__), 'subs'), filename)

def make_filename(id, title): return id + '=' + title + '.vtt'
def parse_filename(filename): return filename[:-4].split('=', 1)

ydl = youtube_dl.YoutubeDL({'outtmpl': '%(id)s%(ext)s',
    'noplaylist': True,
    'writesubtitles': True, 'writeautomaticsub': True,
    'allsubtitles': False, 'subtitleslangs': ['en'], 'subtitlesformat':'vtt' # These options dont seem to work...
})

def download_subs(url):
    result = ydl.extract_info(url, download=False)

    if 'entries' in result:
        video = result['entries'][0]
    else:
        video = result

    title = video['title']
    id = video['id']

    if 'en' in video['subtitles']:
        url = video['subtitles']['en'][1]['url']
        what = 'subtitles'
    else:
        url = video['automatic_captions']['en'][1]['url']
        what = 'automatic captions'

    print('ABAA')
    response = requests.get(url)
    vtt = response.content
    with open(_SUBSDIR(make_filename(id, title)), 'wb') as file:
        file.write(vtt)

    print('ABOO')

    load_subs_by_id_title(id, title)

    return title, what

def delete(id):
    if id not in videos: raise ValueError('Unknown id "{}"!'.format(id))
    # remove them from the loaded videos
    title = videos[id]['title']
    del videos[id]
    # delete the file
    os.remove(_SUBSDIR(id+':'+title+'.vtt'))
    return title

videos = {}

def load_subs():
    for file in os.listdir(_SUBSDIR()):
        id, title = parse_filename(file)
        videos[id] = {'caps': WebVTT().read(_SUBSDIR(file)), 'title': title}

def load_subs_by_id_title(id, title):
    videos[id] = {'caps': WebVTT().read(_SUBSDIR(make_filename(id, title))), 'title': title}

def get_random():
    id = random.choice(list(videos.keys()))
    start = random.randint(0, len(videos[id]['caps'])-3)
    caps = videos[id]['caps'][start:start+3]
    time = caps[0].start.split(':')
    time[2] = time[2].split('.')[0]
    time = '{}h{}m{}s'.format(*time)
    url = 'https://youtu.be/{}?t={}'.format(id, time)
    cap = '\n'.join(c.text for c in caps)
    return cap, url

load_subs()