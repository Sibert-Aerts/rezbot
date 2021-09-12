from typing import List, Tuple, Dict, Any, Optional, TypeVar, Union, Callable
from pyparsing import ParseException, ParseResults, StringEnd
import re

from .grammar import argumentList
from .logger import ErrorLog



class ArgumentError(ValueError):
    '''Special error in case a bad argument is passed.'''

# In this file, a "type" is an object which has a __name__ field
#   and a __call__ method of type (str -> T), which may also raise errors for poorly formed input strings.
# e.g. `str`, `int` and `float` are "types", but also any function (str -> T) is a "type"
# The two classes below are used to create simple new "types" as well

class Option:
    '''
        An Option object behaves like a "type" for parsing enums from strings, returning str-like objects.
        By default it is case insensitive, and will normalise all names to lowercase.
        Set prefer_upper=True to instead normalise all names to uppercase.
        If stringy=True it will return regular strings instead of str-like objects.

        >>> Color = Option('red', 'green', 'blue', name='color')
        >>> Color.red
        red
        >>> Color('red') == Color.red
        True
        >>> 'red' == Color.red
        False
        >>> Color('magenta')
        ArgumentError: Unknown color: "magenta"

        >>> Color2 = Color + ['cyan', 'magenta', 'yellow']
        >>> Color2('magenta') == Color2.magenta
        True
        >>> Color2.red == Color.red
        False
    '''

    class Str:
        ''' The str-like class representing a specific possible option. '''
        def __init__(self, str): self.str = str
        def __repr__(self): return self.str
        def __str__(self): return self.str

    def __init__(self, *options, name='option', case_sensitive=False, prefer_upper=False, stringy=False):
        self.__name__ = name
        self._case_sens = case_sensitive
        self._stringy = stringy
        self._pref_upp = prefer_upper

        if not case_sensitive:
            options = [opt.upper() if prefer_upper else opt.lower() for opt in options]
        self._options = options
        for option in self._options:
            setattr(self, option, option if stringy else Option.Str(option))
        
    def __call__(self, text):
        if not self._case_sens: text = text.upper() if self._pref_upp else text.lower()
        if hasattr(self, text):
            return getattr(self, text)
        if len(self._options) <= 8:
            raise ArgumentError(f'Must be one of {"/".join(self._options)}')
        raise ArgumentError(f'Unknown {self.__name__} "{text}"')

    def __add__(self, other):
        if isinstance(other, list):
            return Option(*self._options, *other, name=self.__name__, case_sensitive=self._case_sens, stringy=self._stringy)
        raise Exception('Option can only be added to list')

    def __iter__(self):
        return self._options.__iter__()

class Multi:
    '''
        A Multi object wraps a "type" to be a comma (or otherwise) separated list of said type.
        The output type is a list but with __repr__ changed to resemble the original input.

        >>> intList = Multi(int)
        >>> intList('10,20,30') == [10, 20, 30]
        True
        >>> intList('10,20,30')
        10,20,30
    '''
    
    class List(list):
        def __init__(self, sep, *a, **kw):
            super().__init__(self, *a, **kw)
            self.sep = sep
        def __repr__(self): return self.sep.join(str(s) for s in self)

    def __init__(self, type, sep=','):
        self.__name__ = type.__name__ + ' list'
        self.type = type
        self.sep = sep

    def __call__(self, text: str):
        out = Multi.List(self.sep)
        for item in text.split(self.sep):
            try:
                out.append(self.type(item))
            except Exception as e:
                if isinstance(self.type, Option) and len(self.type._options) <= 8:
                    raise ArgumentError(f'Must be a sequence of items from {"/".join(self.type._options)} separated by "{self.sep}"s.')
                raise ArgumentError(f'"{item}" must be of type {self.type.__name__} ({e})')
        return out


#####################################################
#                     Signature                     #
#####################################################

T = TypeVar('T')

class Par:
    ''' Represents a single parameter in a signature. '''
    def __init__(self, type: Callable[[str], T], default: Union[str, T]=None, desc: str=None, check: Callable[[T], bool]=None, required: bool=None):
        '''
        Arguments:
            type: A "type" as described above; a callable (str -> T) with a __name__.
            default: The default value of type str or T to be used in case the parameter is not assigned, if `None` the parameter is assumed required.
            desc: The signature's description string.
            check: A function (T -> bool) that verifies if the output of `type` meets some arbitrary requirement.
            required: Set to False if default=None should be interpreted literally; using None is the default value.
        '''
        self.type = type
        self.name = None # Set by Signature
        self.default = default if not isinstance(default, str) else type(default)
        self.desc = desc
        self.checkfun = check
        self.required = required if required is not None else (default is None)
        self._re = None
        self._str = None
        
    def __str__(self):
        if not self._str:
            s = ''
            if self.desc:
                s += ' ' + self.desc
            s += ' (' + self.type.__name__
            if self.required:
                s += ', REQUIRED'
            elif self.default is not None:
                s +=', default: ' + repr(self.default)
            s += ')'
            self._str = s
        return self._str

    def re(self):
        # This regex matches the following formats:
        #   name=valueWithoutSpaces
        #   name="value with spaces"            name='likewise'
        #   name="""just "about" anything"""    name='''likewise'''
        #   name=/use this one for regexes/     (functionally identical to " or ')
        if self._re is None:
            self._re = re.compile(r'\b' + self.name + r'=(?:"""(.*?)"""|\'\'\'(.*?)\'\'\'|"(.*?)"|\'(.*?)\'|/(.*?)/|(\S+))\s*', re.S)
            #                                                   [1]            [2]          [3]      [4]      [5]    [6]        
        return self._re

    def parse(self, raw):
        ''' Attempt to parse and check the given string as an argument for this parameter, raises ArgumentError if it fails. '''
        try:
            val = self.type(raw)
        except ArgumentError as e:
            ## ArgumentError means it's a nicely formatted error that we made ourselves
            raise ArgumentError(f'Invalid value "{raw}" for parameter `{self.name}`: {e}')
        except Exception as e:
            ## Exceptions may be less clear so we need to be more verbose
            raise ArgumentError(f'Invalid value "{raw}" for parameter `{self.name}`: Must be of type `{self.type.__name__}` ({e})')

        if self.checkfun and not self.checkfun(val):
            raise ArgumentError(f'Parameter `{self.name}` is not allowed to be "{raw}".')
        return val

