from datetime import datetime
import discord
import re
import random
import asyncio
import time
from typing import List, Tuple, Optional, Any, TypeVar

from lru import LRU

from .pipes import pipes
from .sources import sources, SourceResources
from .spouts import spouts
from .macros import pipe_macros, source_macros
from .events import events
from .macrocommands import parse_macro_command
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

class ErrorLog:
    '''Class for logging warnings & error messages from a pipeline's execution.'''
    def __init__(self):
        self.clear()

    class ErrorMessage:
        def __init__(self, message, count=1):
            self.count = count
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
            if context is not None: message = '**in {}:** {}'.format(context, e.message)
            else: message = e.message
            if self.errors and self.errors[-1].message == message:
                self.errors[-1].count += e.count
            else:
                self.errors.append(ErrorLog.ErrorMessage(message, e.count))

    def steal(self, other, *args, **kwargs):
        self.extend(other, *args, **kwargs)
        other.clear()

    def clear(self):
        self.errors = []
        self.terminal = False
        self.time = datetime.now().strftime('%z %c')

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


class Context:
    def __init__(self, parent=None):
        self.items = []
        self.parent = parent
        self.to_be_ignored = set()
        self.to_be_removed = set()

    def set(self, items):
        self.items = items
        self.to_be_ignored = set()
        self.to_be_removed = set()

    _item_regex = r'{(\^*)(-?\d+)(!?)}'
    #                 ^^^  ^^^^^  ^^
    #              carrots index exclamation
    item_regex = re.compile(_item_regex)
    empty_item_regex = re.compile(r'{(\^*)(!?)}')
    #                                 ^^^  ^^

    @staticmethod
    def preprocess(string):
        '''
        Replaces empty {}'s with explicitly numbered {}'s
        e.g. "{} {} {!}" → "{0} {1} {2!}"
             "{^} {} {^!} {^^} {}" → "{^0} {0} {^1!} {^^0} {1}"
        '''
        if not Context.empty_item_regex.search(string):
            return string
        
        ## Make sure there is no mixed use of numbered and non-numbered items
        # TODO: Only check this per depth level, so e.g. "{} {^0} {}" is allowed?
        if Context.item_regex.search(string):
            raise ContextError('Do not mix empty {}\'s with numbered {}\'s in the format string "%s".' % string)

        def f(m):
            carrots = m[1]
            if carrots not in f.i:
                f.i[carrots] = 0
            else:
                f.i[carrots] += 1
            return '{%s%d%s}' % (carrots, f.i[carrots], m[2])
        f.i = {}

        return Context.empty_item_regex.sub(f, string)

    def get_item(self, carrots, index, exclamation):
        ctx = self
        # For each ^ go up a context
        for i in range(len(carrots)):
            if ctx.parent is None: raise ContextError('Out of scope: References a parent context beyond scope!')
            ctx = ctx.parent

        count = len(ctx.items)
        # Make sure the index fits in the context's range of items
        i = int(index)
        if i >= count: raise ContextError('Out of range: References item {} out of only {} items.'.format(i, count))
        if i < 0: i += count
        if i < 0: raise ContextError('Out of range: Negative index {} for only {} items.'.format(i-count, count))

        # Only flag items to be ignored if we're in the current context (idk how it would work with higher contexts)
        if ctx is self:
            ignore = (exclamation == '!')
            (self.to_be_ignored if ignore else self.to_be_removed).add(i)
        return ctx.items[i]

    def get_ignored_filtered(self):
        ### Merge the sets into a clear view:
        # If "conflicting" instances occur (i.e. both {0} and {0!}) give precedence to the {0!}
        # Since the ! is an intentional indicator of what they want to happen; Do not remove the item
        to_be = [ (i, True) for i in self.to_be_removed.difference(self.to_be_ignored) ] + [ (i, False) for i in self.to_be_ignored ]
        
        # Finnicky list logic for ignoring/removing the appropriate indices
        to_be.sort(key=lambda x: x[0], reverse=True)
        ignored = []
        filtered = list(self.items)
        for i, rem in to_be:
            if not rem: ignored.append(self.items[i])
            del filtered[i]
        ignored.reverse()

        return ignored, filtered


