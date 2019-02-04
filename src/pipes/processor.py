from datetime import datetime
import discord
import re
import random

from .pipes import pipes
from .sources import sources, SourceResources
from .spouts import spouts
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
    '''Class for logging warnings & error messages from a pipeline's execution.'''
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
        self.SPOUT_CALLBACKS = []
        self.message = message
        self.error_log = ErrorLog()
    
    def check_values(self, values):
        '''Raises errors if the user is not permitted to process a certain quantity of values.'''
        # TODO: this could stand to be smarter/more oriented to the type of operation you're trying to do, or something, maybe...?
        # meditate on this...
        MAXCHARS = 1000
        chars = sum(len(i) for i in values)
        if chars > MAXCHARS and not permissions.has(self.message.author.id, permissions.owner):
            raise PipelineError('Attempted to process a flow of {} total characters at once, try staying under {}.'.format(chars, MAXVALUES))

    def split(self):
        '''
        Split the sequence of pipes (one big string) into a list of pipes (list of strings).
        Doesn't split on >'s inside quote blocks or within parentheses, and inserts "print"s on ->'s.
        '''
        # This is an extremely hand-written extremely low-level parser for the basic structure of a pipeline.
        # There are NO ESCAPE SEQUENCES. Every quotation mark is taken as one. Every parenthesis outside of quotation marks is 100% real.
        # This causes parsing inconsistencies. e.g. "foo > bar x=( > baz" only splits on the first ">"

        self.pipeline = []
        quotes = False
        parens = 0
        current = ''
        prev = ''

        for c in self.pipeline_str:
            if quotes: # Look for an unescaped quotation mark.
                if c == '"':
                    quotes = False
                current += c

            elif c == '"':
                quotes = True
                current += c

            # elif c == '\\' and prev == '\\':
            #     current += c
            #     c = '' # Prevent this backslash from escaping the next character

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
    # matches: {source}, {source and some args}, {source args="{something}"}, {10 source}, etc.
    _source_regex = r'{\s*(\d*)\s*([^\s}]+)\s*([^}\s](\"[^\"]*\"|[^}])*)?}'
    source_regex = re.compile(_source_regex)
    source_match_regex = re.compile(_source_regex + '$')

    def is_pure_source(self, source):
        return re.match(Pipeline.source_match_regex, source)

    def evaluate_parsed_source(self, name, args, n):
        # Try with AND without ending 's', hoping one of them is a known name!
        # So whether you write 'word' OR 'words',
        # It'll try to looking for sources named 'word' AND 'words'
        names = [name+'s', name] if name[-1] != 's' else [name[:-1], name]

        for name in names:
            if name in sources:
                return sources[name](self.message, args, n=n)
            elif name in source_macros:
                code = source_macros[name].apply_args(args)
                source_pl = Pipeline(code, self.message)
                # TODO: refactor the WHOLE ENTIRE PIPELINE to be reusable so I can call it `n` times here.
                values = source_pl.apply_source_and_pipeline()
                self.error_log.extend(source_pl.error_log, name)
                return values
                # TODO: we throw away source_pl's printValues here, maybe they are still of use!
        return None

    def evaluate_pure_source(self, source):
        match = re.match(Pipeline.source_regex, source)
        n, name, args, _ = match.groups()
        name = name.lower()

        values = self.evaluate_parsed_source(name, args, n)
        if values is not None: return values

        self.error_log('Unknown source "{}".'.format(name))
        return([match.group()])

    def evaluate_composite_source(self, source):
        '''Applies and replaces all {sources} in a string.'''
        def eval_fun(match):
            _, name, args, _ = match.groups()
            name = name.lower()
            values = self.evaluate_parsed_source(name, args, 1)
            if values is not None:
                return values[0] # Only use the first output value. Is there anything else I can do here?
            self.error_log('Unknown source "{}".'.format(name))
            return(match.group())

        return re.sub(Pipeline.source_regex, eval_fun, source)

    def evaluate_source(self):
        values = []
        if self.source[0] == self.source[-1] == '"' and len(self.source) > 1:
            self.source = self.source[1:-1]
        for source in ChoiceTree(self.source, parse_flags=True, add_brackets=True).all():
            if self.is_pure_source(source):
                values.extend(self.evaluate_pure_source(source))
            else:
                values.append(self.evaluate_composite_source(source))
        return values

    # Matches the first (, until either the last ) or if there are no ), the end of the string
    # Use of this regex relies on the knowledge/assumption that the nested parentheses in the string are matched
    wrapping_brackets_regex = re.compile(r'\(((.*)\)|(.*))')

    def parse_simulpipe(self, simulpipe):
        '''Turn a single string describing one or more simultaneous pipes into a list of ParsedPipes.'''

        ### True and utter hack: Steal triple-quoted strings out of the simulpipe and put them back
        # later after expanding the choices, this way triple quotes prevent their contents from being parsed/expanded.
        stolen = []

        def steal(match):
            stolen.append('"' + match.groups()[0] + '"') # TODO: turning """ into " causes undersirable consequences!
            return '§§'

        def unsteal(pipe):
            pipe = re.sub('§§', lambda _: stolen.pop(), pipe)
            return pipe.replace('!§!', '§')

        simulpipe = simulpipe.replace('§', '!§!')
        simulpipe = re.sub(r'(?s)"""(.*?)"""', steal, simulpipe) # (?s) is just the flag for "dot matches all"
        stolen.reverse()

        # ChoiceTree expands the single string into a set of strings.
        simulpipes = ChoiceTree(simulpipe, parse_flags=True, add_brackets=True).all()

        ### Parse the simultaneous pipes into a usable form: A list of Pipeline or ParsedPipe objects
        parsedPipes = []

        for pipe in simulpipes:
            # Put the stolen triple-quoted strings back
            pipe = unsteal(pipe)

            # CASE: Inline pipeline: (foo > bar > baz)
            if pipe and pipe[0] == '(':
                m = re.match(Pipeline.wrapping_brackets_regex, pipe)
                pipe = m.groups()[1] or m.groups()[2]
                inline_pipeline = Pipeline(pipe, self.message)
                parsedPipes.append(inline_pipeline)

            # CASE: Normal pipe: foo [bar=baz]*
            else:
                name, *args = pipe.strip().split(' ', 1)
                name = name.lower()
                args = args[0] if args else ''
                parsedPipes.append(ParsedPipe(name, args))

        return parsedPipes

    def apply_pipeline(self, values):
        '''Apply the pipeline to the set of values.'''
        self.printValues = []

        ### This loop iterates over the pipeline's pipes as they are applied in sequence. (first > second > third)
        for simulpipe in self.pipeline:
            simulpipe, groupMode = groupmodes.parse(simulpipe, self.error_log)

            # TODO: REUSE: This bit of parsing happens whenever the pipeline is called; store the output instead of throwing it away.
            parsedPipes = self.parse_simulpipe(simulpipe)

            newValues = []
            newPrintValues = []

            # The group mode turns the [values], [pipes] into a list of ([values], pipe) pairs
            # For more information: Check out groupmodes.py
            ### This loop essentially iterates over the pipes as they are applied in parallel. ( [first|second|third] )
            for vals, pipe in groupMode.apply(values, parsedPipes):

                ## CASE: "None" is the group mode's way of demanding a NOP on these values.
                if pipe is None:
                    newValues.extend(vals)
                    continue

                ## CASE: The pipe is actually an inline pipeline
                if type(pipe) is Pipeline:
                    pipeline = pipe # Rename for type clarity
                    # TODO: REUSE: THIS PART HAPPENS MULTIPLE TIMES IF THE INLINE PIPELINE IS CALLED MULTIPLE TIMES...
                    # THIS DOES NOT SEEM EFFICIENT, AND MAY EVEN HAVE SOME TERRIBLE CONSEQUENCES...????!!!!!
                    pipeline.split()
                    values = pipeline.apply_pipeline(vals)
                    newValues.extend(values)
                    self.error_log.extend(pipeline.error_log, 'braces')
                    pipeline.error_log.clear()
                    # TODO: the life long quandry of what exactly the fuck to do with the spout/print state of the inline pipeline.
                    self.SPOUT_CALLBACKS += pipeline.SPOUT_CALLBACKS
                    continue

                ## CASE: The pipe is a regular pipe, given as a name and string of arguments.
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

                elif name in spouts:
                    newValues.extend(vals) # spouts are a NOP on the values, and instead provide side-effects.
                    try:
                        self.SPOUT_CALLBACKS.append(spouts[name](vals, args))
                    except Exception as e:
                        self.error_log('Failed to process spout "{}" with args "{}":\n\t{}: {}'.format(name, args, e.__class__.__name__, e))

                elif name in pipe_macros:
                    # Apply the macro inline, as if it were a single operation
                    # TODO: REUSE: lots of ways to implement reuse here, since MACROS get reused A LOT!!!!!
                    code = pipe_macros[name].apply_args(args)
                    macroPipeline = Pipeline(code, self.message)
                    macroPipeline.split()
                    macroValues = macroPipeline.apply_pipeline(vals)
                    newValues.extend(macroValues)
                    self.error_log.extend(macroPipeline.error_log, name)
                    #TODO: ?
                    self.SPOUT_CALLBACKS += macroPipeline.SPOUT_CALLBACKS

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