class Signature(dict):
    ''' dict-like class representing a set of parameters for a single function. '''
    def __init__(self, params):
        super().__init__(params)
        for param in params:
            params[param].name = param

#####################################################
#                     Arguments                     #
#####################################################

class Arg:
    def __init__(self, string: 'TemplatedString', param: Union[Par, str]):
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

class DefaultArg(Arg):
    ''' Special-case Arg representing a default argument. '''
    def __init__(self, value):
        self.predetermined = True
        self.value = value

class Arguments:
    def __init__(self, args: Dict[str, Arg]):
        self.args = args
        self.predetermined = all(args[p].predetermined for p in args)
        if self.predetermined:
            self.args = { param: args[param].value for param in args }

    @staticmethod
    def from_string(string: str, sig: Signature=None, greedy=True) -> Tuple['Arguments', 'TemplatedString', ErrorLog]:
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
            return None, None, errors
        else:
            return Arguments.from_parsed(parsed, sig, greedy=greedy)

    @staticmethod
    def from_parsed(argList: ParseResults, signature: Signature=None, greedy: bool=True) -> Tuple['Arguments', 'TemplatedString', ErrorLog]:
        '''
            Compiles an argList ParseResult into a ParsedArguments object.
            If Signature is not given, will create a "naive" ParsedArguments object that Macros use.
        '''
        errors = ErrorLog()

        ## Step 1: Collect explicitly and implicitly assigned parameters
        remainder = []
        args = {}
        for arg in argList or []:
            if 'paramName' in arg:
                param = arg['paramName'].lower()
                if param in args:
                    errors.warn(f'Repeated assignment of parameter `{param}`')
                else:
                    value = TemplatedString.from_parsed(arg['value'])
                    args[param] = value
            else:
                remainder += list(arg['implicitArg'])

        remainder = TemplatedString.from_parsed(remainder)
        
        ## Step 2: Turn into Arg objects
        for param in list(args):
            if not signature:
                args[param] = Arg(args[param], param)
                args[param].predetermine(errors)
            elif param in signature:
                args[param] = Arg(args[param], signature[param])
                args[param].predetermine(errors)
            else:
                errors.warn(f'Unknown parameter `{param}`')
                del args[param]

        ## If there's no signature to check against: we're done already.
        if not signature:
            return Arguments(args), remainder, errors

        ## Step 3: Check if required arguments are missing
        missing = [param for param in signature if param not in args and signature[param].required]
        if missing:
            if not remainder or len(missing) > 1:
                # There's no implicit argument left to use for a missing argument
                # OR: There's more than 1 missing argument, which we can't handle in any case
                errors('Missing required parameter{} {}'.format('s' if len(missing) > 1 else '', ' '.join('`%s`'%p for p in missing)), True)

            elif len(missing) == 1:
                ## Only one required parameter is missing; use the implicit parameter
                [param] = missing
                implicit, remainder = remainder.split_implicit_arg(greedy)
                args[param] = Arg(implicit, signature[param])


        ## Step 4: Check if the Signature simply has one parameter, and it hasn't been assigned yet (i.e. it's non-required)
        elif len(signature) == 1 and remainder:
            [param] = list(signature.keys())
            if param not in args:
                # Try using the implicit parameter, but if it causes errors, pretend we didn't see anything!
                maybe_errors = ErrorLog()
                implicit, remainder = remainder.split_implicit_arg(greedy)
                arg = Arg(implicit, signature[param])
                arg.predetermine(maybe_errors)

                # If it causes no trouble: use it!
                if not maybe_errors.terminal:
                    args[param] = arg
                    remainder = None


        ## Last step: Fill out default values of unassigned non-required parameters
        for param in signature:
            if param not in args and not signature[param].required:
                args[param] = DefaultArg(signature[param].default)

        return Arguments(args), remainder, errors

    def __repr__(self):
        return 'Args(' + ' '.join(self.args.keys()) + ')'

    async def determine(self, message, context=None) -> Tuple[Dict[str, Any], ErrorLog]:
        ''' Returns a parsed {parameter: argument} dict ready for use. '''
        errors = ErrorLog()
        if self.predetermined: return self.args, errors
        # TODO: async those awaits
        return { param: await self.args[param].determine(message, context, errors) for param in self.args }, errors



# This lyne ys down here dve to dependencyes cyrcvlaire
from .sourceparser import TemplatedString