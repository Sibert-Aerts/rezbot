import re
from typing import Union, TypeAlias
from pyparsing import ParseBaseException, ParseResults
from functools import lru_cache

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
    NATIVE_SPOUT    = object()
    NATIVE_SOURCE   = object()
    MACRO_PIPE      = object()
    MACRO_SOURCE    = object()
    UNKNOWN         = object()

    __slots__ = ('name', 'type', 'arguments', 'errors', 'pipe')

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
        elif self.name in NATIVE_PIPES:
            self.type = ParsedPipe.NATIVE_PIPE
            self.pipe = NATIVE_PIPES[self.name]
        elif self.name in NATIVE_SPOUTS:
            self.type = ParsedPipe.NATIVE_SPOUT
            self.pipe = NATIVE_SPOUTS[self.name]
        elif self.name in NATIVE_SOURCES:
            self.type = ParsedPipe.NATIVE_SOURCE
            self.pipe = NATIVE_SOURCES[self.name]
        elif self.name in MACRO_PIPES:
            self.type = ParsedPipe.MACRO_PIPE
        elif self.name in MACRO_SOURCES:
            self.type = ParsedPipe.MACRO_SOURCE
        else:
            self.type = ParsedPipe.UNKNOWN
            # NOTE: Don't issue a warning here, since the warning will be repeated even once the pipe name is found

    @staticmethod
    def find_signature(name: str) -> Union['Signature', None]:
        '''Determine pipeoid signature, if any.'''
        if name in ['', 'nop']:
            return None
        if name in NATIVE_PIPES:
            return NATIVE_PIPES[name].signature
        if name in NATIVE_SPOUTS:
            return NATIVE_SPOUTS[name].signature
        if name in NATIVE_SOURCES:
            return NATIVE_SOURCES[name].signature
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

    # ======================================= Representation =======================================

    def __repr__(self):
        return 'ParsedPipe(%s, %s)' % (repr(self.name), repr(self.arguments))
    def __str__(self):
        return self.name + ((' ' + str(self.arguments)) if self.arguments else '')


class ParsedOrigin:
    '''
    Holds an 'origin' for a script (better name pending).
    '''
    __slots__ = ('origin',)

    origin: str | list['TemplatedString']

    def __init__(self, origin: str | list['TemplatedString']):
        # NOTE: Origin may be a single str or a list of TemplatedStrings.
        # We keep the str case because the "[?]" ChoiceTree flag has special behaviour
        #   that we can't/don't want to emulate (yet?) by expanding it to a list of TemplatedStrings.
        self.origin = origin

    def process_str_origin(self) -> tuple[list['TemplatedString'] | None, ErrorLog]:
        '''
        Expands the str-type origin and parses each one as a TemplatedString.
        '''
        origins = []
        expand = True
        errors = ErrorLog()
        origin_str: str = self.origin

        ## Get rid of wrapping quotes or triple quotes
        if len(origin_str) >= 6 and origin_str[:3] == origin_str[-3:] == '"""':
            origin_str = origin_str[3:-3]
            expand = False
        elif len(origin_str) >= 2 and origin_str[0] == origin_str[-1] in ('"', "'", '/'):
            origin_str = origin_str[1:-1]

        ## ChoiceTree expand
        if expand:
            try:
                expanded = ChoiceTree(origin_str, parse_flags=True)
            except ParseBaseException as e:
                errors.log_parse_exception(e)
                return origins, errors
        else:
            expanded = [origin_str]

        ## Parse each string as a TemplatedString, collecting errors along the way
        for origin_str in expanded:
            try:
                origin = TemplatedString.from_string(origin_str)
                origins.append(origin)
                errors.extend(origin.pre_errors)
            except ParseBaseException as e:
                errors.log_parse_exception(e)

        return origins, errors

    # ======================================= Representation =======================================

    def get_static_errors(self) -> ErrorLog:
        '''
        Collects errors that can be known before execution time.
        '''
        if isinstance(self.origin, str):
            _, origin_errors = self.process_str_origin()
            return origin_errors
        else:
            errors = ErrorLog()
            for ts in self.origin:
                errors.extend(ts.pre_errors)
            return errors

    def __repr__(self):
        return 'ParsedOrigin(%s)' % repr(self.origin)
    def __str__(self):
        return str(self.origin)

    # ========================================= Application ========================================

    async def evaluate(self, context: 'Context', scope: 'ItemScope') -> tuple[list[str], ErrorLog]:
        '''
        Evaluates the origin.
        '''
        if isinstance(self.origin, str):
            origins, errors = self.process_str_origin()
            if errors.terminal: return (None, errors)
            values, map_errors = await TemplatedString.map_evaluate(origins, context, scope)
            return values, errors.extend(map_errors)
        else:
            return await TemplatedString.map_evaluate(self.origin, context, scope)