class OnMessage:
    def __init__(self, pattern, channel, script):
        self.pattern = pattern
        self.channel = channel
        self.script = script

    def test(self, message):
        return message.channel == self.channel and self.pattern.search(message.content) is not None

class PipelineProcessor:
    def __init__(self, bot, prefix):
        self.bot = bot
        self.prefix = prefix
        SourceResources.bot = bot
        self.on_message_conditions = PipelineProcessor.on_message_conditions

    def register_on_message(self, args, script, channel):
        regex = re.compile(args)
        tester = OnMessage(regex, channel, script)
        self.on_message_conditions.append(tester)

    async def on_message(self, message):
        for cond in self.on_message_conditions:
            if cond.test(message):
                print('A CONDITION MATCHED!')
                await self.execute_script(cond.script, message)

    async def print(self, dest, output):
        ''' Nicely print the output in rows and columns and even with little arrows.'''

        # Don't apply any formatting if the output is just a single row and column.
        if len(output) == 1:
            if len(output[0]) == 1:
                if output[0][0].strip() != '':
                    await self.bot.send_message(dest, output[0][0])
                else:
                    await self.bot.send_message(dest, '`empty string`')
                return
            elif len(output[0]) == 0:
                await self.bot.send_message(dest, '`no output`')
                return

        rowCount = len(max(output, key=len))
        rows = [''] * rowCount
        for c in range(len(output)):
            col = output[c]
            if len(col) == 0: continue
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

    async def execute_script(self, script, message):
        pipeline = Pipeline(script, message)

        try:
            #############################################
            values = pipeline.apply_source_and_pipeline()
            #############################################

            SourceResources.previous_pipeline_output = values

            ### Print the output!
            # TODO: ~~SPOUT CALLBACK HAPPENS HERE~~
            if not pipeline.SPOUT_CALLBACKS:
                # todo: print as a spout?! could it be???????
                printValues = pipeline.printValues
                printValues.append(values)
                await self.print(message.channel, printValues)
            else:
                for callback, args, values in pipeline.SPOUT_CALLBACKS:
                    await callback(self.bot, message, values, **args)

            ### Print error output!
            # TODO: Option to hide error log by default if not terminal / print it manually later if something didnt work
            if pipeline.error_log:
                await self.bot.send_message(message.channel, embed=pipeline.error_log.embed())

        except Exception as e:
            print('Error applying pipeline!')
            pipeline.error_log(e.__class__.__name__ + ': ' + str(e), terminal=True)
            await self.bot.send_message(message.channel, embed=pipeline.error_log.embed())

    async def process_pipes(self, message):
        text = message.content

        # Test for the pipeline prefix (pipe_prefix in config.ini, default: '>>>')
        if not text.startswith(self.prefix): return False
        script = text[len(self.prefix):]

        # IMPROVISED SYNTAX:
        # >>> ON MESSAGE (pattern) :: (pipeline)
        if len(script) >= 2 and script[:2] == 'ON' and '::' in script:
            ## EVENT STUFF DOWN HERE
            condition, script = script.split('::', 1)
            _, name, args = condition.split(' ', 2)
            args = args.strip()
            print('ENCOUNTERED A CONDITION: ON "{}" WITH ARGS "{}"'.format(name, args))
            if name.lower() == 'message':
                self.register_on_message(args, script, message.channel)
            # EVENT STUFF ENDS HERE
        else:
            # NORMAL, NON-EVENT SCRIPT EXECUTION:
            await self.execute_script(script, message)
        return True

PipelineProcessor.on_message_conditions = []