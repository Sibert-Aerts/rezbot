from typing import Optional, TypeVar, Callable
from pyparsing import ParseException, ParseResults

from .grammar import argumentList
from .logger import ErrorLog

from utils import util


class ArgumentError(ValueError):
    '''Special error in case a bad argument is passed.'''

# In this file, a "type" is an object which has a __name__ field
#   and a __call__ method of type (str -> T), which may also raise errors for poorly formed input strings.
# e.g. `str`, `int` and `float` are "types", but also any function (str -> T) is a "type".
# The two classes below can be used to instantiate simple new "types" as well.

class Option:
    '''
    An Option object behaves like a "type" for parsing enums from strings, returning enum-like objects.
    By default it is case insensitive, and will normalise all names to lowercase.
    Set prefer_upper=True to instead normalise all names to uppercase.
    Set case_sensitive=True to instead be case sensitive.
    Set stringy=True it will return regular strings instead of enum-like objects. True

    Examples:
        >>> Color = Option('red', 'green', 'blue', name='color')
        >>> Color.red
        red
        >>> Color('red') is Color.red
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
        

    With `stringy=True`, it essentially acts as a filter/normaliser for a set of strings.
        >>> Color = Option('red', 'green', 'blue', stringy=True)
        >>> Color('red') == Color.red == 'red'
        True
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
    ''' Represents a single declared parameter in a signature. '''
    name: str
    default: T

    def __init__(self, type: Callable[[str], T], default: str | T=None, desc: str=None, check: Callable[[T], bool]=None, required: bool=None):
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
        
    def __str__(self):
        out = []
        if self.desc:
            out.append(' ' + self.desc)
        out.append(' (' + self.type.__name__)
        if self.required:
            out.append(', REQUIRED')
        elif self.default is not None:
            out.append(f', default: `{repr(self.default)}`')
        out.append(')')
        return ''.join(out)

    def parse(self, raw: str):
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
    ''' Object representing a TemplatedString assigned to a specific parameter. '''
    param: Par | None
    name: str
    string: 'TemplatedString'
    value: T = None
    predetermined: bool = False

    def __init__(self, string: 'TemplatedString', param: Par | str):
        self.param = param if isinstance(param, Par) else None
        self.name = param.name if isinstance(param, Par) else param
        self.string = string

    def predetermine(self, errors):
        if self.string.is_string:
            try:
                self.value = self.param.parse(self.string.string) if self.param else self.string.string
                self.predetermined = True
            except ArgumentError as e:
                errors.log(e, True)

    async def determine(self, message, context, errors: ErrorLog) -> T | None:
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
    def __init__(self, args: dict[str, Arg]):
        self.args = args
        self.predetermined = all(args[p].predetermined for p in args)
        if self.predetermined:
            self.args = { param: args[param].value for param in args }

    @staticmethod
    def from_string(string: str, sig: Signature=None, greedy=True) -> tuple['Arguments', Optional['TemplatedString'], ErrorLog]:
        try:
            parsed = argumentList.parseString(string, parseAll=True)
        except ParseException as e:
            return None, None, ErrorLog().log_parse_exception(e)
        else:
            return Arguments.from_parsed(parsed, sig, greedy=greedy)

    @staticmethod
    def from_parsed(argList: ParseResults, signature: Signature=None, greedy: bool=True) -> tuple['Arguments', Optional['TemplatedString'], ErrorLog]:
        '''
            Compiles an argList ParseResult into a ParsedArguments object.
            If Signature is not given, will create a "naive" ParsedArguments object that Macros use.
        '''
        errors = ErrorLog()

        ## Step 1: Collect explicitly and implicitly assigned parameters
        remainder = []
        args = {}
        start_index = 0

        ## TODO: the running startIndex doesn't track the remainder/implicit string! yikes!!
        for arg in argList or []:
            if 'paramName' in arg:
                param = arg['paramName'].lower()
                if param in args:
                    errors.warn(f'Repeated assignment of parameter `{param}`')
                else:
                    value = TemplatedString.from_parsed(arg['value'], start_index)
                    start_index = value.end_index
                    args[param] = value
            else:
                remainder += list(arg['implicitArg'])

        remainder = TemplatedString.from_parsed(remainder)
        
        ## Step 2: Turn into Arg objects
        for param in list(args):
            if signature is None:
                # TODO: I switched this from "if not signature" (i.e. signature is empty OR None)
                # ...but what use case is "signature is None" anyway?
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
                errors.log(f'Missing required parameter{"s" if len(missing)>1 else ""} {" ".join("`%s`"%p for p in missing)}', True)

            elif len(missing) == 1:
                ## Only one required parameter is missing; use the implicit parameter
                [param] = missing
                implicit, remainder = remainder.split_implicit_arg(greedy)
                args[param] = Arg(implicit, signature[param])


        ## Step 4: Check if the Signature simply has one parameter, and it hasn't been assigned yet (⇒ it's non-required)
        elif len(signature) == 1 and remainder and greedy:
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

    async def determine(self, message, context=None) -> tuple[dict[str], ErrorLog]:
        ''' Returns a parsed {parameter: argument} dict ready for use. '''
        errors = ErrorLog()
        if self.predetermined: return self.args, errors
        
        futures = {param: self.args[param].determine(message, context, errors) for param in self.args}
        values = await util.gather_dict(futures)
        return values, errors



# This lyne ys down here dve to dependencyes cyrcvlaire
from .templatedstring import TemplatedString