PipeSegment: TypeAlias = tuple['groupmodes.GroupMode', list[Union[ParsedPipe, 'Pipeline']]]


class Pipeline:
    '''
    The Pipeline class parses a pipeline script into a reusable, applicable Pipeline object.
    A Pipeline is made for each script execution, for nested (parenthesised) Pipelines, and for Macros.
    Its state should be immutable past parsing and comprises only two things:
        * An internal representation of the script using ParsedPipes, GroupModes, Pipelines, Arguments, etc.
        * An ErrorLog containing warnings and errors encountered during parsing.
    '''

    segments: list[ParsedOrigin | PipeSegment]
    parser_errors: ErrorLog
    iterations: int

    def __init__(self, segments: list[ParsedOrigin | PipeSegment], *, parser_errors: ErrorLog=None, iterations: int=1):
        self.segments = segments
        self.parser_errors = parser_errors if parser_errors is not None else ErrorLog()
        self.iterations = iterations
        if self.iterations < 0:
            self.parser_errors.log('Negative iteration counts are not allowed.', True)

    @lru_cache(100)
    @staticmethod
    def from_string(string: str, *, iterations: str=None, start_with_origin=False):
        errors = ErrorLog()

        segments: list[ParsedOrigin | PipeSegment] = []
        segment_strs = Pipeline.split_into_segments(string, start_with_origin=start_with_origin)
        for segment_str in segment_strs:
            if isinstance(segment_str, ParsedOrigin):
                segments.append(segment_str)
                continue
            try:
                ## Parse groupmode
                groupmode, segment_str = groupmodes.GroupMode.from_string_with_remainder(segment_str)
            except ParseBaseException as e:
                errors.log_parse_exception(e)
                continue
            except groupmodes.GroupModeError as e:
                errors.log(e, True)
                continue
            try:
                ## Parse (parallel) pipe(lines)
                parallel = Pipeline.parse_segment(segment_str)
            except ParseBaseException as e:
                errors.log_parse_exception(e)
                continue
            segments.append((groupmode, parallel))

        return Pipeline(segments, parser_errors=errors, iterations=int(iterations or 1))

    @staticmethod
    def from_string_with_origin(string: str, *, iterations: str=None):
        return Pipeline.from_string(string, iterations=iterations, start_with_origin=True)

    # =========================================== Parsing ==========================================

    @classmethod
    def split_into_segments(cls, string: str, start_with_origin=False) -> list[str | ParsedOrigin]:
        '''
        Split the pipeline into top-level segments (segment > segment > segment)
        '''
        OPEN_PAREN, CLOSE_PAREN = '()'
        OPEN_BRACE, CLOSE_BRACE = '{}'
        OPEN_BRACK, CLOSE_BRACK = '[]'
        TRIPLE_QUOTES = ('"""', "'''")
        SINGLE_QUOTES = ('"', "'")
        ALL_QUOTES = ('"""', "'''", '"', "'")

        segments = []

        stack = []
        start = 0
        i = 0
        in_origin_str = start_with_origin

        def append_segment(s: str):
            s = s.strip()
            segments.append(s if not in_origin_str else ParsedOrigin(s))

        def find_next_segment_start():
            nonlocal i, start
            ls = len(string)
            while i < ls and string[i].isspace():
                i += 1
            start = i

        while i < len(string):
            c = string[i]
            escaped = i > 0 and string[i-1] == '~'

            if not in_origin_str:
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

                may_open_quotes = (
                    i == start
                    if in_origin_str else
                    not stack or stack[-1] not in ALL_QUOTES
                )

                # Triple quotes
                if (ccc := string[i:i+3]) in TRIPLE_QUOTES:
                    if may_open_quotes:
                        stack.append(ccc)
                        i += 3; continue
                    if stack and stack[-1] == ccc:
                        stack.pop()
                        i += 3; continue

                # Single quotes
                if c in SINGLE_QUOTES:
                    if may_open_quotes:
                        stack.append(c)
                        i += 1; continue
                    if stack and stack[-1] == c:
                        stack.pop()
                        i += 1; continue

            ## Un-nested >, ending the segment
            if not stack and c == '>':
                if i > 0 and string[i-1] == '-':
                    # Special case: '->' is shorthand for '> print >'
                    append_segment(string[start:i-1])
                    append_segment('print')
                else:
                    append_segment(string[start:i])

                if string[i:i+2] == '>>':
                    # Start a new OriginString segment
                    in_origin_str = True
                    i += 2
                else:
                    # Start a new pipe segment
                    in_origin_str = False
                    i += 1

                find_next_segment_start()
                continue

            ## Nothing special
            i += 1

        ## Add the final segment, regardless of unclosed delimiters on the stack
        if final_segment := string[start:]:
            append_segment(final_segment)

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

    @classmethod
    def parse_segment(cls, segment: str) -> list[Union[ParsedPipe, 'Pipeline']]:
        '''Turn a single string describing one or more parallel pipes into a list of ParsedPipes or Pipelines.'''
        #### True and utter hack: Steal triple-quoted strings and parentheses wrapped strings out of the segment string.
        # This way these types of substrings are not affected by ChoiceTree expansion, because we only put them back afterwards.
        # For triple quotes: This allows us to pass string arguments containing [|] without having to escape them, which is nice to have.
        # For parentheses: This allows us to use parallel segments inside of inline pipelines, giving them a lot more power and utility.
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
                # Immediately parse the inline pipeline (recursion call!)
                parsed = Pipeline.from_string(pipeline, iterations=m[3])
                parsed_pipes.append(parsed)

            ## Normal pipe: foo bar=baz n=10
            else:
                parsed = ParsedPipe.from_string(pipestr)
                parsed_pipes.append(parsed)

        return parsed_pipes

    # ======================================= Representation =======================================

    def get_static_errors(self) -> ErrorLog:
        '''
        Collects errors that can be known before execution time.
        '''
        errors = ErrorLog()
        if self.parser_errors:
            errors.extend(self.parser_errors)
        for segment in self.segments:
            if isinstance(segment, ParsedOrigin):
                errors.extend(segment.get_static_errors(), 'origin')
            else:
                groupmode, pipes = segment
                errors.extend(groupmode.pre_errors, 'groupmode')
                for pipe in pipes:
                    if isinstance(pipe, ParsedPipe):
                        errors.extend(pipe.errors, pipe.name)
                    else:
                        errors.extend(pipe.get_static_errors(), 'parens')
        return errors

    def __repr__(self):
        return 'Pipeline(%s)' % repr(self.segments)
    def __str__(self):
        pieces = []
        for segment in self.segments:
            if isinstance(segment, ParsedOrigin):
                pieces.append('>>')
                pieces.append(str(segment))
            else:
                gm, pipes = segment
                pieces.append('>')
                pieces.append(str(gm))
                pipes_strs = []
                for pipe in pipes:
                    if isinstance(pipe, Pipeline):
                        pipes_strs.append('( ' + str(pipe) + ' )')
                    else:
                        pipes_strs.append(str(pipe))
                if len(pipes_strs) == 1:
                    pieces.append(pipes_strs[0])
                else:
                    pieces.append('[ ' + ' | '.join(pipes_strs) + ' ]')
        return ' '.join(pieces[1:]) # Crop off the leading >> or >

    # ========================================= Application ========================================

    def check_items(self, values: list[str], context: 'Context'):
        '''Raises an error if the user is asking too much of the bot.'''
        # TODO: this could stand to be smarter/more oriented to the type of operation you're trying to do, or something, maybe...?
        # meditate on this...
        MAXCHARS = 10000
        chars = sum(len(i) for i in values)
        if chars > MAXCHARS and not permissions.has(context.origin.activator.id, permissions.owner):
            raise PipelineError(f'Attempted to process a flow of {chars} total characters at once, try staying under {MAXCHARS}.')

    async def apply(self, items: list[str], context: 'Context', parent_scope: 'ItemScope'=None, exclude_static_errors=False) -> tuple[ list[str], ErrorLog, SpoutState ]:
        '''Apply the pipeline to a list of items the denoted amount of times.'''
        errors = ErrorLog()
        spout_state = SpoutState()

        NOTHING_BUT_ERRORS = (None, errors, None)
        if not exclude_static_errors:
            errors.extend(self.get_static_errors())
            if errors.terminal: return NOTHING_BUT_ERRORS

        for step in range(self.iterations):
            step_items, step_errors, step_spout_state = await self.apply_iteration(items, context, parent_scope)
            errors.extend(step_errors)
            if errors.terminal: return NOTHING_BUT_ERRORS
            items = step_items
            spout_state.extend(step_spout_state, extend_print=True)

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
        for segment in self.segments:

            ## CASE: Origin String
            if isinstance(segment, ParsedOrigin):
                item_scope.set_items(loose_items)
                loose_items, origin_errors = await segment.evaluate(context, item_scope)
                if errors.extend(origin_errors, 'origin').terminal:
                    return NOTHING_BUT_ERRORS
                continue

            ## CASE: Groupmode and a set of parallel pipes or pipelines
            group_mode, parsed_pipes = segment
            next_items = []
            new_printed_items = []

            # GroupMode errors
            errors.extend(group_mode.pre_errors, 'groupmode')
            if errors.terminal: return NOTHING_BUT_ERRORS

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
                    items, pl_errors, pl_spout_state = await parsed_pipe.apply(items, context, group_scope, exclude_static_errors=True)
                    errors.extend(pl_errors, 'parens')
                    if errors.terminal: return NOTHING_BUT_ERRORS
                    next_items.extend(items)
                    # group_mode.is_singular is a special case where we can safely extend print values, otherwise they're discarded here
                    spout_state.extend(pl_spout_state, extend_print=group_mode.is_singular())

                    continue

                ## CASE: The pipe is a ParsedPipe: something of the form "name [argument_list]"
                name = parsed_pipe.name
                errors.extend(parsed_pipe.errors, parsed_pipe.name)
                if errors.terminal: return NOTHING_BUT_ERRORS

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
                    NATIVE_SPOUTS['print'].hook(spout_state, items)

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
                elif parsed_pipe.type == ParsedPipe.NATIVE_SPOUT:
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
                elif name in MACRO_PIPES:
                    macro = MACRO_PIPES[name]
                    try:
                        # Get the set of arguments and put them in Context
                        args = macro.apply_signature(args)
                        macro_ctx = context.into_macro(macro, args)
                    except ArgumentError as e:
                        errors.log(e, True, context=name)
                        return NOTHING_BUT_ERRORS

                    macro_pl = Pipeline.from_string(macro.code)
                    newvals, macro_errors, macro_spout_state = await macro_pl.apply(items, macro_ctx)
                    errors.extend(macro_errors, name)
                    if errors.terminal: return NOTHING_BUT_ERRORS

                    next_items.extend(newvals)
                    # group_mode.is_singular is a special case where we can safely extend print values, otherwise they're discarded here
                    spout_state.extend(macro_spout_state, extend_print=group_mode.is_singular())

                ## A SOURCE MACRO
                elif name in MACRO_SOURCES:
                    macro = MACRO_SOURCES[name]

                    # Source Macro functioning is implemented in ParsedSource
                    temp_parsed_source = ParsedSource(name, None)
                    new_vals, src_errs = await temp_parsed_source.evaluate(context, group_scope, args)
                    errors.extend(src_errs, context='source-as-pipe')

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
from .templated_string import TemplatedString
from .macros import MACRO_PIPES, MACRO_SOURCES
from .context import Context, ItemScope
from .signature import Signature, ArgumentError, Arguments
from .pipe import Pipe, Source, Spout
from . import groupmodes

from pipes.implementations.sources import NATIVE_SOURCES
from pipes.implementations.pipes import NATIVE_PIPES
from pipes.implementations.spouts import NATIVE_SPOUTS
