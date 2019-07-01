from datetime import datetime
import discord
import re
import random
import asyncio

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
    def __init__(self, message):
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

    async def evaluate_parsed_source(self, name, args, n):
        '''Given the exact name, arguments and (n) of a source, evaluates it.'''
        # Try with AND without ending 's', hoping one of them is a known name!
        # So whether you write 'word' OR 'words',
        # It'll try to looking for sources named 'word' AND 'words'
        names = [name+'s', name] if name[-1] != 's' else [name[:-1], name]

        for name in names:
            if name in sources:
                ###### This is the SINGLE spot where a source's function is called during execution of pipelines
                return await sources[name](self.message, args, n=n)

            elif name in source_macros:
                code = source_macros[name].apply_args(args)
                # Dressed-down version of PipelineProcessor.execute_script:
                source, pipeline = PipelineProcessor.split(code)
                ## STEP 1
                source_processor = SourceProcessor(self.message)
                values = await source_processor.evaluate(source)
                errors = source_processor.errors
                ## STEP 2
                # TODO: REUSE: Pull these bits of parsing up or summat
                pipeline = Pipeline(pipeline)
                ## STEP 3
                values, _, pl_errors, _ = pipeline.apply(values, self.message)
                errors.extend(pl_errors)
                # TODO: Ability to reuse a script N amount of times easily?
                # Right now we just ignore the N argument....
                self.errors.extend(errors, name)
                return values
        return None

    async def evaluate_pure_source(self, source):
        '''Takes a string containing exactly one source and nothing more, a special case which allows it to produce multiple values at once.'''
        match = re.match(SourceProcessor.source_regex, source)
        n, name, args, _ = match.groups()
        name = name.lower()

        values = await self.evaluate_parsed_source(name, args, n)
        if values is not None: return values

        self.errors('Unknown source "{}".'.format(name))
        return([match.group()])

    async def evaluate_composite_source(self, source):
        '''Applies and replaces all {sources} in a string that mixes sources and normal characters.'''

        # Unwrapped re.sub myself to be able to call async functions for replacements
        out = []
        start = 0
        for match in re.finditer(SourceProcessor.source_regex, source):
            _, name, args, _ = match.groups()
            name = name.lower()

            values = await self.evaluate_parsed_source(name, args, 1) # n=1 because we only want 1 item anyway...

            if values is not None:
                value = values[0] # Only use the first output value. Is there anything else I can do here?
            else:
                self.errors('Unknown source "{}".'.format(name))

            out.append( source[start: match.start()] )
            out.append( value )
            start = match.end()
        out.append( source[start: ])
        return ''.join(out)


    async def evaluate(self, source):
        '''Takes a raw source string, expands it into multiple strings, applies {sources} in each one and returns the set of values.'''
        values = []
        if len(source) > 1 and source[0] == source[-1] == '"':
            source = source[1:-1]
        for source in ChoiceTree(source, parse_flags=True, add_brackets=True).all():
            if self.is_pure_source(source):
                values.extend(await self.evaluate_pure_source(source))
            else:
                values.append(await self.evaluate_composite_source(source))
        return values


