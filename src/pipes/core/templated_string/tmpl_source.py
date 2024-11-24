from pyparsing import ParseResults

from ..state.error_log import ErrorLog
from ..state.context import Context
from ..state.item_scope import ItemScope
from ..pipeline import Pipeline
from ..signature import ArgumentError, Arguments

from pipes.implementations.sources import NATIVE_SOURCES
from pipes.implementations.pipes import NATIVE_PIPES
from ..macros import MACRO_SOURCES, MACRO_PIPES

from .templated_string import TemplatedString


class TmplSource:
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

    def __init__(self, name: str, args: 'Arguments', amount: str | int | None=None, remainder: TemplatedString=None):
        self.name = name.lower()
        self.amount = amount
        self.remainder = remainder
        self.args = args
        self.pre_errors = ErrorLog()

        if self.name in NATIVE_SOURCES:
            self.type = TmplSource.NATIVE_SOURCE
            self.source = NATIVE_SOURCES[self.name]
        elif self.name in NATIVE_PIPES:
            self.type = TmplSource.NATIVE_PIPE
            self.pipe = NATIVE_PIPES[self.name]
        elif self.name in MACRO_PIPES:
            self.type = TmplSource.MACRO_PIPE
        elif self.name in MACRO_SOURCES:
            self.type = TmplSource.MACRO_SOURCE
        else:
            self.type = TmplSource.UNKNOWN

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

        parsed_source = TmplSource(name, args, amount, remainder)
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
        * We are a Native Source: Straightforwardly call Source.generate
        * We are a Native Pipe: Evaluate the Arguments' remainder, and feed it into the Pipe.apply
        * We are a Macro Source: Perform Pipeline.apply on no values
        * We are a Macro Pipe: Evaluate the Arguments' remainder, and feed it into Pipeline.apply
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
        if self.type == TmplSource.NATIVE_SOURCE:
            try:
                return await self.source.generate(context, args, n=self.amount), errors
            except Exception as e:
                errors.log(f'Failed to evaluate Source `{self.name}` with args {args}:\n\t{type(e).__name__}: {e}', True)
                return NOTHING_BUT_ERRORS

        ### CASE: Native Pipe
        elif self.type == TmplSource.NATIVE_PIPE:
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
                # Get the set of arguments and put them in Context
                args = macro.apply_signature(args, source_amount=self.amount)
                macro_ctx = context.into_macro(macro, args)
            except ArgumentError as e:
                errors.log(e, True, context=self.name)
                return NOTHING_BUT_ERRORS

            ## STEP 2: Apply Pipeline
            pipeline = Pipeline.from_string_with_origin(macro.code)
            values, pl_errors, _ = await pipeline.apply((), macro_ctx)
            return values, errors.extend(pl_errors, self.name)

        ## CASE: Macro Pipe
        elif self.name in MACRO_PIPES:
            macro = MACRO_PIPES[self.name]
            ## STEP 1: Ensure arguments are passed to the Macro
            try:
                args = macro.apply_signature(args)
                macro_ctx = context.into_macro(macro, args)
            except ArgumentError as e:
                errors.log(e, True, context=self.name)
                return NOTHING_BUT_ERRORS

            ## STEP 2: Evaluate the remainder
            remainder_str, remainder_errors = await self.remainder.evaluate(context, scope)
            errors.extend(remainder_errors, self.name)
            if errors.terminal: return NOTHING_BUT_ERRORS

            ## STEP 3: Apply Pipeline
            pipeline = Pipeline.from_string(macro.code)
            values, pl_errors, _ = await pipeline.apply([remainder_str], macro_ctx)
            return values, errors.extend(pl_errors, self.name)

        else:
            errors.log(f'Unknown source `{self.name}`.', True)
            return NOTHING_BUT_ERRORS
