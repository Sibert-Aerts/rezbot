from pyparsing import ParseException, ParseResults, StringEnd
from typing import Any, List, Dict, Optional, Tuple, Union

# Here to make sure circular dependencies get loaded in the right order...
from pipes.processor import PipelineProcessor, Pipeline

from .grammar import templatedString, argumentList
from .sourceprocessor import Context, ContextError
from .signature import Arguments
from .sources import sources
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

    def evaluate(self, context: Context=None):
        if context:
            return context.get_parsed_item(self.carrots, self.index, self.bang)
        return str(self)


class ParsedSource:
    ''' Class representing a Source inside a TemplatedString. '''
    NATIVESOURCE = object()
    SOURCEMACRO  = object()
    UNKNOWN      = object()

    def __init__(self, name: str, args: Arguments, amount: Union[str, int, None]):
        self.name = name.lower()
        self.amount = amount
        self.args = args
        self.pre_errors = ErrorLog()
        
        if self.name in sources:
            self.type = ParsedSource.NATIVESOURCE
            self.source = sources[self.name]
        elif self.name in source_macros:
            self.type = ParsedSource.SOURCEMACRO
        else:
            self.type = ParsedSource.UNKNOWN            

    @staticmethod
    def from_parsed(parsed: ParseResults):
        name = parsed['sourceName'].lower()

        if 'amount' in parsed:
            amt = parsed['amount']
            if amt == 'ALL': amount = 'all'
            else: amount = int(amt)
        else: amount = None

        # TODO: this is maybe dumb. Simplify ParsedArguments.from_parsed to just the naive version, and ParsedArgs.adapt_to_signature(Signature), or something?
        if name in sources:
            args, _, pre_errors = Arguments.from_parsed(parsed.get('args'), sources[name].signature)
        else:
            args, _, pre_errors = Arguments.from_parsed(parsed.get('args'))

        parsedSource = ParsedSource(name, args, amount)
        parsedSource.pre_errors.extend(pre_errors)
        return parsedSource

    def __str__(self):
        return '{%s %s %s}' %( self.amount or '', self.name, self.args.__repr__() if self.args else '' )
    def __repr__(self):
        return 'Source' + str(self)


    async def evaluate(self, message=None, context=None, args=None) -> Tuple[ List[str], ErrorLog ]:
        ''' Find some values for the damn Source that we are. '''
        errors = ErrorLog()
        if self.pre_errors: errors.extend(self.pre_errors)
        NOTHING_BUT_ERRORS = (None, errors)
        if errors.terminal: return NOTHING_BUT_ERRORS

        if not (self.name in sources or self.name in source_macros):
            errors(f'Unknown source `{self.name}`.')
            return NOTHING_BUT_ERRORS

        if args is None:
            ## Determine the arguments
            args, argErrors = await self.args.determine(message, context)
            errors.extend(argErrors, self.name)
            if errors.terminal: return NOTHING_BUT_ERRORS

        ### CASE: Native Source
        if self.type == ParsedSource.NATIVESOURCE:
            try:
                return await self.source(message, args, n=self.amount), errors

            except Exception as e:
                argfmt = ' '.join( f'`{p}`={args[p]}' for p in args )
                errors(f'Failed to evaluate source `{self.name}` with args {argfmt}:\n\t{e.__class__.__name__}: {e}', True)
                return NOTHING_BUT_ERRORS

        ### CASE: Macro Source
        elif self.name in source_macros:
            code = source_macros[self.name].apply_args(args)

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
            # TODO: Actually use the "amount"
            values, _, pl_errors, _ = await pipeline.apply(values, message)
            errors.extend(pl_errors, self.name)
            return values, errors


