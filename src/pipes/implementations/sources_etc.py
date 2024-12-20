import emoji
import random
from datetime import datetime, timezone, timedelta

from .sources import source_from_func, multi_source, set_category, with_signature
from pipes.core.signature import Par, regex, ListOf, Option

from utils.rand import choose, sample
from utils.util import format_doc
from utils.texttools import *

import python_weather


#####################################################
#                  Sources : ETC.                   #
#####################################################
set_category('ETC')

@source_from_func({
    'min': Par(int, 1, 'The minimum value'),
    'max': Par(int, 20, 'The maximum value'),
    'n'  : Par(int, 1, 'The amount of rolls')
}, command=True)
@multi_source
async def roll_source(ctx, min, max):
    '''A dice roll between min and max.'''
    return str(random.randint(min, max))


@source_from_func({
    'start': Par(int, 0, 'The starting of the range'),
    'end':   Par(int, None, 'The end of the range (not included in the range!)'),
    'step':  Par(int, 1, 'The step size')
})
async def range_source(ctx, start, end, step):
    ''' The complete range of numbers from start to end with a given step size.
    More precisely:
    The list [start, start + step, start + 2*step, ..., x ] so that x is "one step short" of reaching/passing end'''
    return list(map(str, range(start, end, step)))


@source_from_func({
    'format': Par(str, '%Y/%m/%d %H:%M:%S', 'The format, see http://strftime.org/ for syntax.'),
    'utc'   : Par(float, 0, 'The offset from UTC in hours.'),
    'timestamp': Par(int, None, 'The UNIX UTC timestamp to format, leave empty to use the current time.', required=False),
    'parse': Par(str, None, 'A datetime string to parse and reformat, leave empty to use the current time.', required=False),
    'pformat': Par(str, '%Y/%m/%d %H:%M:%S', 'The format according to which to parse `parse`.'),
})
async def datetime_source(ctx, format, utc, timestamp, parse, pformat):
    '''
    The current date and time formatted to be human readable.
    The `utc` parameter determines timezone and daylight savings offsets.
    '''
    tz = timezone(timedelta(hours=utc))
    if timestamp and parse:
        raise ValueError("Values given for both `timestamp` and `parse` arguments.")
    if timestamp:
        time = datetime.fromtimestamp(timestamp, tz)
    elif parse:
        time = datetime.strptime(parse, pformat)
        # Date is assumed UTC unless it (somehow) specifies
        if time.tzinfo is None:
            time.replace(tzinfo=timezone.utc)
        time.astimezone(tz)
    else:
        time = datetime.now(tz)
    return [time.strftime(format)]


@source_from_func({
    'utc'   : Par(float, 0, 'The offset from UTC in hours to interpret the date as being.'),
    'parse': Par(str, None, 'A datetime string to parse and reformat, leave empty to use the current time.', required=False),
    'pformat': Par(str, '%Y/%m/%d %H:%M:%S', 'The format according to which to parse `parse`.'),
    })
async def timestamp_source(ctx, utc, parse, pformat):
    '''
    A date and time as a UNIX timestamp, representing seconds since 1970/01/01 00:00:00 UTC.
    The UNIX timestamp is independent of timezones.
    '''
    tz = timezone(timedelta(hours=utc))
    if parse is not None:
        time = datetime.strptime(parse, pformat).replace(tzinfo=tz)
    else:
        time = datetime.now(tz)
    return [str(int(time.timestamp()))]


@source_from_func({
    'pattern': Par(regex, None, 'The pattern to look for', required=False),
    'n'      : Par(int, 1, 'The number of sampled words.')
}, depletable=True)
async def word_source(ctx, pattern, n):
    '''Random dictionary words, optionally matching a pattern.'''
    if pattern:
        items = [w for w in allWords if pattern.search(w)]
    else:
        items = allWords
    return sample(items, n)


EMOJI_LIST = list(emoji.EMOJI_DATA)

@source_from_func({
    'n' : Par(int, 1, 'The amount of emoji.'),
    'oldest' : Par(float, 0.6, 'How old the emoji can be, inclusive.'),
    'newest' : Par(float, 15, 'How new the emoji can be, inclusive.'),
}, command=True)
async def emoji_source(ctx, n, oldest, newest):
    '''
    Random emoji.

    For oldest/newest, float values represent "Emoji versions" as defined by the Unicode Consortium.
    '''
    emoji_list = EMOJI_LIST

    # Only filter if it's even needed
    if oldest > 0.6 or newest < 15:
        def condition(e):
            age = emoji.EMOJI_DATA[e]["E"]
            return (age >= oldest and age <= newest)
        emoji_list = list(filter(condition, emoji_list))

    return choose(emoji_list, n)


WEATHER_WHAT = Option(
    'temperature',
    'feels_like',
    'humidity',
    'pressure',
    'date',
    'timestamp',
    'country',
    'location',
    'description',
    'precipitation',
    'kind',
    'emoji',
    'ultraviolet',
    'visibility',
    'wind_direction',
    'wind_speed',
    aliases={'temperature': ['temp']},
    name='Weather Property',
    stringy=True,
)

@source_from_func(command=True)
@with_signature(
    location = Par(str, None, 'The Location.'),
    what = Par(ListOf(WEATHER_WHAT), None, 'Which properties to fetch, separated by commas.'),
)
@format_doc(options=', '.join(WEATHER_WHAT))
async def weather_source(ctx, location: str, what: list[str]):
    '''
    Current weather info for a given location.

    Available properties: {options}
    '''
    async with python_weather.Client() as client:
        weather = await client.get(location)
        res = []
        for w in what:
            if w == 'emoji':
                res.append(weather.current.kind.emoji)
            elif w == 'country':
                res.append(weather.nearest_area.country)
            elif w == 'location':
                res.append(weather.nearest_area.name)
            elif w == 'timestamp':
                res.append(str(int((weather.current.date.timestamp()))))
            else:
                res.append(str(getattr(weather.current, w)))
        return res