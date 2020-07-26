import discord
import re
import asyncio
from typing import List, Tuple, Optional, Any, TypeVar

from lru import LRU

from .pipes import pipes
from .sources import sources, SourceResources
from .spouts import spouts
from .macros import pipe_macros, source_macros
from .events import events
from .macrocommands import parse_macro_command
from .logger import ErrorLog
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

class ContextError(ValueError):
    '''Special error used by the Context class when a context string cannot be fulfilled.'''

class TerminalError(Exception):
    '''Special error that serves as a signal to end script execution but contains no information.'''


class ParsedPipe:
    def __init__(self, name, argstr):
        self.name = name
        self.argstr = argstr

class Pipeline:
    ''' 
        The Pipeline class parses a pipeline script into a reusable, applicable Pipeline object.
        A Pipeline is made for each script execution, for nested (parenthesised) Pipelines, and for macros.
        Its state should be immutable and comprises only two things:
            An internal representation of the script using e.g. ParsedPipes, GroupModes, Pipelines, etc.
            An ErrorLog containing warnings and errors encountered during parsing.
    '''
    def __init__(self, string):
        self.parser_errors = ErrorLog()

        ### Split the pipeline into segments (segment > segment > segment)
        segments = self.split_into_segments(string)

        ### For each segment, parse the group mode and expand the parallel pipes.
        self.parsed_segments = []
        for segment in segments:
            try:
                segment, groupMode = groupmodes.parse(segment)
            except groupmodes.GroupModeError as e:
                # Encountered a terminal error during parsing! Keep parsing anyway so we can potentially scoop up more errors.
                self.parser_errors(str(e), True)
                continue
            parallel = self.parse_segment(segment)
            self.parsed_segments.append( (groupMode, parallel) )

        ### That's as far as I'm willing to parse/pre-compile a pipeline before execution right now, but there is absolutely room for improvement.

        # NOTE: The only errors that are logged in this entire function are in groupmodes.parse,
        # which raise terminal errors that prevent the script from ever executing.
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
    wrapping_parens_regex = re.compile(r'\(((.*)\)|(.*))', re.S)

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

    rp_regex = re.compile(r'µ(\d+)µ')
    rq_regex = re.compile(r'§(\d+)§')

    def restore_parentheses(self, bereft, stolen):
        bereft = self.rp_regex.sub(lambda m: stolen[int(m[1])], bereft)
        return bereft.replace('?µ?', 'µ')

    def steal_triple_quotes(self, segment):
        '''Steals all triple quoted parts from a string and puts them in a list so we can put them back later.'''
        stolen = []
        def steal(match):
            stolen.append('"' + match[1] + '"') # TODO: turning """ into " causes undersirable consequences!
            return '§' + str(len(stolen)-1) + '§'
        segment = segment.replace('§', '!§!')
        segment = re.sub(r'(?s)"""(.*?)"""', steal, segment) # (?s) means "dot matches all"
        return segment, stolen

    def restore_triple_quotes(self, bereft, stolen):
        bereft = self.rq_regex.sub(lambda m: stolen[int(m[1])], bereft)
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
        parallel_pipes = ChoiceTree(segment, add_brackets=True).all()

        ### Parse the simultaneous pipes into a usable form: A list of (Pipeline or ParsedPipe) objects
        parsedPipes = []

        for pipe in parallel_pipes:
            ## Put the stolen triple-quoted strings and parentheses back.
            pipe = self.restore_triple_quotes(pipe, stolen_quotes)
            pipe = self.restore_parentheses(pipe, stolen_parens)
            pipe = pipe.strip()

            ## Inline pipeline: (foo > bar > baz)
            if pipe and pipe[0] == '(':
                # TODO: This regex is dumb as tits. Somehow use the knowledge from the parentheses parsing earlier instead.
                m = re.match(Pipeline.wrapping_parens_regex, pipe)
                pipeline = m[2] or m[3]
                # Immediately parse the inline pipeline
                parsePl = Pipeline(pipeline)
                self.parser_errors.steal(parsePl.parser_errors, context='braces')
                parsedPipes.append(parsePl)

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
        MAXCHARS = 10000
        chars = sum(len(i) for i in values)
        if chars > MAXCHARS and not permissions.has(message.author.id, permissions.owner):
            raise PipelineError('Attempted to process a flow of {} total characters at once, try staying under {}.'.format(chars, MAXCHARS))

    async def apply(self, values: List[str], message, parentContext=None) -> Tuple[ List[str], List[List[str]], ErrorLog, List[Any] ]:
        '''Apply the pipeline to the set of values.'''
        ## This is the big method where everything happens.

        errors = ErrorLog()
        errors.extend(self.parser_errors)
        # Turns out this code just isn't even executable due to parsing errors! abort!
        if errors.terminal:
            return None, None, errors, None

        context = Context(parentContext)
        printValues = []
        SPOUT_CALLBACKS = []
        source_processor = SourceProcessor(message)

        self.check_values(values, message)

        ### This loop iterates over the pipeline's pipes as they are applied in sequence. (first > second > third)
        for groupMode, parsedPipes in self.parsed_segments:
            newValues = []
            newPrintValues = []

            # GroupModes that mess with the items in some way add a new context layer.
            if groupMode.splits_trivially():
                pipeContext = context
            else:
                context.set(values)
                pipeContext = Context(context)

            # The group mode turns the [values], [pipes] into a list of ([values], pipe) pairs
            # For more information: Check out groupmodes.py
            ### This loop essentially iterates over the pipes as they are applied in parallel. ( [first|second|third] )
            for vals, pipe in groupMode.apply(values, parsedPipes):
                pipeContext.set(vals)

                ## CASE: `None` is the group mode's way of leaving these values untouched
                if pipe is None:
                    newValues.extend(vals)
                    continue

                ## CASE: The pipe is an inline pipeline (recursion!)
                if type(pipe) is Pipeline:
                    pipeline = pipe
                    vals, pl_printValues, pl_errors, pl_SPOUT_CALLBACKS = await pipeline.apply(vals, message, pipeContext)
                    newValues.extend(vals)
                    errors.extend(pl_errors, 'braces')
                    SPOUT_CALLBACKS += pl_SPOUT_CALLBACKS
                    continue

                ## CASE: The pipe is given as a name followed by string of arguments
                name = pipe.name
                args = pipe.argstr

                #### Argstring preprocessing
                # Evaluate sources and insert context into the arg string
                args = await source_processor.evaluate_composite_source(args, pipeContext)
                errors.steal(source_processor.errors, context='args for `{}`'.format(name))
                # Cut script execution short by returning only the error log (I don't love this approach)
                if errors.terminal: return None, None, errors, None
                # Handle context's ignoring/filtering of values depending on their use in the argstring
                ignored, vals = pipeContext.get_ignored_filtered()
                newValues.extend(ignored)

                #### Resolve the pipe's name, in order:

                ## NO OPERATION
                if name in ['', 'nop']:
                    newValues.extend(vals)

                ## HARDCODED 'PRINT' SPOUT (TODO: GET RID OF THIS)
                elif name == 'print':
                    newPrintValues.extend(vals)
                    newValues.extend(vals)
                    SPOUT_CALLBACKS.append(spouts['print'](vals, args))

                ## A NATIVE PIPE
                elif name in pipes:
                    try:
                        newValues.extend(pipes[name](vals, args))
                    except Exception as e:
                        errors('Failed to process pipe `{}` with args "{}":\n\t{}: {}'.format(name, args, e.__class__.__name__, e))
                        newValues.extend(vals)

                ## A SPOUT
                elif name in spouts:
                    # As a rule, spouts do not affect the values
                    newValues.extend(vals)
                    # Queue up the spout for side-effects
                    try:
                        SPOUT_CALLBACKS.append(spouts[name](vals, args))
                    except Exception as e:
                        errors('Failed to process spout `{}` with args "{}":\n\t{}: {}'.format(name, args, e.__class__.__name__, e))

                ## A MACRO PIPE
                elif name in pipe_macros:
                    code = pipe_macros[name].apply_args(args)
                    ## Load the cached pipeline if we already parsed this code once before
                    if code in pipe_macros.pipeline_cache:
                        macro = pipe_macros.pipeline_cache[code]
                    else:
                        macro = Pipeline(code)
                        pipe_macros.pipeline_cache[code] = macro

                    newvals, macro_printValues, macro_errors, macro_SPOUT_CALLBACKS = await macro.apply(vals, message)
                    newValues.extend(newvals)
                    errors.extend(macro_errors, name)
                    # TODO: what to do here?
                    SPOUT_CALLBACKS += macro_SPOUT_CALLBACKS

                ## A SOURCE
                elif name in sources or name in source_macros:
                    # Sources don't accept input values: Discard them but warn about it if it's a nonzero amount being discarded.
                    # This is just a style warning, if it turns out this is an annoying warning to prevent then just remove this bit...
                    if vals:
                        errors('Source-as-pipe `{}` received nonempty input; either use all items as arguments or explicitly `remove` unneeded items.'.format(name))

                    newVals = await source_processor.evaluate_parsed_source(name, args)
                    errors.steal(source_processor.errors, context='source-as-pipe')
                    if newVals is None:
                        errors.terminal = True
                        return None, None, errors, None
                    newValues.extend(newVals)

                ## UNKNOWN NAME
                else:
                    errors('Unknown pipe `{}`.'.format(name))
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
        # LRU cache holding up to 40 items... probably don't need any more
        self.script_cache = LRU(40)
        SourceResources.bot = bot

    async def on_message(self, message):
        '''Check if an incoming message triggers any custom Events.'''
        for event in events.values():
            m = event.test(message)
            if m:
                if m is not True:
                    context = Context()
                    context.items = list(m.groups())
                    await self.execute_script(event.script, message, context)
                else:
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

    @staticmethod
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

    async def execute_script(self, script, message, context=None):
        errors = ErrorLog()

        ### STEP 0: PRE-PROCESSING
        ## Check if we have executed this exact script recently
        if script in self.script_cache:
            # Fetch the previous pre-processing results from cache
            source, pipeline = self.script_cache[script]
        else:
            # Perform very safe, basic pre-processing (parsing) and cache it
            source, pipeline = PipelineProcessor.split(script)
            pipeline = Pipeline(pipeline)
            self.script_cache[script] = (source, pipeline)

        try:
            ### STEP 1: GET STARTING VALUES FROM SOURCE
            source_processor = SourceProcessor(message)
            values = await source_processor.evaluate(source, context)
            errors.extend(source_processor.errors)

            ### STEP 2: APPLY THE PIPELINE TO THE STARTING VALUES
            values, printValues, pl_errors, SPOUT_CALLBACKS = await pipeline.apply(values, message, context)
            errors.extend(pl_errors)
            if errors.terminal: raise TerminalError()

            ### STEP 3: (MUMBLING INCOHERENTLY)

            ## Put the thing there
            SourceResources.previous_pipeline_output = values

            ## Print the output!
            # TODO: ~~SPOUT CALLBACK HAPPENS HERE~~
            # TODO: auto-print if the LAST output was not a spout of any kind
            if not SPOUT_CALLBACKS or any( callback is spouts['print'].function for (callback, _, _) in SPOUT_CALLBACKS ):
                # TODO: `print` as a spout?! could it be???????
                printValues.append(values)
                await self.print(message.channel, printValues)

            for callback, args, values in SPOUT_CALLBACKS:
                try:
                    await callback(self.bot, message, values, **args)
                except Exception as e:
                    errors('Failed to execute spout `{}`:\n\t{}'.format(callback.__name__, str(e)))

            ## Post warning output to the channel if any
            if errors:
                await message.channel.send(embed=errors.embed())

        except Exception as e:
            # Something terrible happened, post error output to the channel
            print('Error applying pipeline!')
            if not isinstance(e, TerminalError):
                errors('**Terminal pipeline error:**\n' + e.__class__.__name__ + ': ' + str(e), terminal=True)
            await message.channel.send(embed=errors.embed())
            raise e

    async def process_script(self, message):
        '''This is the starting point for all script execution.'''
        text = message.content

        # Test for the script prefix (pipe_prefix in config.ini, default: '>>') and remove it
        if not text.startswith(self.prefix):
            return False
        script = text[len(self.prefix):]

        ## Check if it's a script or some kind of script-like command, such as a macro or event definition

        ##### MACRO DEFINITION: (TODO: push regex down into parse_macro_command)
        # >> (NEW|EDIT|DESC) <type> <name> :: <code>
        if re.match(r'\s*(NEW|EDIT|DESC)\s+(hidden)?(pipe|source).*::', script, re.I):
            await parse_macro_command(script, message)

        ##### EVENT DEFINITION:
        elif await events.parse_command(script, message.channel):
            pass

        ##### NORMAL SCRIPT EXECUTION:
        else:
            async with message.channel.typing():
                await self.execute_script(script, message)

        return True

# This one is down below due to a circular dependency (SourceProcessor needs Pipeline and PipelineProcessor)!
from .sourceprocessor import Context, SourceProcessor