import asyncio
import re
from typing import Awaitable, Iterable, TypeVar

T = TypeVar('T')
U = TypeVar('U')


def minima(items: list[T], key=None, min_min: float=None) -> list[T]:
    '''
    Returns the list of all items i whose key(i) is equal to the minimum for all items.
    If min_min is given, it completely ignores items whose key() are less than min_min.
    '''
    min_i = []
    min_k = None
    for i in items:
        k = i if key is None else key(i)
        if min_min is not None and k < min_min:
            continue
        elif min_k is None or k < min_k:
            min_k = k
            min_i = [i]
        elif k == min_k:
            min_i.append(i)

    return min_i


def remove_duplicates(list):
    out = []
    for l in list:
        if l not in out:
            out.append(l)
    return out


def parse_bool(s: str) -> bool:
    ''' Sensibly parse a string as a boolean value, allowing 1/0, true/false, t/f, yes/no, y/n, case insensitive. '''
    s = s.lower()
    if s in ('t', 'true', '1', 'y', 'yes'): return True
    if s in ('f', 'false', '0', 'n', 'no'): return False
    raise ValueError('Cannot interpret "%s" as a boolean value' % s)


def format_doc(**kwargs):
    '''Decorator that formats the function's docstring.'''
    def _format_doc(func):
        try: func.__doc__ = func.__doc__.format(**kwargs)
        except: pass
        return func
    return _format_doc


async def gather_dict(d: dict[T, Awaitable[U]]) -> dict[T, U]:
    '''Asyncronously turns a dict of coroutines into a dict of awaited values.'''
    return await dict_from_gather(d, d.values())


async def dict_from_gather(keys: Iterable[T], futures: Iterable[Awaitable[U]]) -> dict[T, U]:
    '''Asyncronously turns a list of keys and a list of coroutines into a dict of awaited values.'''
    values = await asyncio.gather(*futures)
    return dict(zip(keys, values))


def normalize_name(name: str):
    '''Normalizes a user-entered name to a lowercase name of only alphanumeric/underscore chars.'''
    # Cut off anything past the first space
    name = re.match('\s*(\S*)\s*', name)[1].lower()
    if not name:
        raise ValueError()
    # Squash inappropriate characters down to underscores
    name = re.sub('[^a-z0-9_]+', '_', name)
    return name


theSheriff = '''
⠀　　　:cowboy:
　　:100::100::100:
　:100: 　:100:　:100:
:point_down::skin-tone-3:　  :100::100:　:point_down::skin-tone-3:
　　:100:　  :100:
　　:100:　　:100:
　　 :boot:　　:boot:
'''