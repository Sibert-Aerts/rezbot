import math
import textwrap

from .pipes import pipe_from_func, many_to_one, one_to_one, one_to_many, set_category
from pipes.core.signature import Par, Option, ListOf, parse_bool, regex
from utils.texttools import min_dist, case_pattern
from utils.choicetree import ChoiceTree
from resource.upload import uploads


#####################################################
#                  Pipes : STRING                   #
#####################################################
set_category('STRING')


@pipe_from_func({
    'f' : Par(str, None, 'The format string. Items of the form {0}, {1} etc. are replaced with the respective item at that index.')
})
@many_to_one
def format_pipe(input, f):
    ''' Formats inputs according to a given template. '''
    ## Due to arguments automatically being formatted as described, this pipe does nothing but return `f` as its only output.
    return [f]


@pipe_from_func
@one_to_one
def reverse_text_pipe(text):
    ''' Reverses each text string individually. '''
    return text[::-1]


@pipe_from_func
@many_to_one
def length_pipe(input):
    ''' Gives the total length in characters of all items. '''
    return [str(sum( len(text) for text in input ))]


@pipe_from_func({
    'on' : Par(regex, None, 'Pattern to split on'),
    'lim': Par(int, 0, 'Maximum number of splits. (0 for no limit)')
})
@one_to_many
def split_pipe(text, on, lim):
    '''Splits the input into multiple outputs according to a pattern.'''
    return on.split(text, maxsplit=lim)


@pipe_from_func({
    's' : Par(str, '', 'The separator inserted between two items.')
})
@many_to_one
def join_pipe(input, s):
    ''' Joins inputs into a single item, separated by the given separator. '''
    return [s.join(input)]


@pipe_from_func({
    'pattern': Par(regex, None, 'The pattern to find')
})
@one_to_many
def find_all_pipe(text, pattern):
    '''
    Extracts all pattern matches from the input.
    Only groups (parentheses) are returned, or the entire matched string if no groups are present.
    '''
    matches = pattern.findall(text)
    # matches is either a List[str] or a List[Tuple[str]] depending on the regex
    if matches and isinstance(matches[0], tuple):
        return [match for tup in matches for match in tup]
    return matches


@pipe_from_func({
    'from': Par(regex, None, 'Pattern to replace'),
    'to' : Par(str, None, 'Replacement string'),
})
@one_to_one
def sub_pipe(text, to, **kwargs):
    '''
    Substitutes regex patterns in text.
    Use \\1, \\2, ... in the `to` string to insert matched groups (parentheses) of the regex pattern.
    '''
    return kwargs['from'].sub(to, text)


DIRECTION = Option(
    'left', 'center', 'right',
    aliases={'left': ['l'], 'center': ['c'], 'right': ['r']},
    name="Direction",
)

