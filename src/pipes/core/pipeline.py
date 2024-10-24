import re
from typing import Union
from pyparsing import ParseBaseException, ParseResults

import permissions
from utils.choicetree import ChoiceTree

# More import statements at the end of the file, due to circular dependencies.
from .logger import ErrorLog
from .spout_state import SpoutState


class PipelineError(ValueError):
    '''Special error for some invalid element when processing a pipeline.'''


class ParsedPipe:
    '''In a parsed Pipeline represents a single, specific pipeoid along with its specific assigned arguments.'''
    # Different types of ParsedPipe, determined at moment of parsing
    SPECIAL         = object()
    NATIVE_PIPE     = object()
    SPOUT           = object()
    NATIVE_SOURCE   = object()
    MACRO_PIPE      = object()
    MACRO_SOURCE    = object()
    UNKNOWN         = object()

    def __init__(self, name: str, arguments: 'Arguments', *, errors: ErrorLog=None):
        self.errors = errors if errors is not None else ErrorLog()
        self.arguments = arguments

        # Validate name
        self.name = name.strip().lower()
        if self.name and not re.match(r'^[_a-z]\w*$', self.name):
            self.errors.log(f'Invalid pipe name "{self.name}"', True)

        ## (Attempt to) determine what kind of pipe it is ahead of time
        if self.name in ['', 'nop', 'print']:
            self.type = ParsedPipe.SPECIAL
        elif self.name in pipes:
            self.type = ParsedPipe.NATIVE_PIPE
            self.pipe = pipes[self.name]
        elif self.name in spouts:
            self.type = ParsedPipe.SPOUT
            self.pipe = spouts[self.name]
        elif self.name in sources:
            self.type = ParsedPipe.NATIVE_SOURCE
            self.pipe = sources[self.name]
        elif self.name in pipe_macros:
            self.type = ParsedPipe.MACRO_PIPE
        elif self.name in source_macros:
            self.type = ParsedPipe.MACRO_SOURCE
        else:
            self.type = ParsedPipe.UNKNOWN
            # NOTE: Don't issue a warning here, since the warning will be repeated even once the pipe name is found

    @staticmethod
    def find_signature(name: str) -> Union['Signature', None]:
        '''Determine pipeoid signature, if any.'''
        if name in ['', 'nop']:
            return None
        if name in pipes:
            return pipes[name].signature
        if name in spouts:
            return spouts[name].signature
        if name in sources:
            return sources[name].signature
        # Else: A macro, or an unknown/invalid pipe
        return None

    @staticmethod
    def from_string(pipestr: str) -> 'ParsedPipe':
        name, *args = pipestr.strip().split(' ', 1)
        name = name.lower()
        argstr = args[0] if args else ''
        signature = ParsedPipe.find_signature(name)
        arguments, _, errors = Arguments.from_string(argstr, signature)
        return ParsedPipe(name, arguments, errors=errors)

    @staticmethod
    def from_parsed(result: ParseResults) -> 'ParsedPipe':
        name = result['pipe_name'].strip().lower()
        signature = ParsedPipe.find_signature(name)
        arguments, _, errors = Arguments.from_parsed(result['args'], signature)
        return ParsedPipe(name, arguments, errors=errors)


