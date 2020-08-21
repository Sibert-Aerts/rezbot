import re
import asyncio
from .logger import ErrorLog
from .macros import source_macros
from utils.choicetree import ChoiceTree
from .sources import sources
from .processor import Pipeline, PipelineProcessor


class ContextError(ValueError):
    '''Special error used by the Context class when a context string cannot be fulfilled.'''

class Context:
    def __init__(self, parent=None, source_processor=None, items=None):
        self.items = items or []
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

    def extract_ignored(self):
        ### Merge the sets into a clear view:
        # If "conflicting" instances occur (i.e. both {0} and {0!}) give precedence to the {0!}
        # Since the ! is an intentional indicator of what they want to happen; Do not remove the item
        to_be = [ (i, True) for i in self.to_be_removed.difference(self.to_be_ignored) ] + [ (i, False) for i in self.to_be_ignored ]
        
        # Finnicky list logic for ignoring/removing the appropriate indices
        to_be.sort(key=lambda x: x[0], reverse=True)
        ignored = []
        items = list(self.items)
        for i, rem in to_be:
            if not rem: ignored.append(self.items[i])
            del items[i]
        ignored.reverse()

        return ignored, items


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

    _source_regex = r'(?i){\s*(ALL|\d*)\s*([_a-z][\w]*)\s*((?:\"[^\"]*\"|[^}])*)?}'
    #                          ^^^^^^^     ^^^^^^^^^^^     ^^^^^^^^^^^^^^^^^^^^
    #                             n            name                args
    source_regex = re.compile(_source_regex)

    # This one matches both sources and items, so any syntactically meaningful instance of curly braces in string literals.
    # It has 6 capture groups: n, name, args, carrots, index, exclamation
    source_or_item_regex = re.compile('(?:' + _source_regex + '|' + Context._item_regex + ')')

    def is_pure_source(self, source):
        '''Checks whether a string matches the exact format "{[n] source [args]}", AKA "pure".'''
        return re.fullmatch(SourceProcessor.source_regex, source)

    async def evaluate_parsed_source(self, name, argstr, n=None):
        '''Given the exact name, argstring and `n` of a source, attempts to find and evaluate it.'''
        if name in sources:
            source = sources[name]
            args, errors, _ = await source.signature.parse_and_determine(argstr, self, context=None)
            self.errors.extend(errors, context=name)
            if errors.terminal: return None
            try:
                return await source(self.message, args, n=n)
            except Exception as e:
                argfmt = ' '.join( f'`{p}`={args[p]}' for p in args )
                self.errors(f'Failed to evaluate source `{name}` with args {argfmt}:\n\t{e.__class__.__name__}: {e}', True)
                return None

        elif name in source_macros:
            code = source_macros[name].apply_args(args)
            # Dressed-down version of PipelineProcessor.execute_script:
            source, code = PipelineProcessor.split(code)
            ## STEP 1: create a new SourceP. so we can contextualise errors
            source_processor = SourceProcessor(self.message)
            values = await source_processor.evaluate(source)
            self.errors.extend(source_processor.errors, name)
            ## STEP 2: parse the Pipeline (but check the cache first)
            if code in source_macros.pipeline_cache:
                pipeline = source_macros.pipeline_cache[code]
            else:
                pipeline = Pipeline(code)
                source_macros.pipeline_cache[code] = pipeline
            ## STEP 3: apply
            # TODO: Ability to reuse a script N amount of times easily?
            # Right now we just ignore the N argument....
            values, _, pl_errors, _ = await pipeline.apply(values, self.message)
            self.errors.extend(pl_errors, name)
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
        for source in ChoiceTree(source, parse_flags=True, add_brackets=True):
            if self.is_pure_source(source):
                values.extend(await self.evaluate_pure_source(source))
            else:
                values.append(await self.evaluate_composite_source(source, context))
        return values
