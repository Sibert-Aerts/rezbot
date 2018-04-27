from datetime import datetime
import discord
import re
import random

from .pipes import pipes
from .sources import sources, SourceResources
from .macros import pipe_macros, source_macros
import pipes.groupmodes as groupmodes
from utils.choicetree import ChoiceTree

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
        self.terminal |= other.terminal
        for e in other.errors:
            if context is not None: e.message = '**in {}:** '.format(context) + e.message
            if self.errors and self.errors[-1].message == e.message:
                self.errors[-1].count += 1
            else:
                self.errors.append(e)

    def clear(self):
        self.errors = []
        self.terminal = False

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

class ParsedPipe:
    def __init__(self, name, argstr):
        self.name = name
        self.argstr = argstr

class Pipeline:
    def __init__(self, pipeline:str, message):
        self.pipeline_str = pipeline
        self.message = message
        self.error_log = ErrorLog()
    
    def check_values(self, values):
        '''Raises errors if the user is not permitted to process a certain quantity of values.'''
        MAXVALUES = 20
        if len(values) > MAXVALUES and not permissions.has(self.message.author.id, permissions.owner):
            raise PipelineError('Attempted to process {} values at once, try staying under {}.'.format(len(values), MAXVALUES))

    def split(self):
        '''
        Split the sequence of pipes (one big string) into a list of pipes (list of strings).
        Doesn't split on >'s inside quote blocks or within parentheses, and inserts "print"s on ->'s.
        '''
        self.pipeline = []
        quotes = False
        parens = 0
        current = ''
        prev = ''

        for c in self.pipeline_str:
            if quotes: # Look for an unescaped quotation mark.
                if c == '"':
                    if prev != '\\': quotes = False
                current += c

            elif c == '"':
                if prev != '\\': quotes = True
                current += c

            elif c == '\\' and prev == '\\':
                current += c
                c = '' # Prevent this backslash from escaping the next character

            elif c == '(':
                parens += 1
                current += c

            elif c == ')':
                if parens > 0: parens -= 1
                current += c

            elif parens == 0 and c == '>':
                if prev == '-': # The > was actually part of a ->
                    self.pipeline.append(current[:-1].strip())
                    self.pipeline.append('print')
                else:
                    self.pipeline.append(current.strip())
                current = ''

            else:
                current += c

            prev = c

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
        for source in ChoiceTree(self.source, parse_flags=True, add_brackets=True).all():
            if self.is_pure_source(source):
                values.extend(self.evaluate_pure_source(source))
            else:
                values.append(self.evaluate_composite_source(source))
        return values

    wrapping_brackets_regex = re.compile(r'\(((.*)\)|(.*))')

    def parse_simulpipe(self, simulpipe):
        '''Turn a single string describing one or more simultaneous pipes into a list of ParsedPipes.'''

        # True and utter hack: Simply swipe triple-quoted strings out of the simulpipe and put them back
        # later in the expanded pipes, so that triple quotes escape all ChoiceTree expansion.
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

        simulpipe = re.sub(r'(?s)"""(.*?)"""', steal_triple_quotes, simulpipe)

        simulpipes = ChoiceTree(simulpipe, parse_flags=True, add_brackets=True).all()

        # Parse the simultaneous pipes into a usable form: A list of {name, args}
        parsedPipes = []
        for pipe in simulpipes:
            # Put triple-quoted strings back in their positions
            pipe = return_triple_quotes(pipe)
            if pipe and pipe[0] == '(':
                m = re.match(Pipeline.wrapping_brackets_regex, pipe)
                pipe = m.groups()[1] or m.groups()[2]
                # print('INLINE PIPELINE: ' + pipe)
                inline_pipeline = Pipeline(pipe, self.message)
                parsedPipes.append(inline_pipeline)
            else:
                split = pipe.strip().split(' ', 1)
                name = split[0].lower()
                args = ''.join(split[1:]) # split[1:] may be empty
                parsedPipes.append(ParsedPipe(name, args))

        return parsedPipes

    def apply_pipeline(self, values):
        '''Apply a list of pipe strings to a list of values'''
        self.printValues = []

        for simulpipe in self.pipeline:
            simulpipe, groupMode = groupmodes.parse(simulpipe)
            parsedPipes = self.parse_simulpipe(simulpipe)

            newValues = []
            newPrintValues = []

            # The group mode turns the lists of values and simultaneous pipes into tuples of values & the pipe they need to be applied to
            # For more information: Check out groupmodes.py for a long, in-depth explanation.
            for vals, pipe in groupMode.apply(values, parsedPipes):
                if pipe is None: # None is a way for groupMode to convey a nop on a subset of values
                    newValues.extend(vals)
                    continue

                if type(pipe) is Pipeline:
                    pipe.split()
                    values = pipe.apply_pipeline(vals)
                    newValues.extend(values)
                    self.error_log.extend(pipe.error_log, 'braces')
                    pipe.error_log.clear()
                    continue

                name = pipe.name
                args = pipe.argstr

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
                    # def argfunc(match):
                    #     id = match.groups()[0].lower()
                    #     print('ENCOUNTERED: ', id)
                    #     try:
                    #         val = re.search(id+'=(\S+)', args).groups()[0]
                    #         print('FOUND VALUE ASSIGNMENT: ', val)
                    #         return val
                    #     except:
                    #         print('ARGUMENT NOT GIVEN, LEAVING IT.')
                    #         return match.group()

                    # code = re.sub(r'(?i)\$([A-Z]+)\$', argfunc, code)

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

            self.check_values(values)

        return values

    def apply_source_and_pipeline(self):
        self.split()
        self.source = self.pipeline[0]
        self.pipeline = self.pipeline[1:]
        values = self.evaluate_source()
        self.check_values(values)
        return self.apply_pipeline(values)


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
        text = message.content

        # Test for the pipeline prefix (pipe_prefix in config.ini, default: '>>>')
        if not text.startswith(self.prefix): return False
        text = text[len(self.prefix):]

        pipeline = Pipeline(text, message)

        try:
            #############################################
            values = pipeline.apply_source_and_pipeline()
            #############################################

            SourceResources.previous_pipeline_output = values

            ### Print the output!
            # TODO: something else happens here? maybe?
            printValues = pipeline.printValues
            printValues.append(values)
            await self.print(message.channel, printValues)

            ### Print error output!
            # TODO: Option to hide error log by default if not terminal / print it manually later if something didnt work
            if pipeline.error_log:
                await self.bot.send_message(message.channel, embed=pipeline.error_log.embed())

        except Exception as e:
            print('Error applying pipeline!')
            pipeline.error_log(str(e), terminal=True)
            await self.bot.send_message(message.channel, embed=pipeline.error_log.embed())
        return True