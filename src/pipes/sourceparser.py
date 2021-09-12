from pyparsing import ParseException, ParseResults, StringEnd
from typing import Any, List, Dict, Optional, Tuple, Union

# Here to make sure circular dependencies get loaded in the right order...
from pipes.processor import PipelineProcessor, Pipeline

from .grammar import templatedString, argumentList
from .sourceprocessor import Context, ContextError
from .signature import ArgumentError, Signature, Par
from .sources import sources
from .macros import source_macros
from .logger import ErrorLog

from utils.choicetree import ChoiceTree



##### New concept, replaces the usage of SourceProcessor
class ParsedItem:
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



##### New concept, replaces the usage of SourceProcessor
class ParsedSource:
    ''' Class representing a Source parsed from an expression. '''
    NATIVESOURCE = object()
    SOURCEMACRO  = object()
    UNKNOWN      = object()

    def __init__(self, name: str, args: 'ParsedArguments', amount: Union[str, int, None]):
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
            source = sources[name]
            args, pre_errors = ParsedArguments.from_parsed(parsed.get('args'), source.signature)
        else:
            args, pre_errors = ParsedArguments.from_parsed(parsed.get('args'))

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
            values, _, pl_errors, _ = await pipeline.apply(values, None)
            errors.extend(pl_errors, self.name)
            return values, errors




##### Replaces previous implicit usages of str
class TemplatedString:
    ''' Class representing a string that may contain Sources or Items. '''
    def __init__(self, parsed: ParseResults=[]):
        self.pieces: List[Union[str, ParsedSource, ParsedItem]] = []
        self.pre_errors = ErrorLog()

        itemIndex = 0; explicitItem = False; implicitItem = False

        for piece in parsed:
            # A string piece
            if 'stringBit' in piece:
                if not self.pieces or not isinstance(self.pieces[-1], str):
                    self.pieces.append(piece['stringBit'])
                else:
                    self.pieces[-1] += piece['stringBit']

            elif 'source' in piece:
                source = ParsedSource.from_parsed(piece['source'])
                self.pieces.append(source)
                self.pre_errors.extend(source.pre_errors, source.name)

            elif 'item' in piece:
                # TODO: this currently does not work as intuitive due to nesting:
                # "{} {roll max={}} {}" == "{0} {roll max={0}} {1}"
                item = ParsedItem(piece['item'])
                if item.explicitlyIndexed:
                    explicitItem = True
                else:
                    implicitItem = True
                    item.index = itemIndex
                    itemIndex += 1
                self.pieces.append(item)

        # TODO: only make this show up if Items are actually intended to be added at some point(?)
        if explicitItem and implicitItem:
            self.pre_errors('Do not mix empty {}\'s with numbered {}\'s"!', True)
        
        # For simplicity later, an empty List is replaced with an empty string
        self.pieces = self.pieces or ['']
        
        # Determine if we're a very simple kind of TemplatedString
        self.isString = len(self.pieces)==1 and isinstance(self.pieces[0], str)
        if self.isString: self.string: str = self.pieces[0]

        self.isSource = len(self.pieces)==1 and isinstance(self.pieces[0], ParsedSource)
        if self.isSource: self.source: ParsedSource = self.pieces[0]
        
        self.isItem = len(self.pieces)==1 and isinstance(self.pieces[0], ParsedItem)
        if self.isItem: self.item: ParsedItem = self.pieces[0]
    
    @staticmethod
    def from_string(string: str):
        return TemplatedString( templatedString.parseString(string, parseAll=True) )

    def __str__(self):
        return ''.join(str(x) for x in self.pieces)
    def __repr__(self):
        return 'Template"' + ''.join(x if isinstance(x, str) else x.__repr__() for x in self.pieces) + '"'
    def __bool__(self):
        return not (self.isString and not self.pieces[0])

    async def evaluate(self, message, context=None) -> Tuple[str, ErrorLog]:
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

        return ''.join(evaluated), errors

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
        elif len(originStr) >= 2 and originStr[0] == originStr[-1] == '"':
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



##### Replaces Arg
class ParsedArg:
    def __init__(self, string: TemplatedString, param: Union[Par, str]):
        self.param = param if isinstance(param, Par) else None
        self.name = param.name if isinstance(param, Par) else param
        self.string = string
        self.value = None
        self.predetermined = False

    def predetermine(self, errors):
        if self.string.isString:
            try:
                self.value = self.param.parse(self.string.string) if self.param else self.string.string
                self.predetermined = True
            except ArgumentError as e:
                errors.log(e, True)

    async def determine(self, message, context, errors: ErrorLog) -> Any:
        if self.predetermined: return self.value

        value, arg_errs = await self.string.evaluate(message, context)
        errors.steal(arg_errs, context='parameter `{}`'.format(self.name))
        if errors.terminal: return
        
        try:
            return self.param.parse(value) if self.param else value
        except ArgumentError as e:
            errors.log(e, True)
            return None