class TemplatedString:
    ''' Class representing a string that may contain Sources or Items. '''
    def __init__(self, pieces: List[Union[str, ParsedSource, ParsedItem]], startIndex: int=0):
        self.pieces = pieces
        self.pre_errors = ErrorLog()
        
        itemIndex = startIndex; explicitItem = False; implicitItem = False
        # TODO: this currently does not work as intended due to nesting:
        # "{} {roll max={}} {}" == "{0} {roll max={0}} {1}"
        for piece in pieces:
            if isinstance(piece, ParsedSource):
                pass
            elif isinstance(piece, ParsedItem):
                if piece.explicitlyIndexed:
                    explicitItem = True
                else:
                    implicitItem = True
                    piece.index = itemIndex
                    itemIndex += 1

        self.endIndex = itemIndex

        # TODO: only make this show up if Items are actually intended to be added at some point(?)
        if explicitItem and implicitItem:
            self.pre_errors('Do not mix empty {}\'s with numbered {}\'s"!', True)

        # For simplicity, an empty List is normalised to an empty string
        self.pieces = self.pieces or ['']
        
        ## Determine if we're a very simple kind of TemplatedString
        self.isString = len(self.pieces)==1 and isinstance(self.pieces[0], str)
        if self.isString: self.string: str = self.pieces[0]

        self.isSource = len(self.pieces)==1 and isinstance(self.pieces[0], ParsedSource)
        if self.isSource: self.source: ParsedSource = self.pieces[0]
        
        self.isItem = len(self.pieces)==1 and isinstance(self.pieces[0], ParsedItem)
        if self.isItem: self.item: ParsedItem = self.pieces[0]

    @staticmethod
    def from_parsed(parsed: ParseResults=[], minIndex=0):
        pre_errors = ErrorLog()
        pieces = []

        for piece in parsed:
            if 'stringBit' in piece:
                if not pieces or not isinstance(pieces[-1], str):
                    pieces.append(piece['stringBit'])
                else:
                    pieces[-1] += piece['stringBit']

            elif 'source' in piece:
                source = ParsedSource.from_parsed(piece['source'])
                pieces.append(source)
                pre_errors.extend(source.pre_errors, source.name)

            elif 'item' in piece:
                item = ParsedItem(piece['item'])
                pieces.append(item)

        string = TemplatedString(pieces, minIndex)
        string.pre_errors.extend(pre_errors)
        return string
    
    @staticmethod
    def from_string(string: str):
        return TemplatedString.from_parsed( templatedString.parseString(string, parseAll=True) )

    def __str__(self):
        return ''.join(str(x) for x in self.pieces)
    def __repr__(self):
        return 'Template"' + ''.join(x if isinstance(x, str) else x.__repr__() for x in self.pieces) + '"'
    def __bool__(self):
        return not (self.isString and not self.pieces[0])

    def unquote(self) -> 'TemplatedString':
        ''' Modifies the TemplatedString to remove wrapping string delimiters, if present. '''
        pieces = self.pieces

        if isinstance(pieces[0], str) and isinstance(pieces[-1], str):
            if pieces[0][:3] == pieces[-1][-3:] == '"""' and not (self.isString and len(pieces[0]) < 6):
                pieces[0] = pieces[0][3:]
                pieces[-1] = pieces[-1][:-3]
            elif pieces[0][:1] == pieces[-1][-1:] in ('"', "'", '/') and not (self.isString and len(pieces[0]) < 2):
                pieces[0] = pieces[0][1:]
                pieces[-1] = pieces[-1][:-1]
            if self.isString: self.string: str = self.pieces[0]

        return self

    def split_implicit_arg(self, greedy: bool) -> Tuple['TemplatedString', 'TemplatedString']:
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


    async def evaluate(self, message, context: Context=None) -> Tuple[str, ErrorLog]:
        ''' Evaluate the TemplatedString into a string '''
        errors = ErrorLog()
        errors.extend(self.pre_errors)

        if self.isString:
            return self.string, errors

        # TODO: pull that `await` outside the loop!!!!!!!!!
        evaluated = []

        for piece in self.pieces:
            if isinstance(piece, str):
                evaluated.append(piece)

            elif isinstance(piece, ParsedItem):
                try: evaluated.append(piece.evaluate(context))
                except ContextError as e:
                    errors(str(e), True)

            elif isinstance(piece, ParsedSource) and not errors.terminal:
                items, src_errors = await piece.evaluate(message, context)
                errors.extend(src_errors)
                evaluated.append(items[0] if items else '')

        return ''.join(evaluated) if not errors.terminal else None, errors

    @staticmethod
    async def evaluate_origin(originStr: str, message, context=None) -> Tuple[List[str], ErrorLog]:
        '''Takes a raw source string, expands it if necessary, applies {sources} in each one and returns the list of values.'''
        values = []
        expand = True
        errors = ErrorLog()
    
        ## Get rid of wrapping quotes or triple quotes
        if len(originStr) >= 6 and originStr[:3] == originStr[-3:] == '"""':
            originStr = originStr[3:-3]
            expand = False
        elif len(originStr) >= 2 and originStr[0] == originStr[-1] in ('"', "'", '/'):
            originStr = originStr[1:-1]
    
        sources = ChoiceTree(originStr, parse_flags=True, add_brackets=True) if expand else [originStr]

        ## Evaluate each string as a TemplatedString, collecting errors along the way
        for originStr in sources:
            try:
                origin = TemplatedString.from_string(originStr)

            except ParseException as e:
                # Identical to the except clause in ParsedArguments.from_string
                if isinstance(e.parserElement, StringEnd):
                    error = f'ParseException: Likely unclosed brace at position {e.loc}:\n­\t'
                    error += e.line[:e.col-1] + '**[' + e.line[e.col-1] + '](http://0)**' + e.line[e.col:]
                    errors(error, True)
                else:
                    errors('An unexpected ParseException occurred!')
                    errors(e, True)

            ## If the origin parsed properly:
            else:
                if origin.isSource:
                    vals, errs = await origin.source.evaluate(message, context)
                    errors.extend(errs)
                    if not errors.terminal: values.extend(vals)
                else:
                    val, errs = await origin.evaluate(message, context)
                    errors.extend(errs)
                    if not errors.terminal: values.append(val)

        return values, errors

