'''
There are five types of Templated Elements:
    * Item: e.g. {}, {0}, {^1}, {2!}, {^^3!}
        These are (implicit) indexes pointing out items to use from the provided ItemScope.

    * Source: e.g. {word}, {word query=foo}, {txt bible sequential=false}
        These are evaluated as calls to their respective Source.

    * Conditional: e.g. {?foo if {0}=='bar' else baz}, {?{word} if {arg 1} LIKE /^foo/ and {get baz} != zip else {arg 2}}
        These represent an (if_case: TemplatedString, condition: Condition, else_case: TemplatedString) tuple,
            the Condition is evaluated based on both ItemScope and Context, and then depending on its value,
            either `if_case` or `else_case` is evaluated.

    * InlineScript: e.g. {>> {word} > find_all . > join +}
        The script (whose syntax is limited) is evaluated.

    * Special: e.g. {\n}, {\t}
        These are simply replaced by respective '\n' and '\t' special characters at parse time.
'''

from pyparsing import ParseResults
from typing import TypeAlias, Literal, NamedTuple

from .logger import ErrorLog
from .context import Context, ItemScope, ItemScopeError


class ParsedItem:
    ''' Class representing an Item inside a TemplatedString. '''
    Index = NamedTuple('ParsedItemIndex', [
        ('carrots', int),
        ('index', int),
        ('bang', bool)
    ])
    Range = NamedTuple('ParsedItemRange', [
        ('carrots', int),
        ('start', int | None),
        ('end', int | Literal[False] | None),
        ('bang', bool)
    ])

    __slots__ = ('is_implicit', 'indices', 'implicit_carrots', 'implicit_index', 'implicit_bang')

    indices: list[Index | Range]
    # Implicit
    is_implicit: bool
    implicit_carrots: int
    implicit_index: int
    implicit_bang: bool

    def __init__(self, is_implicit: bool, indices: list[Index]=None, implicit_carrots: int=None, implicit_bang: bool=None):
        self.is_implicit = is_implicit
        self.indices = indices
        # TODO: Deprecate implicit_carrots syntax, and maybe also implicit_bang,
        #   if you want to be implicit you can't also be doing fancy things?
        self.implicit_carrots = implicit_carrots
        self.implicit_index = None
        self.implicit_bang = implicit_bang

    @staticmethod
    def from_parsed(result: ParseResults):
        if result._name == 'implicit_item':
            return ParsedItem(is_implicit=True, implicit_carrots=len(result.get('carrots', '')), implicit_bang=bool(result.get('bang')))

        elif result._name == 'explicit_item':
            indices = []
            for index_result in result['indices']:
                index_result: ParseResults
                carrots = len(index_result.get('carrots', ''))
                bang = index_result.get('bang', '') == '!'
                if 'index' in index_result:
                    index = int(index_result['index'])
                    indices.append(ParsedItem.Index(carrots, index, bang))
                else:
                    start = int(s) if (s := index_result['interval'].get('start')) else None
                    end = int(e) if (e := index_result['interval'].get('end')) else None
                    indices.append(ParsedItem.Range(carrots, start, end, bang))
            return ParsedItem(is_implicit=False, indices=indices)

        else:
            raise Exception(f'Unexpected ParseResult._name: {result._name}')

    def __repr__(self):
        if self.is_implicit:
            return f'Item(is_implicit=True, carrots={self.implicit_carrots}, index={self.implicit_index}, bang={self.implicit_bang})'
        indices = []
        for i in self.indices:
            if isinstance(i, ParsedItem.Index):
                indices.append(f'(carrots={i.carrots}, index={i.index}, bang={i.bang})')
            else:
                indices.append(f'(carrots={i.carrots}, start={i.start}, end={i.end}, bang={i.bang})')
        return 'Item(is_implicit=False, [%s])' % ', '.join(indices)
    def __str__(self):
        if self.is_implicit:
            return '{%s%s}' % ('^'*self.implicit_carrots, '!' if self.implicit_bang else '')
        indices = []
        for i in self.indices:
            if isinstance(i, ParsedItem.Index):
                indices.append('%s%d%s' % ('^'*i.carrots, i.index, '!' if i.bang else ''))
            else:
                indices.append('%s%s:%s%s' % ('^'*i.carrots, i.start if i.start is not None else '', i.end if i.end is not None else '', '!' if i.bang else ''))
        return '{%s}' % ','.join(indices)

    def evaluate(self, scope: ItemScope) -> list[str]:
        if scope is None: raise ItemScopeError('No scope!')
        if self.is_implicit:
            return [scope.get_item(0, self.implicit_index, self.implicit_bang)]
        items = []
        for index in self.indices:
            if isinstance(index, ParsedItem.Index):
                items.append(scope.get_item(index.carrots, index.index, index.bang))
            else:
                items.extend(scope.get_items(index.carrots, index.start, index.end, index.bang))
        return items

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

        if self.name in NATIVE_SOURCES:
            self.type = ParsedSource.NATIVE_SOURCE
            self.source = NATIVE_SOURCES[self.name]
        elif self.name in NATIVE_PIPES:
            self.type = ParsedSource.NATIVE_PIPE
            self.pipe = NATIVE_PIPES[self.name]
        elif self.name in MACRO_PIPES:
            self.type = ParsedSource.MACRO_PIPE
        elif self.name in MACRO_SOURCES:
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
        if name in NATIVE_SOURCES:
            signature = NATIVE_SOURCES[name].signature
        if name in NATIVE_PIPES:
            signature = NATIVE_PIPES[name].signature
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
        elif self.name in MACRO_SOURCES:
            macro = MACRO_SOURCES[self.name]
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
            pipeline = MACRO_SOURCES.pipeline_from_code(code)
            values, pl_errors, _ = await pipeline.apply(values, macro_ctx)
            errors.extend(pl_errors, self.name)
            return values, errors

        ## CASE: Macro Pipe
        elif self.name in MACRO_PIPES:
            macro = MACRO_PIPES[self.name]
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
            pipeline = MACRO_PIPES.pipeline_from_code(code)
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
        symbol = ParsedSpecialSymbol.SPECIAL_SYMBOL_MAP.get(name)
        if symbol is None:
            raise ValueError(f'Unknown special symbol "\{name}".')
        return symbol


class ParsedInlineScript:
    ''' Class representing an inline script inside a TemplatedString. '''

    def __init__(self, script: 'PipelineWithOrigin'):
        self.script = script

    @staticmethod
    def from_parsed(parsed: ParseResults):
        return ParsedInlineScript(PipelineWithOrigin.from_parsed_simple_script(parsed['inline_script']))

    def __repr__(self):
        return 'InlScript(%s)' % repr(self.script)
    def __str__(self):
        return '{>> %s}' % str(self.script)

    # ================ Evaluation

    async def evaluate(self, context: Context, scope: ItemScope) -> tuple[ list[str] | None, ErrorLog ]:
        values, errors, spout_state = await self.script.execute_without_side_effects(context, scope)
        return values, errors


# NOTE: No ParsedSpecialSymbol since that class is never instantiated
ParsedTemplatedElement: TypeAlias = ParsedItem | ParsedSource | ParsedConditional | ParsedInlineScript


# þeſe lynes art doƿn here due to dependencys circulaire
from .templated_string import TemplatedString
from .pipeline_with_origin import PipelineWithOrigin
from .signature import ArgumentError, Arguments
from pipes.implementations.sources import NATIVE_SOURCES
from pipes.implementations.pipes import NATIVE_PIPES
from .macros import MACRO_SOURCES, MACRO_PIPES
from .conditions import Condition