##### Replaces DefaultArg
class ParsedDefaultArg(ParsedArg):
    ''' Special-case Arg representing a default argument. '''
    def __init__(self, value):
        self.predetermined = True
        self.value = value


##### Replaces Arguments
class ParsedArguments:
    def __init__(self, args: Dict[str, ParsedArg]):
        self.args = args
        self.predetermined = all(args[p].predetermined for p in args)
        if self.predetermined:
            self.args = { param: args[param].value for param in args }

    def __repr__(self):
        return 'Args(' + ' '.join(self.args.keys()) + ')'

    @staticmethod
    def from_string(string: str, sig: Signature=None) -> Tuple['ParsedArguments', ErrorLog]:
        try:
            parsed = argumentList.parseString(string, parseAll=True)
        except ParseException as e:
            errors = ErrorLog()
            if isinstance(e.parserElement, StringEnd):
                error = f'ParseException: Likely unclosed brace at position {e.loc}:\n­\t'
                error += e.line[:e.col-1] + '**[' + e.line[e.col-1] + '](http://0)**' + e.line[e.col:]
                errors(error, True)
            else:
                errors('An unexpected ParseException occurred!')
                errors(e, True)
            return None, errors
        else:
            return ParsedArguments.from_parsed(parsed, sig)


    ###### this will replace Signature.parse_args
    @staticmethod
    def from_parsed(argList: ParseResults, signature: Signature=None) -> Tuple['ParsedArguments', ErrorLog]:
        '''
            Compiles an argList ParseResult into a ParsedArguments object.
            If Signature is not given, will create a "naive" ParsedArguments object that Macros use.
        '''
        errors = ErrorLog()

        ## Step 1: Collect explicitly and implicitly assigned parameters
        implicit = []
        args = {}
        for arg in argList or []:
            if 'paramName' in arg:
                param = arg['paramName'].lower()
                if param in args:
                    errors.warn(f'Repeated assignment of parameter `{param}`')
                else:
                    value = TemplatedString(arg['value'])
                    args[param] = value
            else:
                implicit += list(arg['implicitArg'])

        implicit = TemplatedString(implicit)
        
        ## Step 2: Turn into Arg objects
        for param in list(args):
            if not signature:
                args[param] = ParsedArg(args[param], param)
                args[param].predetermine(errors)
            elif param in signature:
                args[param] = ParsedArg(args[param], signature[param])
                args[param].predetermine(errors)
            else:
                errors.warn(f'Unknown parameter `{param}`')
                del args[param]

        if not signature:
            return ParsedArguments(args), errors

        ## Step 3: Check if required arguments are missing
        missing = [param for param in signature if param not in args and signature[param].required]
        if missing:
            if not implicit or len(missing) > 1:
                # There's no implicit argument left to use for a missing argument
                # OR: There's more than 1 missing argument, which we can't handle in any case
                errors('Missing required parameter{} {}'.format('s' if len(missing) > 1 else '', ' '.join('`%s`'%p for p in missing)), True)

            elif len(missing) == 1:
                ## Only one required parameter is missing; use the implicit parameter
                [param] = missing
                args[param] = ParsedArg(implicit, signature[param])
                implicit = None


        ## Step 4: Check if the Signature simply has one parameter, and it hasn't been assigned yet (i.e. it's non-required)
        elif len(signature) == 1 and implicit:
            [param] = list(signature.keys())
            if param not in args:
                # Try using the implicit parameter, but if it causes errors, pretend we didn't see anything!
                maybe_errors = ErrorLog()
                arg = ParsedArg(implicit, signature[param])
                arg.predetermine(maybe_errors)

                # If it causes no trouble: use it!
                if not maybe_errors.terminal:
                    args[param] = arg
                    remainder = None


        ## Last step: Fill out default values of unassigned non-required parameters
        for param in signature:
            if param not in args and not signature[param].required:
                args[param] = ParsedDefaultArg(signature[param].default)

        return ParsedArguments(args), errors

    async def determine(self, message, context) -> Tuple[Dict[str, Any], ErrorLog]:
        ''' Returns a parsed {parameter: argument} dict ready for use. '''
        errors = ErrorLog()
        if self.predetermined: return self.args, errors
        # TODO: async those awaits
        return { param: await self.args[param].determine(message, context, errors) for param in self.args }, errors