@pipe_from_func({
    'width': Par(int, None, 'How many characters to trim each string down to.'),
    'where': Par(DIRECTION, DIRECTION.right, 'Which side to trim from: left/center/right'),
})
@one_to_one
def trim_pipe(text, width, where):
    ''' Trims input text to a certain width, discarding the rest. '''
    if where == DIRECTION.left:
        return text[-width:]
    if where == DIRECTION.right:
        return text[:width]
    if where == DIRECTION.center:
        diff = max(0, len(text)-width)
        return text[ diff//2 : -math.ceil(diff/2) ]


@pipe_from_func({
    'width': Par(int, None, 'The minimum width to pad to.'),
    'where': Par(DIRECTION, DIRECTION.right, 'Which side to pad on: left/center/right'),
    'fill' : Par(str, ' ', 'The character used to pad out the string.'),
})
@one_to_one
def pad_pipe(text, where, width, fill):
    ''' Pads input text to a certain width. '''
    if where == DIRECTION.left:
        return text.rjust(width, fill)
    if where == DIRECTION.center:
        return text.center(width, fill)
    if where == DIRECTION.right:
        return text.ljust(width, fill)


@pipe_from_func
@one_to_one
def strip_pipe(value):
    ''' Strips whitespace from the start and end of each input text. '''
    return value.strip()


WRAP_MODE = Option('dumb', 'smart')

@pipe_from_func({
    'mode' : Par(WRAP_MODE, WRAP_MODE.smart, 'How to wrap: dumb (char-by-char) or smart (on spaces).'),
    'width': Par(int, 40, 'The minimum width to pad to.')
})
@one_to_many
def wrap_pipe(text, mode, width):
    '''
    Text wraps input text.
    Split input text into multiple output lines so that each line is shorter than a given number of characters.
    '''
    if mode == WRAP_MODE.dumb:
        return [text[i:i+width] for i in range(0, len(text), width)]
    if mode == WRAP_MODE.smart:
        return textwrap.wrap(text, width)


@pipe_from_func({
    'pattern': Par(str, None, 'Case pattern to apply'),
})
def case_pipe(inputs, pattern):
    '''
    Converts the case of each input according to a pattern.

    A pattern is parsed as a sequence 4 types of actions:
    • Upper/lowercase characters (A/a) enforce upper/lowercase
    • Neutral characters (?!_-,.etc.) leave case unchanged
    • Carrot (^) swaps upper to lowercase and the other way around

    Furthermore, parentheseses will repeat that part to stretch the pattern to fit the entire input.

    Examples:
        A       Just turns the first character uppercase
        Aa      Turns the first character upper, the second lower
        A(a)    Turns the first character upper, all others lower
        A(-)A   Turns the first upper, the last lower
        ^(Aa)^  Reverses the first and last characters, AnD DoEs tHiS To tHe oNeS BeTwEeN
    '''
    return case_pattern(pattern, *inputs)


@pipe_from_func({
    'columns':    Par(str, None, 'The names of the different columns separated by commas, OR an integer giving the number of columns.'),
    'alignments': Par(ListOf(DIRECTION), 'l', 'How the columns should be aligned: l/c/r separated by commas.'),
    'sep':        Par(str, ' │ ', 'The column separator'),
    'max_width':  Par(int, 100, 'The maximum desired width the output table should have, -1 for no limit.'),
    'code_block': Par(parse_bool, True, 'If the table should be wrapped in a Discord code block (triple backticks).'),
})
@many_to_one
def table_pipe(input, columns, alignments, sep, code_block, max_width):
    '''
    Formats input as an ASCII-art table.

    If max_width is exceeded, the table will change layout to attempt to remain legible,
    at the cost of no longer strictly adhering to a proper table layout, or in extreme cases, a table layout whatsoever.
    '''
    try:
        colNames = None
        colCount = int(columns)
    except:
        colNames = columns.split(',')
        colCount = len(colNames)

    if colCount <= 0:
        raise ValueError('Number of columns should be at least 1.')
    # Pad out the list of alignments with itself
    alignments = alignments * math.ceil( colCount/len(alignments) )

    # `table` is a list of lists of strings: `entry = table[row][column]`
    table = [ input[i:i+colCount] for i in range(0, len(input), colCount) ]
    # Pad out the last row with empty strings
    table[-1] += [''] * (colCount - len(table[-1]))

    ## Calculate the desired width of each column
    colWidths = [ max(len(row[i]) for row in table) for i in range(colCount) ]
    if colNames:
        colWidths = [ max(w, len(name)) for (w, name) in zip(colWidths, colNames) ]

    formatWidth = len(sep)*(colCount-1) + 2
    tableWidth = sum(colWidths) + formatWidth

    def pad(text, width, where, what=' '):
        if where is DIRECTION.left: return text.ljust(width, what)
        if where is DIRECTION.center: return text.center(width, what)
        if where is DIRECTION.right: return text.rjust(width, what)

    if tableWidth <= max_width:
        ### BEST CASE: The ideal table lay-out fits within the max_width.
        rows = [ ' %s ' % sep.join( pad(row[i], colWidths[i], alignments[i]) for i in range(colCount) ) for row in table ]
        if colNames:
            rows = [ '_%s_' % sep.replace(' ', '_').join([ pad(colNames[i], colWidths[i], alignments[i], '_') for i in range(colCount) ]) ] + rows

    else:
        minRowWidths = [ sum(len(cell) for cell in row) + formatWidth for row in table ]
        minNamesWidth = 0 if not colNames else sum(len(name) for name in colNames) + formatWidth
        altTableWidth = max(minNamesWidth, max(minRowWidths))

        if max_width < 0 or altTableWidth <= max_width:
            ### OK CASE: Each row individually does fit within the max_width.
            # So we'll lay out each row 'individually', ruining the table alignment,
            #   but we do pad the cells so that the rows are at least equal in length.
            # "TODO": Is there some smarter way to pad those cells to try and preserve bits of grid-like structure?

            def w(n, m, i):
                ''' w equally distributes the spare width `n` over `m` different cells indexed `i` '''
                return n//m if i >= (n%m) else math.ceil(n/m)

            def pad2(text, extra, where, what=' '):
                if where is DIRECTION.left: return text.ljust(len(text) + extra, what)
                if where is DIRECTION.center: return text.center(len(text) + extra, what)
                if where is DIRECTION.right: return text.rjust(len(text) + extra, what)

            rows = []
            if colNames:
                room = altTableWidth-minNamesWidth
                s = [ pad2(colNames[i], w(room, colCount, i), alignments[i], '_') for i in range(colCount) ]
                rows.append('_%s_' % sep.replace(' ', '_').join(s))

            for r in range(len(table)):
                room = altTableWidth-minRowWidths[r]
                s = [ pad2(table[r][i], w(room, colCount, i), alignments[i], ' ') for i in range(colCount) ]
                rows.append(' %s ' % sep.join(s))

        else:
            ### BAD CASE: There are rows which even individually are simply too wide to fit the max_width.
            # So we simply lay out each row's entries one after the other, with different rows separated with a horizontal line
            if colNames: namesWidth = max(len(name) for name in colNames)
            rows = []
            for row in table:
                if colNames:
                    rows += [ pad(colNames[i], namesWidth, DIRECTION.right) + ': ' + row[i] for i in range(len(colNames)) ]
                else:
                    rows += row
                rows.append('─' * max_width)
            del rows[-1]

    return [ ('```\n%s\n```' if code_block else '%s') % '\n'.join(rows) ]


class MapType:
    ''' Type used as argument for the map pipe. '''
    def __init__(self, text: str):
        self.map = {}
        self.caseMap = {}
        self.invMap = {}
        self.invCaseMap = {}
        for entry in text.split(','):
            key, val = entry.split(':', 1)
            self.map[key] = val
            self.caseMap[key.lower()] = val
            self.invMap[val] = key
            self.invCaseMap[val.lower()] = key

    def __repr__(self): return '<Map with {} entries>'.format(len(self.map))

    def get(self, key):
        return self.map[key]
    def caseGet(self, key):
        return self.caseMap[key.lower()]
    def invGet(self, key):
        return self.invMap[key]
    def invCaseGet(self, key):
        return self.invCaseMap[key.lower()]


@pipe_from_func({
    'map': Par(MapType, None, 'A sequence `key:value` entries separated by commas.'),
    'default': Par(str, None, 'The default fallback value. Leave undefined to cause an error instead.', required=False),
    'case': Par(parse_bool, False, 'If mapping should be case sensitive.'),
    'invert': Par(parse_bool, False, 'If the map should map inversely (i.e. values to keys).'),
})
@one_to_one
def map_pipe(item: str, map: MapType, case: bool, invert: bool, default: str):
    '''
    Map specific items to specific other items via a literal map.

    Warning: Crudely implemented, special characters ',' and ':' cannot be escaped.
    '''
    try:
        return ((map.get if case else map.caseGet) if not invert else (map.invGet if case else map.invCaseGet))(item)
    except:
        if default is not None:
            return default
        raise KeyError('No map entry for item "{}"'.format(item))


@pipe_from_func({
    'file': Par(str, None, 'The name of the file to be matched from. >files for a list of files'),
    'min':  Par(int, 0, 'Upper limit on minimum distance (e.g. 1 to never get the same word).')
}, command=True)
@one_to_one
def nearest_pipe(text, min, file):
    ''' Replaces each item with the nearest item (by edit distance) from the given file. '''
    file = uploads[file]
    return min_dist(text, min, file.get())


@pipe_from_func({
    'random': Par(int, None, 'If given, only produces the given number of (possibly repeating) random expansions. ' \
        'If there are a large number of possible expansions and you only want a few random ones, this option is far more efficient '\
        'than simply generating all of them before randomly choosing some.',
        required=False),
})
@one_to_many
def expand_pipe(text, random):
    '''
    Expands [bracket|choice] syntax.

    e.g.
    `[Mike|Jay] likes [cat|dog[|go]]s`
    produces
    ```
    Mike likes cats
    Jay likes cats
    Mike likes dogs
    Jay likes dogs
    Mike likes doggos
    Jay likes doggos
    ```
    '''
    tree = ChoiceTree(text, parse_all=False)
    if random is None:
        return list(tree)
    else:
        return [tree.random() for i in range(random)]
