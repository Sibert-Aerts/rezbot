import re
from typing import Union

from discord import Message

import permissions
from utils.choicetree import ChoiceTree

# More import statements at the end of the file, due to circular dependencies.
from . import groupmodes
from .logger import ErrorLog


class PipelineError(ValueError):
    '''Special error for some invalid element when processing a pipeline.'''


class ParsedPipe:
    '''In a parsed Pipeline represents a single, specific pipeoid along with its specific assigned arguments.'''
    # Different types of ParsedPipe, determined at moment of parsing
    SPECIAL      = object()
    NATIVE_PIPE   = object()
    SPOUT        = object()
    NATIVE_SOURCE = object()
    MACRO_PIPE    = object()
    MACRO_SOURCE  = object()
    UNKNOWN      = object()

    def __init__(self, pipestr:str):
        ''' Parse a string of the form `[name] [argstr]` '''
        name, *args = pipestr.strip().split(' ', 1)
        self.name = name.lower()
        self.argstr = args[0] if args else ''

        self.errors = ErrorLog()
        self.arguments: Arguments|None = None
        
        ## (Attempt to) determine what kind of pipe it is ahead of time
        if self.name in ['', 'nop', 'print']:
            self.type = ParsedPipe.SPECIAL
            # Special pipes don't have arguments
        elif self.name in pipes:
            self.type = ParsedPipe.NATIVE_PIPE
            self.pipe = pipes[self.name]
            self.arguments, _, errors = Arguments.from_string(self.argstr, self.pipe.signature)
            self.errors.extend(errors, self.name)
        elif self.name in spouts:
            self.type = ParsedPipe.SPOUT
            self.pipe = spouts[self.name]
            self.arguments, _, errors = Arguments.from_string(self.argstr, self.pipe.signature)
            self.errors.extend(errors, self.name)
        elif self.name in sources:
            self.type = ParsedPipe.NATIVE_SOURCE
            self.pipe = sources[self.name]
            self.arguments, _, errors = Arguments.from_string(self.argstr, self.pipe.signature)
            self.errors.extend(errors, self.name)
        elif self.name in pipe_macros:
            self.type = ParsedPipe.MACRO_PIPE
            self.arguments, _, errors = Arguments.from_string(self.argstr)
            self.errors.extend(errors, self.name)
        elif self.name in source_macros:
            self.type = ParsedPipe.MACRO_SOURCE
            self.arguments, _, errors = Arguments.from_string(self.argstr)
            self.errors.extend(errors, self.name)
        else:
            self.type = ParsedPipe.UNKNOWN
            self.arguments, _, errors = Arguments.from_string(self.argstr)
            self.errors.extend(errors, self.name)
            # This one will keep being posted repeatedly even if the name eventually is defined, so don't uncomment it
            # self.errors.warn(f'`{self.name}` is no known pipe, source, spout or macro at the time of parsing.')
        return


