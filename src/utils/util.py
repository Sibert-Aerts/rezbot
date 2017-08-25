from discord.ext import commands
import re

# Gets the entire list of minimum values, rather than just the one
# With an option to set the maximum infimum
def mins(it, key=lambda x:x, maxMin=None):
    min_i = []
    min_k = 1000000000
    for i in it:
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


def get_args(ctx):
    '''Takes a Discord.py ctx object and return the message content with the first word (command name) removed.'''
    return ' '.join(ctx.message.content.split(' ')[1:])


def format_doc(**kwargs):
    '''Decorator that formats the function's docstring.'''
    def _format_doc(func):
        try:
            func.__doc__ = func.__doc__.format(**kwargs)
        except:
            pass
        return func
    return _format_doc

theSheriff = '''
⠀　　　:cowboy:
　　:100::100::100:
　:100: 　:100:　:100:
:point_down::skin-tone-3:　  :100::100:　:point_down::skin-tone-3:
　　:100:　  :100:
　　:100:　　:100:
　　 :boot:　　:boot:
'''