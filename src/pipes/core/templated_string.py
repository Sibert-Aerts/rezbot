'''
File containing the TemplatedString class, and the 'Templated Element' classes that constitute a TemplatedString.

A TemplatedString is a sequence of static strings and Templated Elements, meant to be evaluated to a single string.
Templated Elements need to be evaluated to yield strings, and may vary depending state, context or randomization.

There are four types of Templated Elements:
    * Item: e.g. {}, {0}, {^1}, {2!}, {^^3!}
        These are (implicit) indexes pointing out items to use from the provided ItemScope.

    * Source: e.g. {word}, {word query=foo}, {txt bible sequential=false}
        These are evaluated as calls to their respective Source.

    * Conditional: e.g. {?foo if {0}=='bar' else baz}, {?{word} if {arg 1} LIKE /^foo/ and {get baz} != zip else {arg 2}}
        These represent an (if_case: TemplatedString, condition: Condition, else_case: TemplatedString) tuple,
            the Condition is evaluated based on both ItemScope and Context, and then depending on its value,
            either `if_case` or `else_case` is evaluated.

    * Special: e.g. {\n}, {\t}
        These are simply replaced by respective '\n' and '\t' special characters at parse time.
'''


import asyncio
from pyparsing import ParseBaseException, ParseResults

from utils.choicetree import ChoiceTree
from .logger import ErrorLog
from .context import Context, ItemScope, ItemScopeError
from . import grammar


class ParsedItem:
    ''' Class representing an Item inside a TemplatedString. '''
    carrots: int
    explicitly_indexed: bool
    index: int | None
    bang: bool

    def __init__(self, carrots: int, explicitly_indexed: bool, index: int|None, bang: bool):
        self.carrots = carrots
        self.explicitly_indexed = explicitly_indexed
        self.index = index
        self.bang = bang

    @staticmethod
    def from_parsed(result: ParseResults):
        carrots = len(result.get('carrots', ''))
        explicitly_indexed = 'index' in result
        index = int(result['index']) if 'index' in result else None
        bang = result.get('bang', '') == '!'
        return ParsedItem(carrots, explicitly_indexed, index, bang)

    def __repr__(self):
        return f'Item(%s%s%s)' % ('^'*self.carrots, self.index if self.explicitly_indexed else '', '!' if self.bang else '')
    def __str__(self):
        return '{%s%s%s}' % ('^'*self.carrots, self.index if self.explicitly_indexed else '', '!' if self.bang else '')

    def evaluate(self, scope: ItemScope) -> str:
        if scope is None: raise ItemScopeError('No scope!')
        return scope.get_item(self.carrots, self.index, self.bang)