class Pipeline:
    ''' 
    The Pipeline class parses a pipeline script into a reusable, applicable Pipeline object.
    A Pipeline is made for each script execution, for nested (parenthesised) Pipelines, and for Macros.
    Its state should be immutable past parsing and comprises only two things:
        * An internal representation of the script using ParsedPipes, GroupModes, Pipelines, Arguments, etc.
        * An ErrorLog containing warnings and errors encountered during parsing.
    '''
    def __init__(self, string: str, iterations: str=None):
        self.parser_errors = ErrorLog()

        self.iterations = int(iterations or 1)
        if self.iterations < 0:
            self.parser_errors.log('Negative iteration counts are not allowed.', True)

        ### Split the pipeline into segments (segment > segment > segment)
        segments = self.split_into_segments(string)

        ### For each segment, parse the group mode, expand the parallel pipes and parse each parallel pipe.
        self.parsed_segments: list[tuple[ groupmodes.GroupMode, list[ParsedPipe | Pipeline] ]] = []
        for segment in segments:
            try:
                segment, groupMode = groupmodes.parse(segment)
            except groupmodes.GroupModeError as e:
                self.parser_errors.log(e, True)
                # Don't attempt to parse the rest of this segment, since we aren't sure where the groupmode ends
                continue 
            parallel = self.parse_segment(segment)
            self.parsed_segments.append((groupMode, parallel))

    @classmethod
    def split_into_segments(cls, string: str):
        '''
        Split the sequence of pipes (one big string) into a list of pipes (list of strings).
        Doesn't split on >'s inside quote blocks or within parentheses, and inserts "print"s on ->'s.
        '''
        # This is an extremely hand-written extremely low-level parser for the basic structure of a pipeline.
        # There are NO ESCAPE SEQUENCES. Every quotation mark is taken as one. Every parenthesis outside of quotation marks is 100% real.
        # TODO: NOTE: This causes terrible parsing inconsistencies. e.g.    foo > bar x=( > baz     only splits on the first >

        segments: list[str] = []
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
    wrapping_parens_regex = re.compile(r'\(((.*)\)(?:\^(-?\d+))?|(.*))', re.S)
    #                                        ^^         ^^^^^     ^^

    @classmethod
    def steal_parentheses(cls, segment):
        '''Steals all (intelligently-parsed) parentheses-wrapped parts from a string and puts them in a list so we can put them back later.'''
        ## Prepare the segment for Magic
        # Pretty sure the magic markers don't need to be different from the triple quote ones, but it can't hurt so why not haha
        segment = segment.replace('µ', '?µ?')

        # Parsing loop similar to the one in split_into_segments.
        # NOTE: So why not combine the two into one? Well, I tried, but BETWEEN splitting into segments and stealing parentheses
        # we have to consume the group mode from each segment! Which is hard to squeeze in here! Especially since one group mode also uses parentheses!!!
        stolen = []
        bereft = []

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
                    bereft += (segment[start:i], 'µ',  str(len(stolen)), 'µ')
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
        else: bereft.append( segment[start:] )

        return ''.join(bereft), stolen

    rp_regex = re.compile(r'µ(\d+)µ')
    rq_regex = re.compile(r'§(\d+)§')

    @classmethod
    def restore_parentheses(cls, bereft, stolen):
        bereft = cls.rp_regex.sub(lambda m: stolen[int(m[1])], bereft)
        return bereft.replace('?µ?', 'µ')

    @classmethod
    def steal_triple_quotes(cls, segment):
        '''Steals all triple quoted parts from a string and puts them in a list so we can put them back later.'''
        stolen = []
        def steal(match):
            stolen.append(match[0])
            return '§' + str(len(stolen)-1) + '§'
        segment = segment.replace('§', '!§!')
        segment = re.sub(r'(?s)""".*?"""', steal, segment) # (?s) means "dot matches all"
        return segment, stolen

    @classmethod
    def restore_triple_quotes(cls, bereft, stolen):
        bereft = cls.rq_regex.sub(lambda m: stolen[int(m[1])], bereft)
        return bereft.replace('!§!', '§')

    def parse_segment(self, segment: str) -> list[Union[ParsedPipe, 'Pipeline']]:
        '''Turn a single string describing one or more parallel pipes into a list of ParsedPipes or Pipelines.'''
        #### True and utter hack: Steal triple-quoted strings and parentheses wrapped strings out of the segment string.
        # This way these types of substrings are not affected by ChoiceTree expansion, because we only put them back afterwards.
        # For triple quotes: This allows us to pass string arguments containing [|] without having to escape them, which is nice to have.
        # For parentheses: This allows us to use parallel segments inside of inline pipelines, giving them a lot more power and utility.
        segment, stolen_parens = self.steal_parentheses(segment)
        segment, stolen_quotes = self.steal_triple_quotes(segment)

        ### Parse the simultaneous pipes into a usable form: A list[Union[Pipeline, ParsedPipe]]
        parsedPipes: list[ParsedPipe | Pipeline] = []

        # ChoiceTree expands the segment into the different parallel pipes 
        for pipe in ChoiceTree(segment, add_brackets=True):
            ## Put the stolen triple-quoted strings and parentheses back.
            pipe = self.restore_triple_quotes(pipe, stolen_quotes)
            pipe = self.restore_parentheses(pipe, stolen_parens)
            pipe = pipe.strip()

            ## Inline pipeline: (foo > bar > baz)
            if pipe and pipe[0] == '(':
                # TODO: This shouldn't happen via regex.
                m = re.match(Pipeline.wrapping_parens_regex, pipe)
                pipeline = m[2] or m[4]
                # Immediately attempt to parse the inline pipeline (recursion call!)
                parsed = Pipeline(pipeline, m[3])
                self.parser_errors.steal(parsed.parser_errors, context='parens')
                parsedPipes.append(parsed)

            ## Normal pipe: foo [bar=baz]*
            else:
                parsed = ParsedPipe(pipe)
                self.parser_errors.steal(parsed.errors)
                parsedPipes.append(parsed)

        return parsedPipes

    def check_items(self, values: list[str], message: Message):
        '''Raises an error if the user is asking too much of the bot.'''
        # TODO: this could stand to be smarter/more oriented to the type of operation you're trying to do, or something, maybe...?
        # meditate on this...
        MAXCHARS = 10000
        chars = sum(len(i) for i in values)
        if chars > MAXCHARS and not permissions.has(message.author.id, permissions.owner):
            raise PipelineError(f'Attempted to process a flow of {chars} total characters at once, try staying under {MAXCHARS}.')

    async def apply(self, items: list[str], message: Message, parent_context: 'Context'=None) -> tuple[ list[str], list[list[str]], ErrorLog, list ]:
        '''Apply the pipeline to a list of items the denoted amount of times.'''
        errors = ErrorLog()
        NOTHING_BUT_ERRORS = (None, None, errors, None)
    
        errors.extend(self.parser_errors)
        if errors.terminal: return NOTHING_BUT_ERRORS

        print_values = []
        spoutCallbacks = []
        for _ in range(self.iterations):
            iterItems, iterPrintValues, iterErrors, iterSpoutCallbacks = await self.apply_iteration(items, message, parent_context)
            errors.extend(iterErrors)
            if errors.terminal: return NOTHING_BUT_ERRORS
            items = iterItems
            print_values.extend(iterPrintValues)
            spoutCallbacks.extend(iterSpoutCallbacks)

        return items, print_values, errors, spoutCallbacks

    async def apply_iteration(self, items: list[str], message: Message, parent_context: 'Context'=None) -> tuple[ list[str], list[list[str]], ErrorLog, list ]:
        '''Apply the pipeline to a list of items a single time.'''
        ## This is the big method where everything happens.

        errors = ErrorLog()
        # When a terminal error is encountered, cut script execution short and only return the error log
        # This suggestively named tuple is for such cases.
        NOTHING_BUT_ERRORS = (None, None, errors, None)

        # Turns out this pipeline just isn't even executable due to parsing errors! abort!
        if errors.terminal:
            return NOTHING_BUT_ERRORS

        # Set up some objects we'll likely need
        context = Context(parent_context)
        printed_items = []
        spout_callbacks = []
        loose_items = items

        self.check_items(loose_items, message)

        ### This loop iterates over the pipeline's segments as they are applied in sequence. (first > second > third)
        for group_mode, parsed_pipes in self.parsed_segments:
            next_items = []
            new_printed_items = []

            # Non-trivial groupmodes add a new context layer
            if group_mode.splits_trivially():
                group_context = context
            else:
                context.set_items(loose_items)
                group_context = Context(context)

            try:
                applied_group_mode = group_mode.apply(loose_items, parsed_pipes)
            except groupmodes.GroupModeError as e:
                errors.log('GroupModeError: ' + str(e), True)
                return NOTHING_BUT_ERRORS

            ### The group mode turns the list[item], list[pipe] into  list[Tuple[ list[item], Optional[Pipe] ]]
            # i.e. it splits the list of items into smaller lists, and assigns each one a pipe to be applied to (if any).
            # The implemenation of this arcane flowchart magicke is detailed in `./groupmodes.py`
            # In the absolute simplest (and most common) case, all values are simply sent to a single pipe, and this loop iterates exactly once.
            for items, parsed_pipe in applied_group_mode:
                group_context.set_items(items)

                ## CASE: `None` is how the groupmode assigns values to remain unaffected
                if parsed_pipe is None:
                    next_items.extend(items)
                    continue

                ## CASE: The pipe is itself an inlined Pipeline (recursion!)
                if isinstance(parsed_pipe, Pipeline):
                    items, pl_print_values, pl_errors, pl_spout_callbacks = await parsed_pipe.apply(items, message, group_context)
                    errors.extend(pl_errors, 'braces')
                    if errors.terminal: return NOTHING_BUT_ERRORS
                    next_items.extend(items)
                    spout_callbacks += pl_spout_callbacks

                    # Special case where we can safely absorb print items into the whole
                    if group_mode.is_singular():
                        printed_items.extend(pl_print_values)

                    continue

                ## CASE: The pipe is a ParsedPipe: something of the form "name [argument_list]"
                name = parsed_pipe.name

                #### Determine the arguments (if needed)
                if parsed_pipe.arguments is not None:
                    args, arg_errors = await parsed_pipe.arguments.determine(message, group_context)
                    errors.extend(arg_errors, context=name)

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
                    spout_callbacks.append(spouts['print'].hook(items))

                ## A NATIVE PIPE
                elif parsed_pipe.type == ParsedPipe.NATIVE_PIPE:
                    pipe: Pipe = parsed_pipe.pipe
                    if not pipe.may_use(message.author):
                        errors.log(f'User lacks permission to use Pipe `{pipe.name}`.', True)
                        return NOTHING_BUT_ERRORS
                    try:
                        if pipe.is_coroutine:
                            next_items.extend(await pipe.apply(items, **args))
                        else:
                            next_items.extend(pipe.apply(items, **args))
                    except Exception as e:
                        errors.log(f'Failed to process Pipe `{pipe.name}` with args {args}:\n\t{type(e).__name__}: {e}', True)
                        return NOTHING_BUT_ERRORS

                ## A SPOUT
                elif parsed_pipe.type == ParsedPipe.SPOUT:
                    spout: Spout = parsed_pipe.pipe
                    # As a rule, spouts do not affect the values
                    next_items.extend(items)
                    try:
                        # Queue up the spout's side-effects instead, to be executed once the entire script has completed
                        spout_callbacks.append( spout.hook(items, **args) )
                    except Exception as e:
                        errors.log(f'Failed to process Spout `{name}` with args {args}:\n\t{type(e).__name__}: {e}', True)
                        return NOTHING_BUT_ERRORS
                    
                ## A NATIVE SOURCE
                elif parsed_pipe.type == ParsedPipe.NATIVE_SOURCE:
                    source: Source = parsed_pipe.pipe
                    # Sources don't accept input values: Discard them but warn about it if nontrivial input is being discarded.
                    # This is just a style warning, if it turns out this is annoying then it should be removed.
                    if items and not (len(items) == 1 and not items[0]):
                        errors.log(f'Source-as-pipe `{name}` received nonempty input; either use all items as arguments or explicitly `remove` unneeded items.')

                    try:
                       next_items.extend( await source.generate(context, args) )
                    except Exception as e:
                        errors.log(f'Failed to process Source-as-Pipe `{name}` with args {args}:\n\t{type(e).__name__}: {e}', True)
                        return NOTHING_BUT_ERRORS

                ## A PIPE MACRO
                elif name in pipe_macros:
                    try:
                        code = pipe_macros[name].apply_args(args)
                    except ArgumentError as e:
                        errors.log(e, True, context=name)
                        return NOTHING_BUT_ERRORS

                    ## Load the cached pipeline if we already parsed this code once before
                    if code in pipe_macros.pipeline_cache:
                        macro = pipe_macros.pipeline_cache[code]
                    else:
                        macro = Pipeline(code)
                        pipe_macros.pipeline_cache[code] = macro

                    newvals, macro_print_values, macro_errors, macro_spout_callbacks = await macro.apply(items, message)
                    errors.extend(macro_errors, name)
                    if errors.terminal: return NOTHING_BUT_ERRORS

                    next_items.extend(newvals)
                    spout_callbacks += macro_spout_callbacks

                    # Special case where we can safely absorb print items into the whole
                    if group_mode.is_singular():
                        printed_items.extend(macro_print_values)

                ## A SOURCE MACRO
                elif name in source_macros:
                    if items and not (len(items) == 1 and not items[0]):
                        errors.log(f'Macro-source-as-pipe `{name}` received nonempty input; either use all items as arguments or explicitly `remove` unneeded items.')

                    source_macro = ParsedSource(name, None, None)
                    newVals, src_errs = await source_macro.evaluate(message, group_context, args)
                    errors.steal(src_errs, context='source-as-pipe')

                    if newVals is None or errors.terminal:
                        errors.terminal = True
                        return NOTHING_BUT_ERRORS
                    next_items.extend(newVals)

                ## UNKNOWN NAME
                else:
                    errors.log(f'Unknown pipe `{name}`.', True)
                    return NOTHING_BUT_ERRORS

            loose_items = next_items
            if new_printed_items:
                printed_items.append(new_printed_items)

            self.check_items(loose_items, message)

        return loose_items, printed_items, errors, spout_callbacks


# These lynes be down here dve to dependencyes cyrcvlaire
from .implementations.pipes import pipes
from .implementations.sources import sources
from .implementations.spouts import spouts
from .macros import pipe_macros, source_macros
from .context import Context
from .signature import ArgumentError, Arguments
from .templatedstring import ParsedSource
from .pipe import Pipe, Source, Spout
