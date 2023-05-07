import asyncio
from pyparsing import ParseException, ParseResults

import discord

from .processor import PipelineProcessor
from .pipeline import Pipeline
from . import grammar
from .context import Context, ContextError
from .signature import ArgumentError, Arguments
from .implementations.sources import sources
from .macros import source_macros
from .logger import ErrorLog

from utils.choicetree import ChoiceTree


class ParsedItem:
    ''' Class representing an Item inside a TemplatedString. '''
    def __init__(self, item: ParseResults):
        self.carrots = len(item.get('carrots', ''))
        self.explicitlyIndexed = ('index' in item)
        self.index = int(item['index']) if 'index' in item else None
        self.bang = item.get('bang', '') == '!'
        
    def __str__(self):
        return '{%s%s%s}' %( '^'*self.carrots, self.index if self.explicitlyIndexed else '', '!' if self.bang else '')
    def __repr__(self):
        return 'Item' + str(self)

    def evaluate(self, context: Context=None) -> str:
        if context:
            return context.get_parsed_item(self.carrots, self.index, self.bang)
        return str(self)


class ParsedSource:
    ''' Class representing a Source inside a TemplatedString. '''
    NATIVE_SOURCE = object()
    MACRO_SOURCE  = object()
    UNKNOWN      = object()

    def __init__(self, name: str, args: Arguments, amount: str | int | None):
        self.name = name.lower()
        self.amount = amount
        self.args = args
        self.pre_errors = ErrorLog()
        
        if self.name in sources:
            self.type = ParsedSource.NATIVE_SOURCE
            self.source = sources[self.name]
        elif self.name in source_macros:
            self.type = ParsedSource.MACRO_SOURCE
        else:
            self.type = ParsedSource.UNKNOWN            

    @staticmethod
    def from_parsed(parsed: ParseResults):
        name = parsed['source_name'].lower()

        if 'amount' in parsed:
            amt = parsed['amount']
            if amt == 'ALL': amount = 'all'
            else: amount = int(amt)
        else: amount = None

        signature = sources[name].signature if name in sources else None
        args, _, pre_errors = Arguments.from_parsed(parsed.get('args'), signature)

        parsedSource = ParsedSource(name, args, amount)
        parsedSource.pre_errors.extend(pre_errors)
        return parsedSource

    def __str__(self):
        return '{%s %s %s}' %( self.amount or '', self.name, repr(self.args) if self.args else '' )
    def __repr__(self):
        return 'Source' + str(self)

    async def evaluate(self, message=None, context=None, args=None) -> tuple[ list[str] | None, ErrorLog ]:
        ''' Find some values for the damn Source that we are. '''
        errors = ErrorLog()
        if self.pre_errors: errors.extend(self.pre_errors)
        NOTHING_BUT_ERRORS = (None, errors)
        if errors.terminal: return NOTHING_BUT_ERRORS

        if not (self.name in sources or self.name in source_macros):
            errors(f'Unknown source `{self.name}`.', True)
            return NOTHING_BUT_ERRORS

        if args is None:
            ## Determine the arguments
            args, argErrors = await self.args.determine(message, context)
            errors.extend(argErrors, self.name)
            if errors.terminal: return NOTHING_BUT_ERRORS

        ### CASE: Native Source
        if self.type == ParsedSource.NATIVE_SOURCE:
            try:
                return await self.source.generate(message, args, n=self.amount), errors
            except Exception as e:
                errors(f'Failed to evaluate source `{self.name}` with args {args}:\n\t{type(e).__name__}: {e}', True)
                return NOTHING_BUT_ERRORS

        ### CASE: Macro Source
        elif self.name in source_macros:
            try:
                code = source_macros[self.name].apply_args(args)
            except ArgumentError as e:
                errors.log(e, True, context=self.name)
                return NOTHING_BUT_ERRORS

            #### Fast-tracked version of PipelineProcessor.execute_script:
            origin, code = PipelineProcessor.split(code)

            ## STEP 1: Get the values from the Macro's origin            
            values, origin_errors = await TemplatedString.evaluate_origin(origin, message, context)
            errors.extend(origin_errors, self.name)
            if errors.terminal: return NOTHING_BUT_ERRORS

            ## STEP 2: parse the Pipeline (but check the cache first)
            if code in source_macros.pipeline_cache:
                pipeline = source_macros.pipeline_cache[code]
            else:
                pipeline = Pipeline(code)
                source_macros.pipeline_cache[code] = pipeline

            ## STEP 3: apply
            # TODO: Actually use the "amount" somehow
            values, _, pl_errors, _ = await pipeline.apply(values, message)
            errors.extend(pl_errors, self.name)
            return values, errors