class ParsedSource:
    ''' Class representing a Source inside a TemplatedString. '''
    NATIVE_SOURCE = object()
    MACRO_SOURCE  = object()
    NATIVE_PIPE   = object()
    MACRO_PIPE    = object()
    UNKNOWN       = object()

    name: str
    amount: str | int | None
    args: 'Arguments'
    pre_errors: ErrorLog
    type: object

    def __init__(self, name: str, args: 'Arguments', amount: str | int | None=None, remainder: 'TemplatedString'=None):
        self.name = name.lower()
        self.amount = amount
        self.remainder = remainder
        self.args = args
        self.pre_errors = ErrorLog()

        if self.name in sources:
            self.type = ParsedSource.NATIVE_SOURCE
            self.source = sources[self.name]
        elif self.name in pipes:
            self.type = ParsedSource.NATIVE_PIPE
            self.pipe = pipes[self.name]
        elif self.name in pipe_macros:
            self.type = ParsedSource.MACRO_PIPE
        elif self.name in source_macros:
            self.type = ParsedSource.MACRO_SOURCE
        else:
            self.type = ParsedSource.UNKNOWN

    @staticmethod
    def from_parsed(parsed: ParseResults):
        name = parsed['source_name'].lower()

        # Determine the "amount"
        if 'amount' in parsed:
            amt = parsed['amount']
            if amt == 'ALL': amount = 'all'
            else: amount = int(amt)
        else: amount = None

        # Parse the Arguments, for which we need to know if it's a Source or a Pipe (if either)
        signature = None
        greedy = True
        if name in sources:
            signature = sources[name].signature
        if name in pipes:
            signature = pipes[name].signature
            greedy = False
        args, remainder, pre_errors = Arguments.from_parsed(parsed.get('args'), signature, greedy=greedy)

        parsed_source = ParsedSource(name, args, amount, remainder)
        parsed_source.pre_errors.extend(pre_errors)
        return parsed_source

    def __repr__(self):
        bits = [self.name, repr(self.args)]
        if self.amount is not None: bits.append(self.amount)
        return 'Source(%s)' % ', '.join(bits)
    def __str__(self):
        bits = []
        if self.amount is not None: bits.append(self.amount)
        bits.append(self.name)
        if self.args: bits.append(str(self.args))
        return '{%s}' % ' '.join(bits)

    # ================ Evaluation

    async def evaluate(self, context: Context, scope: ItemScope, args: dict=None) -> tuple[ list[str] | None, ErrorLog ]:
        '''
        Evaluate this `{source}` expression, there are four cases:
        * We are a native Source: Straightforwardly call Source.generate
        * We are a native Pipe: Evaluate the Arguments' remainder, and feed it into the Pipe.apply
        * We are a Source Macro: Perform a variant of PipelineWithOrigin.execute
        * We are a Pipe Macro: Evaluate the Arguments' remainder, and feet it into Pipeline.apply
        '''
        errors = ErrorLog()
        errors.extend(self.pre_errors)
        NOTHING_BUT_ERRORS = (None, errors)
        if errors.terminal: return NOTHING_BUT_ERRORS

        ## Determine the arguments if needed
        if args is None:
            args, arg_errors = await self.args.determine(context, scope)
            errors.extend(arg_errors, self.name)
            if errors.terminal: return NOTHING_BUT_ERRORS

        ### CASE: Native Source
        if self.type == ParsedSource.NATIVE_SOURCE:
            try:
                return await self.source.generate(context, args, n=self.amount), errors
            except Exception as e:
                errors.log(f'Failed to evaluate Source `{self.name}` with args {args}:\n\t{type(e).__name__}: {e}', True)
                return NOTHING_BUT_ERRORS

        ### CASE: Native Pipe
        elif self.type == ParsedSource.NATIVE_PIPE:
            # Evaluate the remainder first
            remainder_str, remainder_errors = await self.remainder.evaluate(context, scope)
            errors.extend(remainder_errors, self.name)
            if errors.terminal: return NOTHING_BUT_ERRORS
            try:
                return await self.pipe.apply([remainder_str], **args), errors
            except Exception as e:
                errors.log(f'Failed to evaluate Pipe-as-Source `{self.name}` with args {args}:\n\t{type(e).__name__}: {e}', True)
                return NOTHING_BUT_ERRORS

        ### CASE: Macro Source
        elif self.name in source_macros:
            macro = source_macros[self.name]
            ## STEP 1: Ensure arguments are passed to the Macro
            try:
                # NEWFANGLED: Get the set of arguments and put them in Context
                # TODO: Put the implicit 'amount' argument in args
                args = macro.apply_signature(args)
                macro_ctx = context.into_macro(macro, args)
                # DEPRECATED: Insert arguments into Macro string
                code = macro.apply_args(args)
            except ArgumentError as e:
                errors.log(e, True, context=self.name)
                return NOTHING_BUT_ERRORS

            #### Fast-tracked, no-side-effect version of PipelineWithOrigin.execute:
            origin, code = PipelineWithOrigin.split(code)

            ## STEP 2: Get the values from the Macro's origin
            values, origin_errors = await TemplatedString.evaluate_origin(origin, macro_ctx)
            errors.extend(origin_errors, self.name)
            if errors.terminal: return NOTHING_BUT_ERRORS

            ## STEP 3: Apply
            pipeline = source_macros.pipeline_from_code(code)
            values, pl_errors, _ = await pipeline.apply(values, macro_ctx)
            errors.extend(pl_errors, self.name)
            return values, errors

        ## CASE: Macro Pipe
        elif self.name in pipe_macros:
            macro = pipe_macros[self.name]
            ## STEP 1: Ensure arguments are passed to the Macro
            try:
                # NEWFANGLED: Get the set of arguments and put them in Context
                args = macro.apply_signature(args)
                macro_ctx = context.into_macro(macro, args)
                # DEPRECATED: Insert arguments into Macro string
                code = macro.apply_args(args)
            except ArgumentError as e:
                errors.log(e, True, context=self.name)
                return NOTHING_BUT_ERRORS

            ## STEP 2: Evaluate the remainder
            remainder_str, remainder_errors = await self.remainder.evaluate(context, scope)
            errors.extend(remainder_errors, self.name)
            if errors.terminal: return NOTHING_BUT_ERRORS

            ## STEP 3: Apply
            pipeline = pipe_macros.pipeline_from_code(code)
            values, pl_errors, _ = await pipeline.apply([remainder_str], macro_ctx)
            errors.extend(pl_errors, self.name)
            return values, errors

        else:
            errors(f'Unknown source `{self.name}`.', True)
            return NOTHING_BUT_ERRORS


