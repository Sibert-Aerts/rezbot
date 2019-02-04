from datetime import datetime
import discord
import re
import random

from .pipes import pipes
from .sources import sources, SourceResources
from .spouts import spouts
from .macros import pipe_macros, source_macros
from .events import parse_event
import pipes.groupmodes as groupmodes
from utils.choicetree import ChoiceTree

import permissions
import utils.texttools as texttools
import utils.util as util

#################################################################
#              The classes that put it all to work              #
#################################################################

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
                self.errors[-1].count += e.count
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


class SourceProcessor:
    def __init__(self, bot, message):
        self.bot = bot
        self.message = message
        self.errors = ErrorLog()

    # this looks like a big disgusting hamburger because it is
    # matches: {source}, {source and some args}, {source args="{something}"}, {10 source}, etc.
    _source_regex = r'{\s*(\d*)\s*([^\s}]+)\s*([^}\s](\"[^\"]*\"|[^}])*)?}'
    source_regex = re.compile(_source_regex)
    source_match_regex = re.compile(_source_regex + '$')

    def is_pure_source(self, source):
        '''Checks whether a string matches the exact format "{[n] source [args]}", AKA "pure".'''
        return re.match(SourceProcessor.source_match_regex, source)

    def evaluate_parsed_source(self, name, args, n):
        '''Given the exact name, arguments and (n) of a source, evaluates it.'''
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
                # TODO: REUSE: Ability to reuse the pipeline n amount of times easily.
                values = source_pl.apply_source_and_pipeline()
                self.errors.extend(source_pl.error_log, name)
                return values
                # TODO: we throw away source_pl's printValues here, maybe they are still of use!
        return None

    def evaluate_pure_source(self, source):
        '''Takes a string containing exactly one source and nothing more, a special case which allows it to produce multiple values at once.'''
        match = re.match(SourceProcessor.source_regex, source)
        n, name, args, _ = match.groups()
        name = name.lower()

        values = self.evaluate_parsed_source(name, args, n)
        if values is not None: return values

        self.errors('Unknown source "{}".'.format(name))
        return([match.group()])

    def evaluate_composite_source(self, source):
        '''Applies and replaces all {sources} in a string that mixes sources and normal characters.'''
        def eval_fun(match):
            _, name, args, _ = match.groups()
            name = name.lower()
            values = self.evaluate_parsed_source(name, args, 1)
            if values is not None:
                return values[0] # Only use the first output value. Is there anything else I can do here?
            self.errors('Unknown source "{}".'.format(name))
            return(match.group())

        return re.sub(SourceProcessor.source_regex, eval_fun, source)

    def evaluate(self, source):
        '''Takes a raw source string, expands it into multiple strings, applies {sources} in each one and returns the set of values.'''
        values = []
        if source[0] == source[-1] == '"' and len(source) > 1:
            source = source[1:-1]
        for source in ChoiceTree(source, parse_flags=True, add_brackets=True).all():
            if self.is_pure_source(source):
                values.extend(self.evaluate_pure_source(source))
            else:
                values.append(self.evaluate_composite_source(source))
        return values


class Pipeline:
    def __init__(self, string):
        self.errors = ErrorLog()
        ### Split the pipeline into segments (segment > segment > segment)
        segments = self.split(string)
        ### For each segment, parse the group mode and expand the parallel pipes.
        self.parsed_segments = []
        for segment in segments:
            segment, groupMode = groupmodes.parse(segment, self.errors)
            parallel = self.parse_segment(segment)
            self.parsed_segments.append( (groupMode, parallel) )

    def split(self, string):
        '''
        Split the sequence of pipes (one big string) into a list of pipes (list of strings).
        Doesn't split on >'s inside quote blocks or within parentheses, and inserts "print"s on ->'s.
        '''
        # This is an extremely hand-written extremely low-level parser for the basic structure of a pipeline.
        # There are NO ESCAPE SEQUENCES. Every quotation mark is taken as one. Every parenthesis outside of quotation marks is 100% real.
        # This causes parsing inconsistencies. e.g. "foo > bar x=( > baz" only splits on the first ">"

        segments = []
        quotes = False
        parens = 0
        current = ''
        prev = ''

        for c in string:
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
                    segments.append(current[:-1].strip())
                    segments.append('print')
                else:
                    segments.append(current.strip())
                current = ''

            else:
                current += c

            prev = c

        segments.append(current.strip())
        return segments

    def check_values(self, values):
        '''Raises errors if the user is not permitted to process a certain quantity of values.'''
        # TODO: this could stand to be smarter/more oriented to the type of operation you're trying to do, or something, maybe...?
        # meditate on this...
        MAXCHARS = 1000
        chars = sum(len(i) for i in values)
        if chars > MAXCHARS and not permissions.has(self.message.author.id, permissions.owner):
            raise PipelineError('Attempted to process a flow of {} total characters at once, try staying under {}.'.format(chars, MAXVALUES))

    # Matches the first (, until either the last ) or if there are no ), the end of the string
    # Use of this regex relies on the knowledge/assumption that the nested parentheses in the string are matched
    wrapping_brackets_regex = re.compile(r'\(((.*)\)|(.*))')

    def parse_segment(self, simulpipe):
        '''Turn a single string describing one or more parallel pipes into a list of ParsedPipes or Pipelines.'''

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
                # TODO: this is bullshit, we actually smartly parse braces earlier, don't throw that info out!
                m = re.match(Pipeline.wrapping_brackets_regex, pipe)
                pipeline = m.groups()[1] or m.groups()[2]
                # Instantly parse the inline pipeline
                parsedPipes.append(Pipeline(pipeline))

            # CASE: Normal pipe: foo [bar=baz]*
            else:
                name, *args = pipe.strip().split(' ', 1)
                name = name.lower()
                args = args[0] if args else ''
                parsedPipes.append(ParsedPipe(name, args))

        return parsedPipes

    def apply(self, values, message):
        '''Apply the pipeline to the set of values.'''
        printValues = []
        errors = ErrorLog()
        SPOUT_CALLBACKS = []

        self.check_values(values)

        ### This loop iterates over the pipeline's pipes as they are applied in sequence. (first > second > third)
        for groupMode, parsedPipes in self.parsed_segments:
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
                    pipeline = pipe
                    values, printValues, pl_errors, pl_SPOUT_CALLBACKS = pipeline.apply(vals, message)
                    newValues.extend(values)
                    errors.extend(pl_errors, 'braces')
                    # TODO: consider the life long quandry of what exactly the fuck to do with the spout/print state of the inline pipeline.
                    SPOUT_CALLBACKS += pl_SPOUT_CALLBACKS
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
                        errors('Failed to process pipe "{}" with args "{}":\n\t{}: {}'.format(name, args, e.__class__.__name__, e))
                        newValues.extend(vals)

                elif name in spouts:
                    newValues.extend(vals) # spouts are a NOP on the values, and instead have side-effects.
                    try:
                        SPOUT_CALLBACKS.append(spouts[name](vals, args))
                    except Exception as e:
                        errors('Failed to process spout "{}" with args "{}":\n\t{}: {}'.format(name, args, e.__class__.__name__, e))

                elif name in pipe_macros:
                    code = pipe_macros[name].apply_args(args)
                    # TODO: REUSE: pull this line up or sommat
                    macro = Pipeline(code)

                    values, printValues, macro_errors, macro_SPOUT_CALLBACKS = macro.apply(vals, message)
                    newValues.extend(values)
                    errors.extend(macro_errors, name)
                    #TODO: ?
                    SPOUT_CALLBACKS += macro_SPOUT_CALLBACKS

                else:
                    errors('Unknown pipe "{}".'.format(name))
                    newValues.extend(vals)

            values = newValues
            if len(newPrintValues):
                printValues.append(newPrintValues)

            self.check_values(values)

        return values, printValues, errors, SPOUT_CALLBACKS


