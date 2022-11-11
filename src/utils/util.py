from typing import List, Tuple, TypeVar

T = TypeVar('T')

def mins(items: List[T], key=None, min_min: float=None) -> List[T]:
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


def strip_command(ctx):
    '''Takes a Discord.py ctx object and return the message content with the first word (command name) removed.'''
    s = ctx.message.content.split(' ', 1)
    return s[1] if len(s) > 1 else ''

def parse_bool(s: str) -> bool:
    s = s.lower()
    if s in ['t', 'true', '1', 'y', 'yes']: return True
    if s in ['f', 'false', '0', 'n', 'no']: return False
    raise ValueError('Cannot interpret "%s" as a boolean value' % s)

def format_doc(**kwargs):
    '''Decorator that formats the function's docstring.'''
    def _format_doc(func):
        try: func.__doc__ = func.__doc__.format(**kwargs)
        except: pass
        return func
    return _format_doc

class FormatDict(dict):
    '''A dict that returns "{key}" if it does not contain an entry for "key".'''
    def __missing__(self, key):
        return '{'+key+'}'

theSheriff = '''
⠀　　　:cowboy:
　　:100::100::100:
　:100: 　:100:　:100:
:point_down::skin-tone-3:　  :100::100:　:point_down::skin-tone-3:
　　:100:　  :100:
　　:100:　　:100:
　　 :boot:　　:boot:
'''