from discord.ext import commands
import re

def mins(items, key=lambda x:x, maxMin=None):
    '''
    Returns the list of all items i whose key(i) is equal to the minimum for all items.
    If maxMin is given, it pretends there are no items with key() less than maxMin.
    '''
    min_i = []
    min_k = float('inf')
    for i in items:
        k = key(i)
        if maxMin is not None and k < maxMin:
            continue
        elif k == min_k:
            min_i.append(i)
        elif k < min_k:
            min_k = k
            min_i = [i]
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