import os
import pickle
import requests
import random
import re

import youtube_dl
from webvtt import WebVTT

def _CAPSDIR(filename=''):
    return os.path.join(os.path.dirname(__file__), 'caps', filename)

searchify_regex = re.compile(r'[^a-z0-9\s]')

def searchify(text):
    return searchify_regex.sub('', text.lower()).strip()

# Convert a timecode string 'hh:mm:ss.µµµ' to a tuple of integers: (seconds, milliseconds)
def timecode_to_sms(code):
    hours, minutes, sms = code.split(':')
    sec, msec = sms.split('.')
    seconds = int(hours) * 3600 + int(minutes) * 60 + int(sec)
    return (int(seconds), int(msec))


class Video:
    class Cap:
        def __init__(self, time, text):
            self.time = time
            self.text = text
            self.search = searchify(text)

    def __init__(self, title, id, filename, alias=None, tags=None):
        self.title = title
        self.title_lower = title.lower()
        self.alias = alias.lower() if alias else None
        self.tags = tags or []
        self.id = id
        self.captions = []
        
        # Use WebVTT to read the captions file and parse its contents
        for cap in WebVTT().read(filename):
            startsec, startmsec = timecode_to_sms(cap.start)
            endsec, endmsec = timecode_to_sms(cap.end)

            # Clean up the messy captions:
            # Step 1: Ignore "captions" that only stay visible for <50 milliseconds
            if self.captions and (endsec*1000 + endmsec) - (startsec*1000 + startmsec) < 50:
                continue

            # Step 2: strip
            text = cap.text.strip()

            # Step 3: Remove the previous caption piggybacking on the start of the next caption
            if self.captions:
                prevtext = self.captions[-1].text
                # I think this check always passes, but it's there for prudence's sake.
                if prevtext == text[:len(prevtext)]:
                    text = text[len(prevtext):].strip()

            # print(str(startsec) + ' : ' + text)
            self.captions.append(Video.Cap(startsec, text))

        self.write()

    def get_url(self, cap):
        return 'https://youtu.be/{}?t={}'.format(self.id, cap.time)

    def get_random(self):
        i = random.randint(0, max(0, len(self.captions)-3))
        caps = self.captions[i:i+3]
        url = self.get_url(caps[0])
        caption = '\n'.join(c.text for c in caps)
        return caption, url

    def search(self, query, amount=1):
        # TODO: This is copy-pasted from the dril search, make this smarter & fuzzier & put this in its own damn module
    
        # Extract absolute matches "of this form" from the query
        a = query.split('"')
        absolutes = [a[i] for i in range(1, len(a), 2)]
        others = re.split('\s+', ''.join([a[i] for i in range(0, len(a), 2)]).strip())
        queries = [searchify(q) for q in absolutes + others]

        # results is a list of indices of /single captions/ that match the /entire query/
        results = list(filter(lambda i: all([q in self.captions[i].search for q in queries]), range(len(self.captions))))

        # Only take a few of them
        sample = random.sample(results, min(len(results), amount))

        out = []
        for i in sample:
            start = max(0, i-1)
            url = self.get_url(self.captions[start])
            text = '\n'.join(cap.text for cap in self.captions[start : i+2])
            out.append((text, url))
        return out

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
        results = [videos[v] for v in videos if ident_lower in videos[v].title_lower or videos[v].alias is not None and ident_lower in videos[v].alias]
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

        def video_filter(video):
            return query == video.id or query_lower in [video.title_lower, video.alias] or query_lower in video.tags

        # Look for an exact match on ID, title, alias or tags
        videoResults = list(filter(video_filter, [self.videos[v] for v in self.videos]))
        if videoResults:
            print(query + ' matched ' + ', '.join(vid.title for vid in videoResults))
            video = random.choice(videoResults)
            return video.get_random()

        # The query did not relate to any specific videos: Search all known videos for matches!
        results = [result for id in self.videos for result in self.videos[id].search(query)]
        cap, url = random.choice(results)
        return cap, url

# Initialise
youtubeCaps = _YoutubeCaps(_CAPSDIR)