class ParsedConditional:
    ''' Class representing an inline IF/ELSE conditional expression inside a TemplatedString. '''

    def __init__(self, case_if: 'TemplatedString', condition: 'Condition', case_else: 'TemplatedString'):
        self.case_if = case_if
        self.condition = condition
        self.case_else = case_else

    @staticmethod
    def from_parsed(parsed: ParseResults):
        case_if = TemplatedString.from_parsed(parsed['case_if'][0])
        condition = Condition.from_parsed(parsed['condition'])
        case_else = TemplatedString.from_parsed(parsed['case_else'][0])
        return ParsedConditional(case_if, condition, case_else)

    def __repr__(self):
        return 'Conditional(%s, %s, %s)' % (repr(self.case_if), repr(self.condition), repr(self.case_else))
    def __str__(self):
        return '{? %s if %s else %s}' % (str(self.case_if), str(self.condition), str(self.case_else))

    # ================ Evaluation

    async def evaluate(self, context: Context, scope: ItemScope) -> tuple[ list[str] | None, ErrorLog ]:
        errors = ErrorLog()
        cond_value, cond_errors = await self.condition.evaluate(context, scope)
        if errors.extend(cond_errors, 'condition').terminal:
            return None, errors
        if cond_value:
            return await self.case_if.evaluate(context, scope)
        else:
            return await self.case_else.evaluate(context, scope)


class ParsedSpecialSymbol:
    ''' 'Class' translating special symbol codes `{\n}` directly into the symbol, never actually instantiated. '''
    SPECIAL_SYMBOL_MAP = {
        'n': '\n',
        't': '\t',
    }

    @staticmethod
    def from_parsed(result: ParseResults):
        name = result.get('name')
        result = ParsedSpecialSymbol.SPECIAL_SYMBOL_MAP.get(name)
        if result is None:
            raise ValueError(f'Unknown special symbol "\{name}".')
        return result