class PipelineProcessor:
    def __init__(self, bot, prefix):
        self.bot = bot
        self.prefix = prefix
        SourceResources.bot = bot
        self.on_message_events = PipelineProcessor.on_message_events

    async def on_message(self, message):
        for event in self.on_message_events:
            if event.test(message):
                await self.execute_script(event.script, message)

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

    def split(self, script):
        '''Splits a script into the source and pipeline.'''
        # So here's the deal:
        #    SOURCE > PIPE > PIPE > PIPE > ETC...
        # We only need to split on the first >, but this can be escaped by wrapping the entire thing in quotes!
        #    "SOU > RCE" > PIPE
        # We want to split on the LAST pipe there... The issue is parsing this is kinda hard maybe, because of weird cases:
        #    SOU ">" RCE    or    "SOU">"RCE" ???
        # So I would simply like to assume people don't put enough quotes AND >'s in their texts for this to be a problem....
        # ...because what we've been doing so far is: look at quotes as non-nesting and just split on the first non-wrapped >
        # Anyway here is a neutered version of the script used to parse Pipelines.
        quoted = False
        for i in range(len(script)):
            c = script[i]
            if c == '"': quoted ^= True; continue
            if not quoted and c =='>':
                return script[:i].strip(), script[i+1:]
        return script.strip(), ''

    async def execute_script(self, script, message):
        source, pipeline = self.split(script)
        errors = ErrorLog()

        try:
            ### STEP 1: GET STARTING VALUES FROM SOURCE
            source_processor = SourceProcessor(self.bot, message)
            values = source_processor.evaluate(source)
            errors.extend(source_processor.errors)
            
            ### STEP 2: PARSE THE PIPELINE
            pipeline = Pipeline(pipeline)

            ### STEP 3: APPLY THE PIPELINE TO THE STARTING VALUES
            values, printValues, pl_errors, SPOUT_CALLBACKS = pipeline.apply(values, message)
            errors.extend(pl_errors)

            ### STEP 4: (MUMBLING INCOHERENTLY)

            ## Put the thing there
            SourceResources.previous_pipeline_output = values

            ## Print the output!
            # TODO: ~~SPOUT CALLBACK HAPPENS HERE~~
            if not SPOUT_CALLBACKS:
                # TODO: `print` as a spout?! could it be???????
                printValues.append(values)
                await self.print(message.channel, printValues)
            else:
                for callback, args, values in SPOUT_CALLBACKS:
                    await callback(self.bot, message, values, **args)

            ## Print error output!
            if errors:
                await self.bot.send_message(message.channel, embed=errors.embed())

        except Exception as e:
            print('Error applying pipeline!')
            errors('**Terminal pipeline error:**\n' + e.__class__.__name__ + ': ' + str(e), terminal=True)
            await self.bot.send_message(message.channel, embed=errors.embed())

    async def process_script(self, message):
        '''This is the starting point for all script execution.'''
        text = message.content

        # Test for the script prefix (pipe_prefix in config.ini, default: '>>>')
        if not text.startswith(self.prefix):
            return False

        # Remove the prefix
        script = text[len(self.prefix):]

        # IMPROVISED EVENT SYNTAX:
        # >>> ON MESSAGE (pattern) :: (pipeline)
        if len(script) >= 2 and script[:2] == 'ON' and '::' in script:
            self.on_message_events.append(parse_event(script))
        else:
            # NORMAL, NON-EVENT SCRIPT EXECUTION:
            await self.execute_script(script, message)
        return True

PipelineProcessor.on_message_events = []