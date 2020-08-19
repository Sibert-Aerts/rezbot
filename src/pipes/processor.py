import discord
import re
import asyncio
from typing import List, Tuple, Optional, Any, TypeVar
from lru import LRU

# More import statements at the bottom of the file, due to circular dependencies.
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

class TerminalError(Exception):
    '''Special error that serves as a signal to end script execution but contains no information.'''


class ParsedPipe:
    # Different types of parsedpipe, determined at moment of parsing
    SPECIAL      = object()
    NATIVEPIPE   = object()
    SPOUT        = object()
    NATIVESOURCE = object()
    PIPEMACRO    = object()
    SOURCEMACRO  = object()
    UNKNOWN      = object()

    def __init__(self, pipestr:str):
        ''' Parse a string of the form `[name] [argstr]` '''
        name, *args = pipestr.strip().split(' ', 1)
        self.name = name.lower()
        self.argstr = args[0] if args else ''
        self.errors = ErrorLog()
        self.needs_dumb_arg_eval = False
        self.arguments = None   # type: Optional[Arguments]
        
        # Attempt to determine what kind of pipe it is ahead of time
        if self.name in ['', 'nop', 'print']:
            self.type = ParsedPipe.SPECIAL
        elif self.name in pipes:
            self.type = ParsedPipe.NATIVEPIPE
            self.pipe = pipes[self.name]
            self.arguments, errors = self.pipe.signature.parse_args(self.argstr)
            self.errors.extend(errors, self.name)
        elif self.name in spouts:
            self.type = ParsedPipe.SPOUT
            self.pipe = spouts[self.name]
            self.arguments, errors = self.pipe.signature.parse_args(self.argstr)
            self.errors.extend(errors, self.name)
        elif self.name in sources:
            self.type = ParsedPipe.NATIVESOURCE
            self.pipe = sources[self.name]
            self.arguments, errors = self.pipe.signature.parse_args(self.argstr)
            self.errors.extend(errors, self.name)
        elif self.name in pipe_macros:
            self.type = ParsedPipe.PIPEMACRO
            self.needs_dumb_arg_eval = True
        elif self.name in source_macros:
            self.type = ParsedPipe.SOURCEMACRO
            self.needs_dumb_arg_eval = True
        else:
            self.type = ParsedPipe.UNKNOWN
            self.needs_dumb_arg_eval = True
            # This one will keep being posted repeatedly even if the name eventually is defined, so don't do it
            # self.errors.warn(f'`{self.name}` is no known pipe, source, spout or macro at the time of parsing.')

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

        ### For each segment, parse the group mode, expand the parallel pipes and parse each parallel pipe.
        self.parsed_segments = []
        for segment in segments:
            try:
                segment, groupMode = groupmodes.parse(segment)
            except groupmodes.GroupModeError as e:
                self.parser_errors(e, True)
                # Don't attempt to parse the rest of this segment, since we aren't sure where the groupmode ends
                continue 
            parallel = self.parse_segment(segment)
            self.parsed_segments.append((groupMode, parallel))

        ### That's as far as I'm willing to parse/pre-compile a pipeline before execution right now, but there is absolutely room for improvement.

        # NOTE: The only errors that are logged in this entire function are in groupmodes.parse, and parse_segment
        # which may raise terminal errors or warnings, but we keep parsing the entire time hoping to scoop them all up at once.
        # split_into_segments on the other hand never admits any errors, and will bravely parse anything no matter how poorly formed.

    def split_into_segments(self, string):
        '''
        Split the sequence of pipes (one big string) into a list of pipes (list of strings).
        Doesn't split on >'s inside quote blocks or within parentheses, and inserts "print"s on ->'s.
        '''
        # This is an extremely hand-written extremely low-level parser for the basic structure of a pipeline.
        # There are NO ESCAPE SEQUENCES. Every quotation mark is taken as one. Every parenthesis outside of quotation marks is 100% real.
        # TODO: NOTE: This causes terrible parsing inconsistencies. e.g.    foo > bar x=( > baz     only splits on the first >

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
            stolen.append(match[0])
            return '§' + str(len(stolen)-1) + '§'
        segment = segment.replace('§', '!§!')
        segment = re.sub(r'(?s)""".*?"""', steal, segment) # (?s) means "dot matches all"
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
                # Immediately attempt to parse the inline pipeline (recursion call!)
                parsed = Pipeline(pipeline)
                self.parser_errors.steal(parsed.parser_errors, context='braces')
                parsedPipes.append(parsed)

            ## Normal pipe: foo [bar=baz]*
            else:
                parsed = ParsedPipe(pipe)
                self.parser_errors.steal(parsed.errors)
                parsedPipes.append(parsed)

        return parsedPipes

    def check_items(self, values, message):
        '''Raises an error if the user is asking too much of the bot.'''
        # TODO: this could stand to be smarter/more oriented to the type of operation you're trying to do, or something, maybe...?
        # meditate on this...
        MAXCHARS = 10000
        chars = sum(len(i) for i in values)
        if chars > MAXCHARS and not permissions.has(message.author.id, permissions.owner):
            raise PipelineError(f'Attempted to process a flow of {chars} total characters at once, try staying under {MAXCHARS}.')

    async def apply(self, items: List[str], message, parent_context=None) -> Tuple[ List[str], List[List[str]], ErrorLog, List[Any] ]:
        '''Apply the pipeline to a list of items.'''
        ## This is the big method where everything happens.

        errors = ErrorLog()
        errors.extend(self.parser_errors)
        # When a terminal error is encountered, cut script execution short and only return the error log
        # This suggestively named tuple is for such cases.
        NOTHING_BUT_ERRORS = (None, None, errors, None)

        # Turns out this pipeline just isn't even executable due to parsing errors! abort!
        if errors.terminal:
            return NOTHING_BUT_ERRORS

        # Set up some objects we'll likely need
        context = Context(parent_context)
        source_processor = SourceProcessor(message)
        printed_items = []
        spout_callbacks = []
        loose_items = items

        self.check_items(loose_items, message)

        ### This loop iterates over the pipeline's segments as they are applied in sequence. (first > second > third)
        for groupmode, parsed_pipes in self.parsed_segments:
            next_items = []
            new_printed_items = []

            # Non-trivial groupmodes add a new context layer
            if groupmode.splits_trivially():
                group_context = context
            else:
                context.set(loose_items)
                group_context = Context(context)

            ### The group mode turns the List[item], List[pipe] into  List[Tuple[ List[item], Optional[Pipe] ]]
            # i.e. it splits the list of items into smaller lists, and assigns each one a pipe to be applied to (if any).
            # The implemenation of this arcane flowchart magicke is detailed in `./groupmodes.py`
            # In the absolute simplest (and most common) case, all values are simply sent to a single pipe, and this loop iterates exactly once.
            for items, parsed_pipe in groupmode.apply(loose_items, parsed_pipes):
                group_context.set(items)

                ## CASE: `None` is how the groupmode assigns values to remain unaffected
                if parsed_pipe is None:
                    next_items.extend(items)
                    continue

                ## CASE: The pipe is itself an inlined Pipeline (recursion!)
                if isinstance(parsed_pipe, Pipeline):
                    items, pl_printValues, pl_errors, pl_spout_callbacks = await parsed_pipe.apply(items, message, group_context)
                    errors.extend(pl_errors, 'braces')
                    if errors.terminal: return NOTHING_BUT_ERRORS
                    next_items.extend(items)
                    spout_callbacks += pl_spout_callbacks
                    continue

                ## CASE: The pipe is a ParsedPipe: something of the form "name [param=arg ...]"
                name = parsed_pipe.name

                #### Determine the arguments (if needed)
                if parsed_pipe.arguments:
                    # This is a smart method that only does what is needed
                    args, arg_errors = await parsed_pipe.arguments.determine(group_context, source_processor)
                    errors.extend(arg_errors, context=name)

                elif parsed_pipe.needs_dumb_arg_eval:
                    # Evaluate sources and insert context directly into the argument string (flawed!)
                    # This is used for macros, who don't necessarily have nice Signatures that we can be smart about
                    argstr = await source_processor.evaluate_composite_source(parsed_pipe.argstr, group_context)
                    errors.steal(source_processor.errors, context=f'args for `{name}`')

                # Check if something went wrong while determining arguments
                if errors.terminal: return NOTHING_BUT_ERRORS                
                # Handle certain items being ignoring/filtering depending on their use in arguments
                ignored, items = group_context.extract_ignored()
                next_items.extend(ignored)

                ###################################################
                #### Figure out what the pipe is, this is important

                ## NO OPERATION
                if name in ['', 'nop']:
                    next_items.extend(items)
                    
                ## HARDCODED 'PRINT' SPOUT (TODO: GET RID OF THIS)
                elif name == 'print':
                    next_items.extend(items)
                    new_printed_items.extend(items)
                    spout_callbacks.append(spouts['print'](items, ''))

                ## A NATIVE PIPE
                elif parsed_pipe.type == ParsedPipe.NATIVEPIPE:
                    try:
                        next_items.extend( parsed_pipe.pipe(items, **args) )
                    except Exception as e:
                        # This mentions *all* arguments, even default ones, not all of which is very useful for error output...
                        argfmt = ' '.join( f'`{p}`={args[p]}' for p in args )
                        errors(f'Failed to process pipe `{name}` with args {argfmt}:\n\t{e.__class__.__name__}: {e}', True)
                        return NOTHING_BUT_ERRORS

                ## A SPOUT
                elif parsed_pipe.type == ParsedPipe.SPOUT:
                    # As a rule, spouts do not affect the values
                    next_items.extend(items)
                    try:
                        # Queue up the spout's side-effects instead, to be executed once the entire script has completed
                        spout_callbacks.append( parsed_pipe.pipe(items, **args) )
                    except Exception as e:
                        argfmt = ' '.join( f'`{p}`={args[p]}' for p in args )
                        errors(f'Failed to process spout `{name}` with args {argfmt}:\n\t{e.__class__.__name__}: {e}', True)
                        return NOTHING_BUT_ERRORS
                    
                ## A NATIVE SOURCE
                elif parsed_pipe.type == ParsedPipe.NATIVESOURCE:
                    # Sources don't accept input values: Discard them but warn about it if nontrivial input is being discarded.
                    # This is just a style warning, if it turns out this is annoying then it should be removed.
                    if items and not (len(items) == 1 and items[0] == ''):
                        errors(f'Source-as-pipe `{name}` received nonempty input; either use all items as arguments or explicitly `remove` unneeded items.')

                    try:
                       next_items.extend( await parsed_pipe.pipe.apply(message, args) )
                    except Exception as e:
                        argfmt = ' '.join( f'`{p}`={args[p]}' for p in args )
                        errors(f'Failed to process source-as-pipe `{name}` with args {argfmt}:\n\t{e.__class__.__name__}: {e}', True)
                        return NOTHING_BUT_ERRORS

                ## A PIPE MACRO
                elif name in pipe_macros:
                    code = pipe_macros[name].apply_args(argstr)
                    ## Load the cached pipeline if we already parsed this code once before
                    if code in pipe_macros.pipeline_cache:
                        macro = pipe_macros.pipeline_cache[code]
                    else:
                        macro = Pipeline(code)
                        pipe_macros.pipeline_cache[code] = macro

                    newvals, macro_printValues, macro_errors, macro_spout_callbacks = await macro.apply(items, message)
                    errors.extend(macro_errors, name)
                    if errors.terminal:
                        return NOTHING_BUT_ERRORS
                    next_items.extend(newvals)
                    spout_callbacks += macro_spout_callbacks

                ## A SOURCE MACRO
                elif name in sources or name in source_macros:
                    if items and not (len(items) == 1 and items[0] == ''):
                        errors(f'Macro-source-as-pipe `{name}` received nonempty input; either use all items as arguments or explicitly `remove` unneeded items.')

                    newVals = await source_processor.evaluate_parsed_source(name, argstr)
                    errors.steal(source_processor.errors, context='source-as-pipe')
                    if newVals is None or errors.terminal:
                        errors.terminal = True
                        return NOTHING_BUT_ERRORS
                    next_items.extend(newVals)

                ## UNKNOWN NAME
                else:
                    errors(f'Unknown pipe `{name}`.', True)
                    return NOTHING_BUT_ERRORS

            loose_items = next_items
            if new_printed_items:
                printed_items.append(new_printed_items)

            self.check_items(loose_items, message)

        return loose_items, printed_items, errors, spout_callbacks

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
                # If m is not just a bool, but a regex match object, fill the context up with the match groups, otherwise with the entire message.
                context = Context(items=(list(m.groups()) or [message.content]) if m is not True else [message.content])
                await self.execute_script(event.script, message, context, name='Event: ' + event.name)

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
    def split(script: str) -> Tuple[str, str]:
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

    async def execute_script(self, script, message, context=None, name=None):
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
            values, printValues, pl_errors, spout_callbacks = await pipeline.apply(values, message, context)
            errors.extend(pl_errors)
            if errors.terminal: raise TerminalError()

            ### STEP 3: (MUMBLING INCOHERENTLY)

            ## Put the thing there
            SourceResources.previous_pipeline_output = values

            ## Print the output!
            # TODO: ~~SPOUT CALLBACK HAPPENS HERE~~
            # TODO: auto-print if the LAST output was not a spout of any kind
            if not spout_callbacks or any( callback is spouts['print'].function for (callback, _, _) in spout_callbacks ):
                # TODO: `print` as a spout?! could it be???????
                printValues.append(values)
                await self.print(message.channel, printValues)

            for callback, args, values in spout_callbacks:
                try:
                    await callback(self.bot, message, values, **args)
                except Exception as e:
                    errors(f'Failed to execute spout `{callback.__name__}`:\n\t{e}')

            ## Post warning output to the channel if any
            if errors:
                await message.channel.send(embed=errors.embed(name=name))

        except TerminalError:
            ## A TerminalError indicates that whatever problem we encountered was caught, logged, and we halted voluntarily.
            # Nothing more to be done than posting log contents to the channel.
            print('Script execution halted prematurely.')
            await message.channel.send(embed=errors.embed(name=name))
            
        except Exception as e:
            ## An actual error has occurred in executing the script that we did not catch.
            # No script, no matter how poorly formed or thought-out, should be able to trigger this; if this occurs it's a Rezbot bug.
            print('Script execution halted unexpectedly!')
            errors.log('**Unexpected pipeline error:**\n' + e.__class__.__name__ + ': ' + str(e), terminal=True)
            await message.channel.send(embed=errors.embed(name=name))
            raise e

    async def process_script(self, message):
        '''This is the starting point for all script execution.'''
        text = message.content

        # Test for the script prefix and remove it (pipe_prefix in config.ini, default: '>>')
        if not text.startswith(self.prefix):
            return False
        script = text[len(self.prefix):]

        ## Check if it's a script or some kind of script-like command
        if re.match(r'\s*(NEW|EDIT|DESC).*::', script, re.I):
            ##### MACRO DEFINITION:
            # >> (NEW|EDIT|DESC) <type> <name> :: <code>
            if await parse_macro_command(script, message):
                pass
            ##### EVENT DEFINITION:
            # >> (NEW|EDIT) EVENT <name> ON MESSAGE <regex> :: <code>
            elif await events.parse_command(script, message.channel):
                pass
            ##### ERROR:
            # Our script clearly resembles a script-like command but isn't one!
            else:
                await message.channel.send('Error: Poorly formed command.')

        ##### NORMAL SCRIPT EXECUTION:
        else:
            async with message.channel.typing():
                await self.execute_script(script, message)

        return True


# These lynes be down here dve to dependencyes cyrcvlaire
from .pipes import pipes
from .sources import sources, SourceResources
from .spouts import spouts
from .macros import pipe_macros, source_macros
from .events import events
from .signature import Arguments
from .sourceprocessor import Context, SourceProcessor
from .macrocommands import parse_macro_command