class SourceProcessor:
    # This is a class so I don't have to juggle the message (discord context) and error log around
    # This class is responsible for all instances of replacing {}, {0}, {source}, etc. with actual strings
    # TODO: The entire job of parsing sources could be improved by getting an actual parser to do the job,
    #       this would also allow handling {nested what={sources}} which would be nice :)

    def __init__(self, message):
        self.message = message
        self.errors = ErrorLog()

    # Matches: {source}, {source and some args}, {source args="{curly braces allowed}"}, {10 sources}, etc.
    # Doesn't match: {}, {0}, {1}, {2}, {2!} etc., those are matched by Context.item_regex

    _source_regex = r'(?i){\s*(ALL|\d*)\s*([_a-z][^\s}]*)\s*([^}\s](?:\"[^\"]*\"|[^}])*)?}'
    #                          ^^^^^^^     ^^^^^^^^^^^^^     ^^^^^^^^^^^^^^^^^^^^^^^^^^
    #                             n            name                     args
    source_regex = re.compile(_source_regex)
    source_match_regex = re.compile(_source_regex + '$')
    source_or_item_regex = re.compile('(?:' + _source_regex + '|' + Context._item_regex + ')')
    # This is a regex with 6 capture groups: n, name, args, carrots, index, exclamation

    def is_pure_source(self, source):
        '''Checks whether a string matches the exact format "{[n] source [args]}", AKA "pure".'''
        return re.match(SourceProcessor.source_match_regex, source)

    async def evaluate_parsed_source(self, name, args, n=None):
        '''Given the exact name, arguments and `n` of a source, evaluates it.'''
        if name in sources:
            ###### This is the SINGLE spot where a source is called during execution of pipelines
            try:
                return await sources[name](self.message, args, n=n)
            except Exception as e:
                self.errors('Failed to evaluate source `{}` with args "{}":\n\t{}: {}'.format(name, args, e.__class__.__name__, e))
                return None

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
            values, _, pl_errors, _ = await pipeline.apply(values, self.message)
            errors.extend(pl_errors)
            # TODO: Ability to reuse a script N amount of times easily?
            # Right now we just ignore the N argument....
            self.errors.extend(errors, name)
            return values

        self.errors('Unknown source `{}`.'.format(name))
        return None

    async def evaluate_pure_source(self, source):
        '''Takes a string containing exactly one source and nothing more, a special case which allows it to produce multiple values at once.'''
        match = re.match(SourceProcessor.source_regex, source)
        n, name, args = match.groups()
        name = name.lower()

        values = await self.evaluate_parsed_source(name, args, n)
        if values is not None: return values
        return([match.group()])

    async def evaluate_composite_source(self, source, context=None):
        '''Applies and replaces all {sources} in a string that mixes sources and normal characters.'''

        if context: source = Context.preprocess(source)

        #### This method is huge because I essentially unwrapped re.sub to be able to handle coroutines
        slices = []
        start = 0
        # For each match we add one item to all 3 of these lists
        items, futures, matches = [], [], []

        for match in re.finditer(SourceProcessor.source_or_item_regex, source):
            # Either the first or last three of these are None, depending on what we matched
            n, name, args, carrots, index, exclamation = match.groups()

            if name:
                ## Matched a source
                name = name.lower()
                coro = self.evaluate_parsed_source(name, args, 1) # n=1 because we only want 1 item anyway...
                # Turn it into a Future; it immediately starts the call but we only actually await it outside of this loop
                futures.append(asyncio.ensure_future(coro))
                matches.append(match.group())
                items.append(None)

            elif context:
                ## Matched an item and we have context to fill it in
                try:
                    item = context.get_item(carrots, index, exclamation)
                except ContextError as e:
                    # This is a terminal error, but we continue so we can collect more possible errors/warnings in this loop before we quit.
                    self.errors(str(e), True)
                    continue
                items.append(item or '')
                futures.append(None)
                matches.append(None)

            else:
                ## Matched an item but no context: Just ignore this match completely
                continue

            slices.append( source[start: match.start()] )
            start = match.end()

        # We encountered some kind of terminal error! Get out of here!
        if self.errors.terminal: return

        values = []
        for future, item, match in zip(futures, items, matches):
            # By construction: (item is None) XOR (future is None)
            if item is not None:
                values.append(item)
            else:
                # if await future does not deliver, fall back on the match
                results = await future
                if results is None: ## Call failed: Fall back on the match string
                    values.append(match)
                elif not results: ## Call returned an empty list: Fill in the empty string
                    values.append('')
                else: ## Call returned non-empty list: Pick the first value (best we can do?)
                    values.extend(results[0:1])

        return ''.join(val for pair in zip(slices, values) for val in pair) + source[start:]

    async def evaluate(self, source, context=None):
        '''Takes a raw source string, expands it into multiple strings, applies {sources} in each one and returns the set of values.'''
        values = []
        if len(source) > 1 and source[0] == source[-1] == '"':
            source = source[1:-1]
        for source in ChoiceTree(source, parse_flags=True, add_brackets=True).all():
            if self.is_pure_source(source):
                values.extend(await self.evaluate_pure_source(source))
            else:
                values.append(await self.evaluate_composite_source(source, context))
        return values


class ParsedPipe:
    def __init__(self, name, argstr):
        self.name = name
        self.argstr = argstr

class Pipeline:
    ''' 
        The Pipeline class parses a string containing a pipeline script into a reusable Pipeline object.
        Its state comprises only two things:
            An internal representation of the script using e.g. lists of ParsedPipes, GroupModes, Pipelines, etc.
            An ErrorLog containing errors encountered during parsing.
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
                if pipe in ['', 'nop']:
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
                        errors('Source-as-pipe `{}` received nonempty input; either use it for arguments or explicitly `remove` it.'.format(name))

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