class TemplatedString:
    ''' 
    Class representing a string that may contain Sources or Items, which may be evaluated to yield strings.

    Preferably instantiated via the `from_string` or `from_parsed` static methods.

    If there is no need to hold on to the parsed TemplatedString, the static methods `evaluate_string` and `evaluate_origin` can be used instead.
    '''

    pieces: list[str | ParsedSource | ParsedItem]
    pre_errors: ErrorLog
    end_index: int

    is_string = False
    string: str = None
    is_source = False
    source: ParsedSource = None
    is_item = False
    item: ParsedItem = None

    def __init__(self, pieces: list[str | ParsedSource | ParsedItem], start_index: int=0):
        self.pieces = pieces
        self.pre_errors = ErrorLog()
        
        item_index = start_index; explicit_item = False; implicit_item = False
        # TODO: this currently does not work as intended due to nesting:
        # "{} {roll max={}} {}" == "{0} {roll max={0}} {1}"
        for piece in pieces:
            if isinstance(piece, ParsedSource):
                # TODO
                pass
            elif isinstance(piece, ParsedItem):
                if piece.explicitlyIndexed:
                    explicit_item = True
                else:
                    implicit_item = True
                    piece.index = item_index
                    item_index += 1

        self.end_index = item_index

        # TODO: only make this show up if Items are actually intended to be added at some point(?)
        if explicit_item and implicit_item:
            self.pre_errors.log('Do not mix empty {}\'s with numbered {}\'s"!', True)

        # For simplicity, an empty list is normalised to an empty string
        self.pieces = self.pieces or ['']
        
        ## Determine if we're a very simple kind of TemplatedString
        if len(self.pieces) == 1:
            self.is_string = isinstance(self.pieces[0], str)
            if self.is_string: self.string = self.pieces[0]

            self.is_source = isinstance(self.pieces[0], ParsedSource)
            if self.is_source: self.source = self.pieces[0]
            
            self.is_item = isinstance(self.pieces[0], ParsedItem)
            if self.is_item: self.item = self.pieces[0]

    @staticmethod
    def from_parsed(parsed: ParseResults=[], start_index=0):
        pre_errors = ErrorLog()
        pieces = []

        for piece in parsed:
            if 'string_bit' in piece:
                if not pieces or not isinstance(pieces[-1], str):
                    pieces.append(piece['string_bit'])
                else:
                    pieces[-1] += piece['string_bit']

            elif 'source' in piece:
                source = ParsedSource.from_parsed(piece['source'])
                pieces.append(source)
                pre_errors.extend(source.pre_errors, source.name)

            elif 'item' in piece:
                item = ParsedItem(piece['item'])
                pieces.append(item)

        string = TemplatedString(pieces, start_index)
        string.pre_errors.extend(pre_errors)
        return string
    
    @staticmethod
    def from_string(string: str):
        parsed = grammar.templated_string.parse_string(string, parseAll=True)
        return TemplatedString.from_parsed(parsed)

    def __str__(self):
        return ''.join(str(x) for x in self.pieces)
    def __repr__(self):
        return 'TString"' + ''.join(x if isinstance(x, str) else repr(x) for x in self.pieces) + '"'
    def __bool__(self):
        return not (self.is_string and not self.pieces[0])

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
            if self.is_string: self.string: str = self.pieces[0]

        return self

    def split_implicit_arg(self, greedy: bool) -> tuple['TemplatedString', 'TemplatedString | None']:
        ''' Splits the TemplatedString into an implicit arg and a "remainder" TemplatedString. '''
        if greedy:
            return self.unquote(), None
        else:
            # This is stupid since it just applies the TemplatedString version of .split(' ', 1)
            # But we probably don't need more than this...
            implicit = []
            remainder = []
            for i in range(len(self.pieces)):
                piece = self.pieces[i]
                if isinstance(piece, str):
                    if ' ' in piece:
                        piece1, piece2 = piece.split(' ', 1)
                        implicit.append(piece1)
                        remainder = [piece2, self.pieces[i+1:]]
                        break
                    else:
                        implicit.append(piece)
                else:
                    implicit.append(piece)

            return TemplatedString(implicit).unquote(), TemplatedString(remainder)

    async def evaluate(self, message, context: Context=None) -> tuple[str, ErrorLog]:
        ''' Evaluate the TemplatedString into a string '''
        errors = ErrorLog()
        errors.extend(self.pre_errors)

        if self.is_string:
            return self.string, errors

        FUTURE = object()
        results = []
        futures = []

        for piece in self.pieces:
            if isinstance(piece, str):
                results.append(piece)

            elif isinstance(piece, ParsedItem):
                try:
                    results.append(piece.evaluate(context))
                except ContextError as e:
                    errors.log(str(e), True)

            elif isinstance(piece, ParsedSource) and not errors.terminal:
                results.append(FUTURE)
                futures.append(piece.evaluate(message, context))

        source_results = await asyncio.gather(*futures)

        out = None
        if not errors.terminal:
            strings = []
            source_index = 0
            for result in results:
                if result is FUTURE:
                    items, src_errors = source_results[source_index]
                    errors.extend(src_errors)
                    if not errors.terminal:
                        strings.append(items[0])
                    source_index += 1
                else:
                    strings.append(result)            
            out = ''.join(strings)

        return out, errors

    # ================ Specific use cases, wrapped into a single method

    @staticmethod
    async def evaluate_string(string: str, message: discord.Message=None, context: Context=None, force_single=False) -> tuple[list[str] | None, ErrorLog]:
        '''
        Takes a raw source string, evaluates {sources} and returns the list of values.
        
        If forceSingle=False, a pure "{source}" string may generate more (or less!) than 1 value.
        '''
        try:
            template = TemplatedString.from_string(string)
        except ParseException as e:
            return None, ErrorLog().log_parse_exception(e)

        if not force_single and template.is_source:
            vals, errs = await template.source.evaluate(message, context)
            return vals, errs
        else:
            val, errs = await template.evaluate(message, context)
            return [val], errs

    @staticmethod
    async def evaluate_origin(origin_str: str, message: discord.Message=None, context: Context=None) -> tuple[list[str] | None, ErrorLog]:
        '''Takes a raw source string, expands it if necessary, evaluates {sources} in each one and returns the list of values.'''
        values = []
        expand = True
        errors = ErrorLog()
    
        ## Get rid of wrapping quotes or triple quotes
        if len(origin_str) >= 6 and origin_str[:3] == origin_str[-3:] == '"""':
            origin_str = origin_str[3:-3]
            expand = False
        elif len(origin_str) >= 2 and origin_str[0] == origin_str[-1] in ('"', "'", '/'):
            origin_str = origin_str[1:-1]
    
        expanded = ChoiceTree(origin_str, parse_flags=True, add_brackets=True) if expand else [origin_str]

        ## Evaluate each string as a TemplatedString, collecting errors along the way
        ## This part is basically TemplatedString.evaluate_string inlined
        for origin_str in expanded:
            try:
                origin = TemplatedString.from_string(origin_str)
            except ParseException as e:
                errors.log_parse_exception(e)

            else:
                if origin.is_source:
                    vals, errs = await origin.source.evaluate(message, context)
                    errors.extend(errs)
                    if not errors.terminal: values.extend(vals)
                else:
                    val, errs = await origin.evaluate(message, context)
                    errors.extend(errs)
                    if not errors.terminal: values.append(val)

        return values, errors
