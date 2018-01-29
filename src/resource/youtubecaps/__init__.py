import os
import pickle
import requests
import random
import re

import youtube_dl
from webvtt import WebVTT

def _CAPSDIR(filename=''):
    return os.path.join(os.path.dirname(__file__), 'caps', filename)

class Video:
    class Cap:
        def __init__(self, time, text):
            self.time = time
            self.text = text

    def __init__(self, title, id, filename, alias=None, tags=None):
        self.title = title
        self.title_lower = title.lower()
        self.alias = alias.lower() if alias else None
        self.tags = tags or []
        self.id = id
        self.captions = []
        
        # Use WebVTT to read the captions file and parse its contents
        for cap in WebVTT().read(filename):
            time = cap.start.split(':')
            time[2] = time[2].split('.')[0]
            time = '{}h{}m{}s'.format(*time)
            self.captions.append(Video.Cap(time, cap.text))

        self.write()

    def get_random(self):
        i = random.randint(0, max(0, len(self.captions)-3))
        caps = self.captions[i:i+3]
        url = 'https://youtu.be/{}?t={}'.format(self.id, caps[0].time)
        caption = '\n'.join(c.text for c in caps)
        return caption, url

    def write(self):
        '''Write the caps to a file.'''
        pickle.dump(self, open(_CAPSDIR(self.id+'.p'), 'wb'))

class _YoutubeCaps:
    def __init__(self, DIR):

        self.DIR = DIR

        # The youtube downloader object, responsible for downloading video information.
        self.ydl = youtube_dl.YoutubeDL({
            'noplaylist': True, 'writesubtitles': True, 'writeautomaticsub': True,
            'allsubtitles': False, 'subtitleslangs': ['en'], 'subtitlesformat':'vtt' # These options dont seem to work...
        })

        self.videos = {}

        # Load saved captions from files.
        for file in os.listdir(DIR()):
            if file[-2:] == '.p':
                video = pickle.load(open(DIR(file), 'rb'))
                self.videos[video.id] = video

    def download_subs(self, url, alias, tags, force=False):
        result = self.ydl.extract_info(url, download=False)

        if 'entries' in result:
            video = result['entries'][0]
        else:
            video = result

        title = video['title']
        id = video['id']

        if id in self.videos and not force:
            raise ValueError('that video is already loaded. try "youtube_reload [url]" if you want to overwrite previous captions.')

        # Check if it has subtitles or, lacking those, automatic captions.
        if 'en' in video['subtitles']:
            url = video['subtitles']['en'][1]['url']
            what = 'subtitles'
        elif 'en' in video['automatic_captions']:
            url = video['automatic_captions']['en'][1]['url']
            what = 'automatic captions'
        else:
            raise ValueError('that video has no english subtitles or captions.')

        # Download the captions
        response = requests.get(url)
        vtt = response.content

        # Temporarily write it to a file, because WebVTT wants that...
        tempFile = _CAPSDIR(id + '.vtt')
        with open(tempFile, 'wb') as file:
            file.write(vtt)

        # Turn it into something nicer
        video = Video(title, id, tempFile, alias, tags)
        self.videos[id] = video

        # Delete the VTT file
        os.remove(tempFile)

        return title, what


    def identify(self, identifier):
        '''Try to uniquely identify a single video based on a string, returns None if inconclusive.'''
        ident_lower = identifier.lower()
        videos = self.videos

        # By video ID
        results = [videos[v] for v in videos if videos[v].id == identifier]
        if len(results) == 1:
            return results[0]

        # By complete title/alias
        results = [videos[v] for v in videos if ident_lower in [videos[v].title_lower, videos[v].alias]]
        if len(results) == 1:
            return results[0]

        # By partial title/alias
        results = [videos[v] for v in videos if ident_lower in videos[v].title_lower or ident_lower in videos[v].alias]
        if len(results) == 1:
            return results[0]

        return None


    def delete(self, ident):
        video = self.identify(ident)
        if video is None:
            raise ValueError('"{}" does not uniquely identify a video.'.format(ident))

        # Remove it from the loaded videos
        title = video.title
        del self.videos[video.id]
        # Delete the file
        os.remove(_CAPSDIR(video.id+'.p'))

        return title


    def get_random(self):
        id = random.choice(list(self.videos.keys()))
        return self.videos[id].get_random()


    def search(self, query, amount=1):
        query_lower = query.lower()
        # TODO: Make this fuzzy

        # Extract absolute matches "of this form" from the query
        a = query_lower.split('"')
        absolutes = [a[i] for i in range(1, len(a), 2)]
        others = re.split('\s+', ''.join([a[i] for i in range(0, len(a), 2)]).strip())
        queries = absolutes + others

        def video_filter(video):
            return query == video.id or query_lower in [video.title_lower, video.alias] or query_lower in video.tags


        # Look for an exact match on ID, title, alias or tags
        videoResults = list(filter(video_filter, [self.videos[v] for v in self.videos]))
        if videoResults:
            print(query + ' matched ' + ', '.join(vid.title for vid in videoResults))
            video = random.choice(videoResults)
            return video.get_random()

        # The query did not relate to any specific videos: Search all known captions for fuzzy matches!
        # TODO
        raise NotImplementedError()
        # results = list(filter(lambda t: all([q in t['search'] for q in queries]), self.data))
        # return random.sample(results, min(len(results), amount))

# Initialise 
youtubeCaps = _YoutubeCaps(_CAPSDIR)