class Pipeline:
    '''
    The Pipeline class parses a pipeline script into a reusable, applicable Pipeline object.
    A Pipeline is made for each script execution, for nested (parenthesised) Pipelines, and for Macros.
    Its state should be immutable past parsing and comprises only two things:
        * An internal representation of the script using ParsedPipes, GroupModes, Pipelines, Arguments, etc.
        * An ErrorLog containing warnings and errors encountered during parsing.
    '''
    def __init__(self, parsed_segments: list[tuple['groupmodes.GroupMode', list[Union[ParsedPipe, 'Pipeline']]]], *, parser_errors: ErrorLog=None, iterations: int=1):
        self.parsed_segments = parsed_segments
        self.parser_errors = parser_errors
        self.iterations = iterations
        if self.iterations < 0:
            self.parser_errors.log('Negative iteration counts are not allowed.', True)

    @staticmethod
    def from_string(string: str, iterations: str=None):
        errors = ErrorLog()
        iterations = int(iterations or 1)

        ### Split the pipeline into segments (segment > segment > segment)
        segments = Pipeline.split_into_segments(string)

        ### For each segment, parse the group mode, expand the parallel pipes and parse each parallel pipe.
        parsed_segments: list[tuple[ groupmodes.GroupMode, list[ParsedPipe | Pipeline] ]] = []
        for segment in segments:
            try:
                groupmode, segment = groupmodes.GroupMode.from_string_with_remainder(segment)
            except ParseBaseException as e:
                errors.log_parse_exception(e)
                continue
            except groupmodes.GroupModeError as e:
                errors.log(e, True)
                continue
            try:
                parallel, segment_errors = Pipeline.parse_segment(segment)
            except ParseBaseException as e:
                errors.log_parse_exception(e)
                continue
            errors.extend(groupmode.pre_errors, 'groupmode')
            errors.extend(segment_errors)
            parsed_segments.append((groupmode, parallel))

        return Pipeline(parsed_segments, parser_errors=errors, iterations=iterations)

    # =========================================== Parsing ==========================================

    @classmethod
    def split_into_segments(cls, string: str):
        '''
        Split the sequence of pipes (one big string) into a list of pipes (list of strings).
        Doesn't split on >'s inside quote blocks or within parentheses, and inserts "print"s on ->'s.
        '''
        OPEN_PAREN, CLOSE_PAREN = '()'
        OPEN_BRACE, CLOSE_BRACE = '{}'
        OPEN_BRACK, CLOSE_BRACK = '[]'
        TRIPLE_QUOTES = ('"""', "'''")
        SINGLE_QUOTES = ('"', "'")
        ALL_QUOTES = ('"""', "'''", '"', "'")

        stack = []
        segments = []
        segment_start = 0
        i = 0

        while i < len(string):
            c = string[i]
            escaped = i > 0 and string[i-1] == '~'

            ## Parentheses: Only top-level or within other parentheses, unescapable
            if c == OPEN_PAREN and (not stack or stack[-1] == OPEN_PAREN):
                stack.append(c)
                i += 1; continue
            if c == CLOSE_PAREN and stack and stack[-1] == OPEN_PAREN:
                stack.pop()
                i += 1; continue

            if not escaped:
                ## Braces and brackets
                if c in (OPEN_BRACE, OPEN_BRACK):
                    stack.append(c)
                    i += 1; continue
                if c == CLOSE_BRACE and stack and stack[-1] == OPEN_BRACE:
                    stack.pop()
                    i += 1; continue
                if c == CLOSE_BRACK and stack and stack[-1] == OPEN_BRACK:
                    stack.pop()
                    i += 1; continue

                # Triple quotes
                if (ccc := string[i:i+3]) in TRIPLE_QUOTES:
                    if not stack or stack[-1] not in ALL_QUOTES:
                        stack.append(ccc)
                        i += 3; continue
                    if stack and stack[-1] == ccc:
                        stack.pop()
                        i += 3; continue

                # Single quotes
                if c in SINGLE_QUOTES:
                    if not stack or stack[-1] not in ALL_QUOTES:
                        stack.append(c)
                        i += 1; continue
                    if stack and stack[-1] == c:
                        stack.pop()
                        i += 1; continue

            ## Un-nested >, ending the segment
            if not stack and c == '>':
                if i > 0 and string[i-1] == '-':
                    segments.append(string[segment_start:i-1])
                    segments.append('print')
                else:
                    segments.append(string[segment_start:i])
                i += 1
                segment_start = i
                continue

            ## Nothing special
            i += 1

        ## Add the final segment, regardless of unclosed delimiters on the stack
        if final_segment := string[segment_start:]:
            segments.append(final_segment)

        return [s.strip() for s in segments]

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

    @classmethod
    def parse_segment(cls, segment: str) -> list[Union[ParsedPipe, 'Pipeline']] | ErrorLog:
        '''Turn a single string describing one or more parallel pipes into a list of ParsedPipes or Pipelines.'''
        #### True and utter hack: Steal triple-quoted strings and parentheses wrapped strings out of the segment string.
        # This way these types of substrings are not affected by ChoiceTree expansion, because we only put them back afterwards.
        # For triple quotes: This allows us to pass string arguments containing [|] without having to escape them, which is nice to have.
        # For parentheses: This allows us to use parallel segments inside of inline pipelines, giving them a lot more power and utility.
        errors = ErrorLog()
        segment, stolen_parens = cls.steal_parentheses(segment)
        segment, stolen_quotes = cls.steal_triple_quotes(segment)

        ### Parse the simultaneous pipes into a usable form: A list[Union[Pipeline, ParsedPipe]]
        parsed_pipes: list[ParsedPipe | Pipeline] = []

        # ChoiceTree expands the segment into the different parallel pipes
        for pipestr in ChoiceTree(segment):
            ## Put the stolen triple-quoted strings and parentheses back.
            pipestr = cls.restore_triple_quotes(pipestr, stolen_quotes)
            pipestr = cls.restore_parentheses(pipestr, stolen_parens)
            pipestr = pipestr.strip()

            ## Inline pipeline: (foo > bar > baz)
            if pipestr and pipestr[0] == '(':
                # TODO: This shouldn't happen via regex.
                m = re.match(Pipeline.wrapping_parens_regex, pipestr)
                pipeline = m[2] or m[4]
                # Immediately attempt to parse the inline pipeline (recursion call!)
                parsed = Pipeline.from_string(pipeline, m[3])
                errors.steal(parsed.parser_errors, context='parens')
                parsed_pipes.append(parsed)

            ## Normal pipe: foo [bar=baz]*
            else:
                parsed = ParsedPipe.from_string(pipestr)
                errors.steal(parsed.errors, context=parsed.name)
                parsed_pipes.append(parsed)

        return parsed_pipes, errors

    # ========================================= Application ========================================

    def check_items(self, values: list[str], context: 'Context'):
        '''Raises an error if the user is asking too much of the bot.'''
        # TODO: this could stand to be smarter/more oriented to the type of operation you're trying to do, or something, maybe...?
        # meditate on this...
        MAXCHARS = 10000
        chars = sum(len(i) for i in values)
        if chars > MAXCHARS and not permissions.has(context.origin.activator.id, permissions.owner):
            raise PipelineError(f'Attempted to process a flow of {chars} total characters at once, try staying under {MAXCHARS}.')

    async def apply(self, items: list[str], context: 'Context', parent_scope: 'ItemScope'=None) -> tuple[ list[str], ErrorLog, SpoutState ]:
        '''Apply the pipeline to a list of items the denoted amount of times.'''
        errors = ErrorLog()
        spout_state = SpoutState()

        NOTHING_BUT_ERRORS = (None, errors, None)
        errors.extend(self.parser_errors)
        if errors.terminal: return NOTHING_BUT_ERRORS

        for _ in range(self.iterations):
            iter_items, iter_errors, iter_spout_state = await self.apply_iteration(items, context, parent_scope)
            errors.extend(iter_errors)
            if errors.terminal: return NOTHING_BUT_ERRORS
            items = iter_items
            spout_state.extend(iter_spout_state, extend_print=True)

        return items, errors, spout_state

    async def apply_iteration(self, items: list[str], context: 'Context', parent_scope: 'ItemScope'=None) -> tuple[ list[str], ErrorLog, SpoutState ]:
        '''Apply the pipeline to a list of items a single time.'''
        ## This is the big method where everything happens.

        errors = ErrorLog()
        # When a terminal error is encountered, cut script execution short and only return the error log
        # This suggestively named tuple is for such cases.
        NOTHING_BUT_ERRORS = (None, errors, None)

        # Turns out this pipeline just isn't even executable due to parsing errors! abort!
        if errors.terminal:
            return NOTHING_BUT_ERRORS

        # Set up some objects we'll likely need
        item_scope = ItemScope(parent_scope)
        spout_state = SpoutState()
        loose_items = items

        self.check_items(loose_items, context)

        ### This loop iterates over the pipeline's segments as they are applied in sequence. (first > second > third)
        for group_mode, parsed_pipes in self.parsed_segments:
            next_items = []
            new_printed_items = []

            # Non-trivial groupmodes add a new item scope layer
            if group_mode.splits_trivially():
                group_scope = item_scope
            else:
                item_scope.set_items(loose_items)
                group_scope = ItemScope(item_scope)

            try:
                applied_group_mode = await group_mode.apply(loose_items, parsed_pipes, context, group_scope)
            except groupmodes.GroupModeError as e:
                errors.log('**in groupmode:** ' + str(e), True)
                if e.errors: errors.extend(e.errors, 'groupmode')
                return NOTHING_BUT_ERRORS

            ### The group mode turns the list[item], list[pipe] into  list[Tuple[ list[item], Optional[Pipe] ]]
            # i.e. it splits the list of items into smaller lists, and assigns each one a pipe to be applied to (if any).
            # The implemenation of this arcane flowchart magicke is detailed in `./groupmodes.py`
            # In the absolute simplest (and most common) case, all values are simply sent to a single pipe, and this loop iterates exactly once.
            for items, parsed_pipe in applied_group_mode:
                group_scope.set_items(items)

                ## CASE: `None` is how the groupmode assigns values to remain unaffected
                if parsed_pipe is None:
                    next_items.extend(items)
                    continue

                ## CASE: The pipe is itself an inlined Pipeline (recursion!)
                if isinstance(parsed_pipe, Pipeline):
                    items, pl_errors, pl_spout_state = await parsed_pipe.apply(items, context, group_scope)
                    errors.extend(pl_errors, 'braces')
                    if errors.terminal: return NOTHING_BUT_ERRORS
                    next_items.extend(items)
                    # group_mode.is_singular is a special case where we can safely extend print values, otherwise they're discarded here
                    spout_state.extend(pl_spout_state, extend_print=group_mode.is_singular())

                    continue

                ## CASE: The pipe is a ParsedPipe: something of the form "name [argument_list]"
                name = parsed_pipe.name

                #### Determine the arguments (if needed)
                if parsed_pipe.arguments is not None:
                    args, arg_errors = await parsed_pipe.arguments.determine(context, group_scope)
                    errors.extend(arg_errors, context=name)

                # Check if something went wrong while determining arguments
                if errors.terminal: return NOTHING_BUT_ERRORS
                # Handle certain items being ignoring/filtering depending on their use in arguments
                ignored, items = group_scope.extract_ignored()
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
                    spouts['print'].hook(spout_state, items)

                ## A NATIVE PIPE
                elif parsed_pipe.type == ParsedPipe.NATIVE_PIPE:
                    pipe: Pipe = parsed_pipe.pipe
                    if not pipe.may_use(context.origin.activator):
                        errors.log(f'User lacks permission to use Pipe `{name}`.', True)
                        return NOTHING_BUT_ERRORS
                    try:
                        next_items.extend(await pipe.apply(items, **args))
                    except Exception as e:
                        errors.log(f'Failed to process Pipe `{name}` with args {args}:\n\t{type(e).__name__}: {e}', True)
                        return NOTHING_BUT_ERRORS

                ## A SPOUT
                elif parsed_pipe.type == ParsedPipe.SPOUT:
                    spout: Spout = parsed_pipe.pipe
                    # Hook the spout into the SpoutState
                    spout.hook(spout_state, items, **args)
                    # As a rule, spouts do not affect the values
                    next_items.extend(items)

                ## A NATIVE SOURCE
                elif parsed_pipe.type == ParsedPipe.NATIVE_SOURCE:
                    source: Source = parsed_pipe.pipe
                    # Sources don't accept input values: Discard them but warn about it if nontrivial input is being discarded.
                    # This is just a style warning, if it turns out this is annoying then it should be removed.
                    # NOTE: This turned out to be annoying
                    # if items and not (len(items) == 1 and not items[0]):
                    #     errors.log(f'Source-as-pipe `{name}` received nonempty input; either use all items as arguments or explicitly `remove` unneeded items.')

                    try:
                       next_items.extend( await source.generate(context, args) )
                    except Exception as e:
                        errors.log(f'Failed to process Source-as-Pipe `{name}` with args {args}:\n\t{type(e).__name__}: {e}', True)
                        return NOTHING_BUT_ERRORS

                ## A PIPE MACRO
                elif name in pipe_macros:
                    macro = pipe_macros[name]
                    try:
                        # NEWFANGLED: Get the set of arguments and put them in Context
                        args = macro.apply_signature(args)
                        macro_ctx = context.into_macro(macro, args)
                        # DEPRECATED: Insert arguments into Macro string
                        code = macro.apply_args(args)
                    except ArgumentError as e:
                        errors.log(e, True, context=name)
                        return NOTHING_BUT_ERRORS

                    macro_pl = pipe_macros.pipeline_from_code(code)
                    newvals, macro_errors, macro_spout_state = await macro_pl.apply(items, macro_ctx)
                    errors.extend(macro_errors, name)
                    if errors.terminal: return NOTHING_BUT_ERRORS

                    next_items.extend(newvals)
                    # group_mode.is_singular is a special case where we can safely extend print values, otherwise they're discarded here
                    spout_state.extend(macro_spout_state, extend_print=group_mode.is_singular())

                ## A SOURCE MACRO
                elif name in source_macros:
                    macro = source_macros[name]

                    # Source Macro functioning is implemented in ParsedSource
                    temp_parsed_source = ParsedSource(name, None)
                    new_vals, src_errs = await temp_parsed_source.evaluate(context, group_scope, args)
                    errors.steal(src_errs, context='source-as-pipe')

                    if new_vals is None or errors.terminal:
                        errors.terminal = True
                        return NOTHING_BUT_ERRORS
                    next_items.extend(new_vals)

                ## UNKNOWN NAME
                else:
                    errors.log(f'Unknown pipe `{name}`.', True)
                    return NOTHING_BUT_ERRORS

            # Clean up after applying every group mode, prepare for the next pipeline segment
            if new_printed_items:
                spout_state.print_values.append(new_printed_items)
            loose_items = next_items
            self.check_items(loose_items, context)

        return loose_items, errors, spout_state


# These lynes be down here dve to dependencyes cyrcvlaire
from .templated_element import ParsedSource
from .macros import pipe_macros, source_macros
from .context import Context, ItemScope
from .signature import Signature, ArgumentError, Arguments
from .pipe import Pipe, Source, Spout
from . import groupmodes

from pipes.implementations.sources import sources
from pipes.implementations.pipes import pipes
from pipes.implementations.spouts import spouts
