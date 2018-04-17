import re
from .pipe_decorations import sources
from .macros import source_macros
from .sources import *

# this looks like a big disgusting hamburger because it is
# matches: {source}, {source and some args}, {source args="{something}"}
_source_regex = r'{\s*([^\s}]+)\s*([^}\s](\"[^\"]*\"|[^}])*)?}'
source_regex = re.compile(_source_regex)
match_regex = re.compile(_source_regex + '$')

def is_pure_source(string):
    return re.match(match_regex, string)

def evaluate_pure_source(string, message):
    match = re.match(source_regex, string)
    sourceName, args, _ = match.groups()
    sourceName = sourceName.lower()

    if sourceName in sources:
        return sources[sourceName](message, args)
    else:
        print('Error: Unknown source ' + sourceName)
        return([match.group()])

def get_eval_fun(message):
    def eval_fun(match):
        sourceName, args, _ = match.groups()
        sourceName = sourceName.lower()

        if sourceName in sources:
            out = sources[sourceName](message, args)
            return out[0] # ye gods! how stanky!
        else:
            print('Error: Unknown source ' + sourceName)
            return(match.group())

    return eval_fun

def evaluate_all_sources(string, message):
    eval_fun = get_eval_fun(message)
    return re.sub(source_regex, eval_fun, string)

# TODO: make this work as like a test script or something haha

# def find_all_sources(string):
#     out = re.findall(source_regex, string)
#     return [o[0] if isinstance(o, tuple) else o for o in out]
#     return [' // '.join(o) if isinstance(o, tuple) else o for o in out]

# example_strings = [
#     '{words}',
#     '{words  }',
#     '{  words}',
#     '{2 words}',
#     '{words pattern=boo}',
#     '{words q="{bar}"}',
#     'foobar more like {words pattern=^foo}!',
#     'I have {roll} {words}s'
# ]

# for example in example_strings:
#     all = find_all_sources(example)
#     eval = evaluate_all_sources(example, None)
#     print(example + '\t→ ' + eval)
#     print()