class TemplatedString:
    '''
    Class representing a string that may contain Sources or Items, which may be evaluated to yield strings.

    Preferably instantiated via the `from_string` or `from_parsed` static methods.

    If there is no need to hold on to the parsed TemplatedString, the static methods `evaluate_string` and `evaluate_origin` can be used instead.
    '''

    pieces: list[str | ParsedItem | ParsedConditional | ParsedSource]
    pre_errors: ErrorLog
    end_index: int = -1

    is_string = False
    string: str = None
    is_source = False
    source: ParsedSource = None

    def __init__(self, pieces: list[str | ParsedItem | ParsedConditional | ParsedSource], start_index: int=0, index_items=True):
        self.pieces = pieces
        self.pre_errors = ErrorLog()

        if index_items:
            self.assign_implicit_item_indices(start_index)

        # For simplicity, an empty list is normalised to an empty string
        self.pieces = self.pieces or ['']

        ## Determine if we're a very simple kind of TemplatedString
        if len(self.pieces) == 1:
            self.is_string = isinstance(self.pieces[0], str)
            if self.is_string: self.string = self.pieces[0]

            self.is_source = isinstance(self.pieces[0], ParsedSource)
            if self.is_source: self.source = self.pieces[0]

    @staticmethod
    def from_parsed(result: ParseResults=[], start_index=0):
        pre_errors = ErrorLog()
        pieces = []

        def append_string(s):
            if not pieces or not isinstance(pieces[-1], str):
                pieces.append(s)
            else:
                pieces[-1] += s

        # Match and parse the different kinds of pieces that make up the TemplatedString
        for result_piece in result:
            if isinstance(result_piece, str):
                append_string(result_piece)
                continue

            match result_piece._name:
                case 'te_special':
                    try:
                        item = ParsedSpecialSymbol.from_parsed(result_piece)
                        append_string(item)
                    except ValueError as v:
                        pre_errors.log(str(v), terminal=True)

                case 'item':
                    item = ParsedItem.from_parsed(result_piece)
                    pieces.append(item)

                case 'conditional':
                    conditional = ParsedConditional.from_parsed(result_piece)
                    pieces.append(conditional)
                    # TODO: Pre-errors

                case 'source':
                    source = ParsedSource.from_parsed(result_piece)
                    pieces.append(source)
                    pre_errors.steal(source.pre_errors, source.name)

                case _:
                    raise Exception()

        string = TemplatedString(pieces, start_index)
        string.pre_errors.extend(pre_errors)
        # Catch edge case: A TS with pre_errors cannot be a string
        if string.pre_errors:
            string.is_string = False
        return string

    @staticmethod
    def from_string(string: str):
        parsed = grammar.absolute_templated_string.parse_string(string, parse_all=True)
        return TemplatedString.from_parsed(parsed)

    def assign_implicit_item_indices(self, start_index):
        ''' Runs through all implicitly indexed items and assigns them increasing indices, or recursively adjusts existing ones. '''
        item_index = start_index
        explicit_item, implicit_item = False, False
        # TODO: this currently does not work as intended due to nesting:
        # "{} {roll max={}} {}" == "{0} {roll max={0}} {1}"
        for piece in self.pieces:
            # TODO: Account for ParsedConditional
            if isinstance(piece, ParsedSource):
                item_index = piece.args.adjust_implicit_item_indices(item_index)
            elif isinstance(piece, ParsedItem):
                if piece.explicitly_indexed:
                    explicit_item = True
                else:
                    implicit_item = True
                    piece.index = item_index
                    item_index += 1

        self.end_index = item_index

        if explicit_item and implicit_item:
            self.pre_errors.log('Do not mix empty `{}`\'s with numbered `{}`\'s!', True)

    def adjust_implicit_item_indices(self, new_start_index):
        ''' Recursively adjust all implicit item indices by a flat amount and return the new end index. '''
        for piece in self.pieces:
            # TODO: Account for ParsedConditional
            if isinstance(piece, ParsedSource):
                piece.args.adjust_implicit_item_indices(new_start_index)
            elif isinstance(piece, ParsedItem) and not piece.explicitly_indexed:
                piece.index += new_start_index
        self.end_index += new_start_index
        return self.end_index

    def __repr__(self):
        return 'Tstr(%s)' % ', '.join(repr(x) for x in self.pieces)
    def __str__(self):
        return '"' + ''.join(str(x) for x in self.pieces) + '"'
    def __bool__(self):
        # A working TemplatedString is falsey if and only if it represents the static empty string.
        return not (self.is_string and not self.pieces[0])

    # ================ Manipulation

    @staticmethod
    def join(tstrings: list['TemplatedString']) -> 'TemplatedString':
        ''' Joins the TemplatedStrings together as one long TemplatedString, without re-indexing implicit items. '''
        result = TemplatedString([piece for ts in tstrings for piece in ts.pieces], index_items=False)
        for ts in tstrings:
            result.pre_errors.extend(ts.pre_errors)
        # Catch edge case: A TS with pre_errors cannot be a string
        if result.pre_errors:
            result.is_string = False
        return result

    def unquote(self) -> 'TemplatedString':
        ''' Modifies the TemplatedString to remove wrapping string delimiters, if present. '''
        pieces = self.pieces

        if isinstance(pieces[0], str) and isinstance(pieces[-1], str):
            if pieces[0][:3] == pieces[-1][-3:] == '"""' and not (self.is_string and len(pieces[0]) < 6):
                pieces[0] = pieces[0][3:]
                pieces[-1] = pieces[-1][:-3]
            elif pieces[0][:1] == pieces[-1][-1:] in ('"', "'", '/') and not (self.is_string and len(pieces[0]) < 2):
                pieces[0] = pieces[0][1:]
                pieces[-1] = pieces[-1][:-1]
            if self.is_string:
                self.string: str = self.pieces[0]

        return self

    def split_implicit_arg(self, greedy: bool) -> tuple['TemplatedString', 'TemplatedString | None']:
        ''' Splits the TemplatedString into an implicit arg and a "remainder" TemplatedString. '''
        if greedy:
            return self.unquote(), None
        else:
            # This applies the TemplatedString version of .split(' ', 1), probably doesn't need to be more than this.
            implicit = []
            remainder = []
            for i in range(len(self.pieces)):
                piece = self.pieces[i]
                if isinstance(piece, str):
                    if ' ' in piece:
                        piece1, piece2 = piece.split(' ', 1)
                        implicit.append(piece1)
                        remainder = [piece2] + self.pieces[i+1:]
                        break
                    else:
                        implicit.append(piece)
                else:
                    implicit.append(piece)

            return TemplatedString(implicit).unquote(), TemplatedString(remainder)

    # ================ Evaluation

    async def evaluate(self, context: Context, scope: ItemScope=None) -> tuple[str|None, ErrorLog]:
        ''' Evaluate the TemplatedString into a string '''
        errors = ErrorLog()
        errors.extend(self.pre_errors)
        NOTHING_BUT_ERRORS = (None, errors)

        if errors.terminal:
            return NOTHING_BUT_ERRORS
        if self.is_string:
            return self.string, errors

        SOURCE_FUTURE = object()
        COND_FUTURE = object()
        results = []
        futures = []

        ## Go through our pieces and collect either immediately retrievable strings,
        #   or string-determining coroutines (i.e. futures).
        for piece in self.pieces:
            if isinstance(piece, str):
                results.append(piece)

            elif isinstance(piece, ParsedItem):
                try:
                    results.append(piece.evaluate(scope))
                except ItemScopeError as e:
                    msg = f'Error filling in item `{piece}`:\n\tItemScopeError: {e}'
                    errors.log(msg, True)

            elif isinstance(piece, ParsedConditional) and not errors.terminal:
                results.append(COND_FUTURE)
                futures.append(piece.evaluate(context, scope))

            elif isinstance(piece, ParsedSource) and not errors.terminal:
                results.append(SOURCE_FUTURE)
                futures.append(piece.evaluate(context, scope))

        if errors.terminal:
            return NOTHING_BUT_ERRORS

        ## Await all future results at once
        future_results = await asyncio.gather(*futures)

        ## Join the collected results and future results
        strings = []
        future_index = 0
        for result in results:
            if result is SOURCE_FUTURE:
                items, src_errors = future_results[future_index]
                errors.extend(src_errors)
                if not errors.terminal:
                    strings.append(items[0] if items else '')
                future_index += 1
            elif result is COND_FUTURE:
                string, cond_errors = future_results[future_index]
                errors.extend(cond_errors)
                if not errors.terminal:
                    strings.append(string)
                future_index += 1
            else:
                strings.append(result)

        if errors.terminal:
            return NOTHING_BUT_ERRORS

        return ''.join(strings), errors

    # ================ Specific fast-tracked use cases

    @staticmethod
    async def evaluate_string(string: str, context: Context, scope: ItemScope, force_single=False) -> tuple[list[str] | None, ErrorLog]:
        '''
        Takes a raw source string, evaluates {sources} and returns the list of values.

        If force_single=False, a pure "{source}" string may generate more (or less!) than 1 value.
        '''
        errors = ErrorLog()
        NOTHING_BUT_ERRORS = (None, errors)
        try:
            template = TemplatedString.from_string(string)
            errors.extend(template.pre_errors)
            if errors.terminal:
                return NOTHING_BUT_ERRORS
        except ParseBaseException as e:
            errors.log_parse_exception(e)
            return NOTHING_BUT_ERRORS

        if not force_single and template.is_source:
            vals, errs = await template.source.evaluate(context, scope)
            return vals, errs
        else:
            val, errs = await template.evaluate(context, scope)
            return [val], errs

    @staticmethod
    def parse_origin(origin_str: str) -> tuple[list['TemplatedString'] | None, ErrorLog]:
        '''Takes a raw source string, expands it if necessary, and already parses each one as a TemplatedString.'''
        origins = []
        expand = True
        errors = ErrorLog()

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

    @staticmethod
    async def evaluate_origin(origin_str: str, context: Context, scope: ItemScope=None) -> tuple[list[str] | None, ErrorLog]:
        '''Takes a raw source string, expands it if necessary, evaluates {sources} in each one and returns the list of values.'''
        origins, errors = TemplatedString.parse_origin(origin_str)
        if errors.terminal:
            return (None, errors)

        values = []
        for origin in origins:
            if origin.is_source:
                vals, errs = await origin.source.evaluate(context, scope)
                errors.extend(errs)
                if not errors.terminal: values.extend(vals)
            else:
                val, errs = await origin.evaluate(context, scope)
                errors.extend(errs)
                if not errors.terminal: values.append(val)

        return values, errors


# þeſe lynes art doƿn here due to dependencys circulaire
from .pipeline_with_origin import PipelineWithOrigin
from .signature import ArgumentError, Arguments
from pipes.implementations.sources import sources
from pipes.implementations.pipes import pipes
from .macros import source_macros, pipe_macros
from .conditions import Condition
