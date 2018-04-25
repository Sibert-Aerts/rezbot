from datetime import datetime
import discord
import re
import random

from .pipes import pipes
from .sources import sources, SourceResources
from .macros import pipe_macros, source_macros
import pipes.groupmodes as groupmodes
from utils.ctree import CTree

import permissions
import utils.texttools as texttools
import utils.util as util

################################################################
#              The class that puts it all to work              #
################################################################

class PipelineError(ValueError):
    '''Special error for some invalid element when processing a pipeline.'''
    pass


class ErrorLog:
    def __init__(self):
        self.errors = []
        self.terminal = False
        self.time = datetime.now().strftime('%z %c')

    class ErrorMessage:
        def __init__(self, message):
            self.count = 1
            self.message = message
        def __str__(self):
            return ('**(%d)** ' % self.count if self.count > 1 else '') + self.message

    def __call__(self, message, terminal=False):
        if self.errors and self.errors[-1].message == message:
            self.errors[-1].count += 1
        else:
            print('Error logged: ' + message)
            self.errors.append(ErrorLog.ErrorMessage(message))
        self.terminal |= terminal

    def extend(self, other, context=None):
        '''extend another error log, prepending the given 'context' for each error.'''
        for e in other.errors:
            if context is not None: e.message = '**in {}:** '.format(context) + e.message
            self.errors.append(e)

    def __bool__(self): return len(self.errors) > 0
    def __len__(self): return len(self.errors)

    def embed(self):
        desc = '\n'.join(str(m) for m in self.errors) if self.errors else 'No warnings!'
        if self.terminal:
            embed = discord.Embed(title="Error log", description=desc, color=0xff3366 if self.terminal else 0xff88)
        else:
            embed = discord.Embed(title="Warning log", description=desc, color=0xffdd33)
        embed.set_footer(text=self.time)
        return embed


class Pipeline:
    def __init__(self, pipeline:str, message):
        self.pipeline_str = pipeline
        self.message = message
        self.error_log = ErrorLog()

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
        name, args, _ = match.groups()
        name = name.lower()

        if name in sources:
            return sources[name](self.message, args)
        elif name in source_macros:
            code = source_macros[name].code
            source_pl = Pipeline(code, self.message)
            self.error_log.extend(source_pl.error_log, name)
            return source_pl.apply_source_and_pipeline()
            # TODO: we throw away source_pl's printValues here, maybe they are still of use!
        else:
            self.error_log('Unknown source "{}".'.format(name))
            return([match.group()])

    def evaluate_composite_source(self, source):
        '''Applies and replaces all {sources} in a string.'''
        def eval_fun(match):
            name, args, _ = match.groups()
            name = name.lower()
            if name in sources:
                out = sources[name](self.message, args)
                return out[0] # ye gods! how stanky!
            elif name in source_macros:
                code = source_macros[name].code
                source_pl = Pipeline(code, self.message)
                self.error_log.extend(source_pl.error_log, name)
                return source_pl.apply_source_and_pipeline()[0]
                # TODO: we throw away source_pl's printValues here, maybe they are still of use!
            else:
                self.error_log('Unknown source "{}".'.format(name))
                return(match.group())

        return re.sub(Pipeline.source_regex, eval_fun, source)

    def evaluate_source(self):
        values = []
        if self.source[:3] == '[?]':
            source = CTree.get_random(self.source[3:])
            if self.is_pure_source(source):
                values.extend(self.evaluate_pure_source(source))
            else:
                values.append(self.evaluate_composite_source(source))
        else:
            for source in CTree.get_all('[' + self.source + ']'):
                if self.is_pure_source(source):
                    values.extend(self.evaluate_pure_source(source))
                else:
                    values.append(self.evaluate_composite_source(source))
        return values

    def apply_source_and_pipeline(self):
        self.split()
        self.source = self.pipeline[0]
        self.pipeline = self.pipeline[1:]
        values = self.evaluate_source()
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
                name = split[0].lower()
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
                        self.error_log('Failed to process pipe "{}" with args "{}":\n\t{}: {}'.format(name, args, e.__class__.__name__, e))
                        newValues.extend(vals)

                elif name in pipe_macros:
                    # Apply the macro inline, as if it were a single operation
                    code = pipe_macros[name].code

                    # spicey!!!! definitely delete this entirely & pull it up into Macros!!!!!
                    def argfunc(match):
                        id = match.groups()[0].lower()
                        print('ENCOUNTERED: ', id)
                        try:
                            val = re.search(id+'=(\S+)', args).groups()[0]
                            print('FOUND VALUE ASSIGNMENT: ', val)
                            return val
                        except:
                            print('ARGUMENT NOT GIVEN, LEAVING IT.')
                            return match.group()

                    code = re.sub(r'(?i)\$([A-Z]+)\$', argfunc, code)
                    macroPipeline = Pipeline(code, self.message)
                    macroPipeline.split()
                    macroValues = macroPipeline.apply_pipeline(vals)
                    newValues.extend(macroValues)
                    self.error_log.extend(macroPipeline.error_log, name)
                    # TODO: Do something with macroPipeline.printValues

                else:
                    self.error_log('Unknown pipe "{}".'.format(name))
                    newValues.extend(vals)

            values = newValues
            if len(newPrintValues):
                self.printValues.append(newPrintValues)

            MAXVALUES = 20
            if len(values) > MAXVALUES and not permissions.has(self.message.author.id, 'owner'):
                raise PipelineError('Attempted to process {} values at once, try staying under {}.'.format(len(values), MAXVALUES))

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

            if pipeline.error_log:
                await self.bot.send_message(message.channel, embed=pipeline.error_log.embed())

        except Exception as e:
            print('Error applying pipeline!')
            print(e)
            try:
                pipeline.error_log(str(e), True)
                await self.bot.send_message(message.channel, embed=pipeline.error_log.embed())
            except:
                print('...Failed to send error log!')

        return True