from enum import Enum

from .pipes import *
from .sources import *
from .pipe_decorations import pipes, sources
from .macros import pipe_macros, source_macros
import pipes.groupmodes as groupmodes

import permissions
import utils.texttools as texttools
import utils.util as util

################################################################
#              The class that puts it all to work              #
################################################################

class PipelineError(ValueError):
    '''Special error for some invalid element when processing a pipeline.'''
    pass


class Pipeline:
    def __init__(self, pipeline:str, message):
        self.pipeline_str = pipeline
        self.message = message

    def split(self):
        '''
        Split the sequence of pipes (one big string) into a list of pipes (list of strings).
        Doesn't split on >'s inside quote blocks, and inserts "print"s on ->'s.
        '''
        self.pipeline = []
        quotes = False
        current = ''
        for c in self.pipeline_str:
            if not quotes and c == '>':
                if current[-1] == '-': # the > was actually part of a ->
                    self.pipeline.append(current[:-1].strip())
                    self.pipeline.append('print')
                else:
                    self.pipeline.append(current.strip())
                current = ''
            else:
                current += c
                quotes ^= c == '"'
        self.pipeline.append(current.strip())

    # this looks like a big disgusting hamburger because it is
    # matches: {source}, {source and some args}, {source args="{something}"}
    _source_regex = r'{\s*([^\s}]+)\s*([^}\s](\"[^\"]*\"|[^}])*)?}'
    source_regex = re.compile(_source_regex)
    source_match_regex = re.compile(_source_regex + '$')

    def is_pure_source(self, source):
        return re.match(Pipeline.source_match_regex, source)

    def evaluate_pure_source(self, source):
        match = re.match(Pipeline.source_regex, source)
        sourceName, args, _ = match.groups()
        sourceName = sourceName.lower()

        if sourceName in sources:
            return sources[sourceName](self.message, args)
        elif sourceName in source_macros:
            code = source_macros[sourceName].code
            source_pl = Pipeline(code, self.message)
            return source_pl.apply_source_and_pipeline()
            # TODO: we throw away source_pl's printValues here, maybe they are still of use!
        else:
            print('Error: Unknown source ' + sourceName)
            return([match.group()])

    def evaluate_all_sources(self, source):
        '''Applies and replaces all {sources} in a string.'''
        def eval_fun(match):
            sourceName, args, _ = match.groups()
            sourceName = sourceName.lower()
            if sourceName in sources:
                out = sources[sourceName](self.message, args)
                return out[0] # ye gods! how stanky!
            elif sourceName in source_macros:
                code = source_macros[sourceName].code
                source_pl = Pipeline(code, self.message)
                return source_pl.apply_source_and_pipeline()[0]
                # TODO: we throw away source_pl's printValues here, maybe they are still of use!
            else:
                print('Error: Unknown source ' + sourceName)
                return(match.group())

        return re.sub(Pipeline.source_regex, eval_fun, source)

    def apply_source_and_pipeline(self):
        self.split()
        self.source = self.pipeline[0]
        self.pipeline = self.pipeline[1:]

        values = []

        # Determine which values we're working with.
        for source in CTree.get_all('[' + self.source + ']'):
            if self.is_pure_source(source):
                values.extend(self.evaluate_pure_source(source))
            else:
                values.append(self.evaluate_all_sources(source))

        return self.apply_pipeline(values)

    def apply_pipeline(self, values):
        '''Apply a list of pipe strings to a list of values'''
        self.printValues = []

        for bigPipe in self.pipeline:
            bigPipe, groupMode = groupmodes.parse(bigPipe)
            # print('GROUPMODE:', str(groupMode))

            # True and utter hack: Simply swipe triple-quoted strings out of the bigPipe and put them back
            # later in the expanded pipes, so that triple quotes escape all CTree expansion.
            tripleQuoteDict = {}
            def geti(): return str(random.randint(0, 999999))

            def steal_triple_quotes(match):
                i = geti()
                while i in tripleQuoteDict: i = geti()
                # Triple quotes are turned into regular quotes here, which may have unexpected consequences(?)
                tripleQuoteDict[i] = '"' + match.groups()[0] + '"'
                return '--//!!§§' + i + '§§!!//--'

            def return_triple_quotes(pipe):
                def f(m):
                    i = m.groups()[0]
                    if i in tripleQuoteDict: return tripleQuoteDict[i]
                    else: return '--//!!§§' + i + '§§!!//--'
                return re.sub(r'--//!!§§(.*?)§§!!//--', f, pipe)

            bigPipe = re.sub(r'(?s)"""(.*?)"""', steal_triple_quotes, bigPipe)

            # print('BIGPIPE:', bigPipe)
            multiPipes = CTree.get_all('[' + bigPipe + ']')

            # Parse the simultaneous pipes into a usable form: A list of {name, args}
            parsedPipes = []
            for pipe in multiPipes:
                # Put triple-quoted strings back in their positions
                pipe = return_triple_quotes(pipe)
                split = pipe.strip().split(' ', 1)
                name = split[0]
                args = ''.join(split[1:]) # split[1:] may be empty
                parsedPipes.append({'name': name, 'args': args})

            newValues = []
            newPrintValues = []

            # The group mode turns the lists of values and simultaneous pipes into tuples of values & the pipe they need to be applied to
            # For more information: Check out groupmodes.py for a long, in-depth explanation.
            for vals, pipe in groupMode.apply(values, parsedPipes):
                name = pipe['name']
                args = pipe['args']

                if name == 'print':
                    newPrintValues.extend(vals)
                    newValues.extend(vals)

                elif name in ['', 'nop']:
                    newValues.extend(vals)

                elif name in pipes:
                    try:
                        newValues.extend(pipes[name](vals, args))
                    except Exception as e:
                        print('Failed to process pipe "{}" with args "{}":\n\t{}: {}'.format(name, args, e.__class__.__name__, e))
                        newValues.extend(vals)
                        
                elif name in pipe_macros:
                    # Apply the macro inline, as if it were a single operation!
                    macroPipeline = Pipeline(pipe_macros[name].code, self.message)
                    macroPipeline.split()
                    macroValues = macroPipeline.apply_pipeline(vals)
                    newValues.extend(macroValues)
                    # TODO: Do something with macroPipeline.printValues

                else:
                    print('Error: Unknown pipe ' + name)
                    newValues.extend(vals)

            values = newValues
            if len(newPrintValues):
                self.printValues.append(newPrintValues)

            MAXVALUES = 20
            if len(values) > MAXVALUES and not permissions.has(self.message.author.id, 'owner'):
                raise PipelineError('Attempted to process {} values at once, try staying under {}'.format(len(values), MAXVALUES))

        return values