class Pipeline:
    def __init__(self, string):
        self.parser_errors = ErrorLog()

        ### Split the pipeline into segments (segment > segment > segment)
        segments = self.split_into_segments(string)

        ### For each segment, parse the group mode and expand the parallel pipes.
        self.parsed_segments = []
        for segment in segments:
            segment, groupMode = groupmodes.parse(segment, self.parser_errors)
            parallel = self.parse_segment(segment)
            self.parsed_segments.append( (groupMode, parallel) )

        ### That's as far as I'm willing to parse/pre-compile a pipeline before execution right now, but there is absolutely room for improvement.

        # NOTE: The only errors that are logged in this entire function are in groupmodes.parse,
        # and they are nonterminal, simply warning that the default groupmode was used instead of their invalid one.
        # The other two methods (split and parse_segment) are VERY naive and VERY lenient:
        #   They take no effort to check if any of what they're parsing is even remotely well-formed or executable.
        #   If they do notice that something is wrong (e.g. unclosed quotes or parentheses) they simply ignore it.

    def split_into_segments(self, string):
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
        start = 0

        for i in range(len(string)):
            c = string[i]

            ## If quotes are open, only check for closing quotes.
            if quotes:
                ## Close quotes
                if c == '"': quotes = False

            ## Open quotes
            elif c == '"':
                quotes = True

            ## Open parentheses
            elif c == '(':
                parens += 1

            ## Close parentheses
            elif c == ')':
                if parens > 0: parens -= 1

            ## New segment
            elif parens == 0 and c == '>':
                if i > 0 and string[i-1] == '-': # The > is actually the head of a ->
                    segments.append(string[start:i-1].strip())
                    segments.append('print')
                else:
                    segments.append(string[start:i].strip())
                start = i+1 # Clip off the >

        ## Add the final segment, disregarding quotes or parentheses left open
        segments.append(string[start:].strip())
        return segments

    # Matches the first (, until either the last ) or if there are no ), the end of the string
    # Use of this regex relies on the knowledge/assumption that the nested parentheses in the string are matched
    wrapping_brackets_regex = re.compile(r'\(((.*)\)|(.*))', re.S)

    def steal_parentheses(self, segment):
        '''Steals all (intelligently-parsed) parentheses-wrapped parts from a string and puts them in a list so we can put them back later.'''
        ## Prepare the segment for Magic
        # Pretty sure the magic markers don't need to be different from the triple quote ones, but it can't hurt so why not haha
        segment = segment.replace('µ', '?µ?')

        # Parsing loop similar to the one in split_into_segments.
        # NOTE: So why not combine the two into one? Well, I tried, but BETWEEN splitting into segments and stealing parentheses
        # we have to consume the group mode from each segment! Which is hard to squeeze in here! Especially since one group mode also uses parentheses!!!
        stolen = []
        bereft = ''

        quotes = False
        parens = 0
        start = 0

        for i in range(len(segment)):
            c = segment[i]

            ## If we're in quotes: ONLY look for closing quotes.
            if quotes:
                ## Open quotes
                if c == '"': quotes = False
            ## Close quotes
            elif c == '"': quotes = True

            ## Open parentheses
            elif c == '(':
                parens += 1
                ## This '(' opens a top level parenthesis: Start stealing it.
                if parens == 1:
                    ## Leave behind a Magic Marker in its place, and remember where it started
                    bereft += segment[start:i] + 'µ' + str(len(stolen)) + 'µ'
                    start = i

            ## Close parentheses
            elif c == ')':
                if parens > 0:
                    parens -= 1
                    ## This ')' closes a top-level parenthesis: Complete stealing it.
                    if parens == 0:
                        ## Add the portion to our spoils, and continue from there.
                        stolen.append( segment[start:i+1] )
                        start = i+1

        ## Parentheses weren't closed before the segment (and thus also the script) ended: Pretend they were closed.
        if parens > 0: stolen.append(segment[start:])
        ## Parentheses were closed: Just add the last bit of text and we're done.
        else: bereft += segment[start:]

        return bereft, stolen

    def restore_parentheses(self, bereft, stolen):
        bereft = re.sub('µ(\d+)µ', lambda m: stolen[int(m.groups()[0])], bereft)
        return bereft.replace('?µ?', 'µ')

    def steal_triple_quotes(self, segment):
        '''Steals all triple quoted parts from a string and puts them in a list so we can put them back later.'''
        stolen = []
        def steal(match):
            stolen.append('"' + match.groups()[0] + '"') # TODO: turning """ into " causes undersirable consequences!
            return '§' + str(len(stolen)-1) + '§'
        segment = segment.replace('§', '!§!')
        segment = re.sub(r'(?s)"""(.*?)"""', steal, segment) # (?s) means "dot matches all"
        return segment, stolen

    def restore_triple_quotes(self, bereft, stolen):
        bereft = re.sub('§(\d+)§', lambda m: stolen[int(m.groups()[0])], bereft)
        return bereft.replace('!§!', '§')

    def parse_segment(self, segment):
        '''Turn a single string describing one or more parallel pipes into a list of ParsedPipes or Pipelines.'''
        #### True and utter hack: Steal triple-quoted strings and parentheses wrapped strings out of the segment string.
        # This way these types of substrings are not affected by ChoiceTree expansion, because we only put them back afterwards.
        # For triple quotes: This allows us to pass string arguments containing [|] without having to escape them, which is nice to have.
        # For parentheses: This allows us to use parallel segments inside of inline pipelines, giving them a lot more power and utility.
        segment, stolen_parens = self.steal_parentheses(segment)
        segment, stolen_quotes = self.steal_triple_quotes(segment)

        # ChoiceTree expands the single string into a set of strings.
        parallel_pipes = ChoiceTree(segment, parse_flags=True, add_brackets=True).all()

        ### Parse the simultaneous pipes into a usable form: A list of (Pipeline or ParsedPipe) objects
        parsedPipes = []

        for pipe in parallel_pipes:
            ## Put the stolen triple-quoted strings and parentheses back.
            pipe = self.restore_triple_quotes(pipe, stolen_quotes)
            pipe = self.restore_parentheses(pipe, stolen_parens)

            ## Inline pipeline: (foo > bar > baz)
            if pipe and pipe[0] == '(':
                # TODO: This regex is dumb as tits. Somehow use the knowledge from the parentheses parsing earlier instead.
                m = re.match(Pipeline.wrapping_brackets_regex, pipe)
                pipeline = m.groups()[1] or m.groups()[2]
                # Immediately parse the inline pipeline
                parsedPipes.append(Pipeline(pipeline))

            ## Normal pipe: foo [bar=baz]*
            else:
                name, *args = pipe.strip().split(' ', 1)
                name = name.lower()
                args = args[0] if args else ''
                parsedPipes.append(ParsedPipe(name, args))

        return parsedPipes

    def check_values(self, values, message):
        '''Raises an error if the user is asking too much of the bot.'''
        # TODO: this could stand to be smarter/more oriented to the type of operation you're trying to do, or something, maybe...?
        # meditate on this...
        MAXCHARS = 1000
        chars = sum(len(i) for i in values)
        if chars > MAXCHARS and not permissions.has(message.author.id, permissions.owner):
            raise PipelineError('Attempted to process a flow of {} total characters at once, try staying under {}.'.format(chars, MAXVALUES))

    def apply(self, values, message):
        '''Apply the pipeline to the set of values.'''
        printValues = []
        errors = ErrorLog()
        errors.extend(self.parser_errors) # Include the errors we found during parsing!
        SPOUT_CALLBACKS = []

        self.check_values(values, message)

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
                    values, pl_printValues, pl_errors, pl_SPOUT_CALLBACKS = pipeline.apply(vals, message)
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

                    values, macro_printValues, macro_errors, macro_SPOUT_CALLBACKS = macro.apply(vals, message)
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

            self.check_values(values, message)

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
                    await dest.send(output[0][0])
                else:
                    await dest.send('`empty string`')
                return
            elif len(output[0]) == 0:
                await dest.send('`no output`')
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
        await dest.send(output)

    def split(script):
        '''Splits a script into the source and pipeline.'''
        # So here's the deal:
        #    SOURCE > PIPE > PIPE > PIPE > ETC...
        # We only need to split on the first >, but this can be escaped by wrapping the entire thing in quotes!
        #    "SOU > RCE" > PIPE
        # We want to split on the LAST pipe there... The issue is parsing this is kinda hard maybe, because of weird cases:
        #    SOU ">" RCE    or    "SOU">"RCE" ???
        # AND also: SOURCE -> PIPE should parse as SOURCE > print > PIPE
        # So I would simply like to assume people don't put enough quotes AND >'s in their texts for this to be a problem....
        # ...because what we've been doing so far is: look at quotes as non-nesting and just split on the first non-wrapped >
        # Anyway here is a neutered version of the script used to parse Pipelines.
        quoted = False
        p = None
        for i in range(len(script)):
            c = script[i]
            if c == '"': quoted ^= True; continue
            if not quoted and c =='>':
                if p == '-':
                    return script[:i-1].strip(), 'print>'+script[i+1:]
                return script[:i].strip(), script[i+1:]
            p = c
        return script.strip(), ''

    async def execute_script(self, script, message):
        source, pipeline = PipelineProcessor.split(script)
        errors = ErrorLog()

        try:
            ### STEP 1: GET STARTING VALUES FROM SOURCE
            source_processor = SourceProcessor(message)
            values = await source_processor.evaluate(source)
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
                await message.channel.send(embed=errors.embed())

        except Exception as e:
            print('Error applying pipeline!')
            errors('**Terminal pipeline error:**\n' + e.__class__.__name__ + ': ' + str(e), terminal=True)
            await message.channel.send(embed=errors.embed())

    async def process_script(self, message):
        '''This is the starting point for all script execution.'''
        text = message.content

        # Test for the script prefix (pipe_prefix in config.ini, default: '>>>')
        if not text.startswith(self.prefix):
            return False

        # Remove the prefix
        script = text[len(self.prefix):]

        # IMPROVISED EVENT SYNTAX:
        # >>>ON MESSAGE (pattern) :: (pipeline)
        if len(script) >= 2 and script[:2] == 'ON' and '::' in script:
            self.on_message_events.append(parse_event(script, message.channel))
        else:
            # NORMAL, NON-EVENT SCRIPT EXECUTION:
            await self.execute_script(script, message)
        return True

PipelineProcessor.on_message_events = []