class PipelineProcessor:
    def __init__(self, bot, prefix):
        self.bot = bot
        self.prefix = prefix
        SourceResources.bot = bot

    async def print(self, dest, output):
        ''' Nicely print the output in rows and columns and even with little arrows.'''

        # Don't apply any formatting if the output is just a single row and column.
        if len(output) == 1 and len(output[0]) == 1:
            await self.bot.send_message(dest, output[0][0])
            return

        rowCount = len(max(output, key=len))
        rows = [''] * rowCount
        for c in range(len(output)):
            col = output[c]
            colWidth = len(max(col, key=len))
            for r in range(rowCount):
                if r < len(col):
                    rows[r] += col[r] + ' ' * (colWidth - len(col[r]))
                else:
                    rows[r] += ' ' * colWidth 
                try:
                    output[c+1][r]
                    rows[r] += ' → '
                except:
                    rows[r] += '   '
                    pass

        # Remove unnecessary padding
        rows = [row.rstrip() for row in rows]
        output = texttools.block_format('\n'.join(rows))
        await self.bot.send_message(dest, output)

    async def process_pipes(self, message):
        content = message.content

        # Test for the pipe command prefix (pipe_prefix in config.ini, default: '>>>')
        if not content.startswith(self.prefix): return False
        content = content[len(self.prefix):]

        pipeline = Pipeline(content, message)

        try:
            values = pipeline.apply_source_and_pipeline()
            
            SourceResources.previous_pipe_output = values

            # TODO: something happens here?
            printValues = pipeline.printValues
            printValues.append(values)
            await self.print(message.channel, printValues)

        except PipelineError as e:
            print('Error applying pipeline!')
            print(e)

        return True