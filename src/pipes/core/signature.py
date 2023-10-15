import asyncio
from typing import Awaitable, Iterable, Optional, TypeVar, Callable
from pyparsing import ParseException, ParseResults

from . import grammar
from .logger import ErrorLog
from .context import Context, ItemScope

# Make all the signature_types types available through this import
from .signature_types import *


class ArgumentError(ValueError):
    '''Special error in case a bad argument is passed.'''


#####################################################
#                     Signature                     #
#####################################################

T = TypeVar('T')

class Par:
    ''' Represents a single declared parameter in a signature. '''
    name: str
    default: T
    desc: str | None
    checkfun: Callable[[T], bool] | None
    required: bool

    def __init__(self, type: Callable[[str], T], default: str | T=None, desc: str=None, check: Callable[[T], bool]=None, required: bool=True):
        '''
        Arguments:
            type: A "type" as described in signature_types.py; a callable (str -> T) with a __name__.
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
        self.required = required and (default is None)
        
    def __str__(self):
        ''' Make the representation string. '''
        out = [f'* **{self.name}:**']
        if self.desc:
            out.append(' ' + self.desc)
        out.append(' (*' + self.type.__name__ + '*')
        if self.required:
            out.append(', REQUIRED')
        else:
            if self.type == url:
                out.append(f', default: "<{self.default}>"')
            elif isinstance(self.default, str):
                out.append(f', default: "{self.default}"')
            else:
                out.append(f', default: `{self.default}`')
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


class Signature(dict[str, Par]):
    ''' dict-derived class representing a set of parameters for a single function. '''
    def __init__(self, params):
        # Force all keys lowercase
        params  = {k.lower(): v for (k, v) in params.items()}
        super().__init__(params)
        # Tell each Parameter its name
        for param in params:
            params[param].name = param


def with_signature(arg=None, **kwargs: dict[str, Par]):
    ''' Creates a Signature from the given dict or kwargs and stores it on the given function. '''
    if arg and kwargs:
        raise ValueError("with_signature should either specify one arg, or a set of kwargs, not both.")
    def _with_signature(f: Callable):
        signature = Signature(arg or kwargs)
        if hasattr(f, '__func__'):
            f.__func__.pipe_signature = signature
        else:
            f.pipe_signature = signature 
        return f
    return _with_signature


def get_signature(f: Callable, default=None):
    ''' Retrieves a Signature stored by `@with_signature`, or a default value if given, or an empty Signature. '''
    sig = getattr(f, 'pipe_signature', None)
    if sig is not None:
        return sig
    elif default is not None:
        return default
    else:
        return Signature({})


#####################################################
#                     Arguments                     #
#####################################################

class Arg:
    ''' Object representing a parsed TemplatedString assigned to a specific parameter. '''
    param: Par | None
    'The Par that this is argument is assigned to. If None, this Arg is a "naive" stringy argument.'
    name: str
    string: 'TemplatedString'
    value: T = None
    predetermined: bool = False

    def __init__(self, string: 'TemplatedString', param: Par | str):
        self.param = param if isinstance(param, Par) else None
        self.name = param.name if isinstance(param, Par) else param
        self.string = string

    def __repr__(self):
        return repr(self.value) if self.predetermined else repr(self.string)
    def __str__(self):
        return str(self.value) if self.predetermined else str(self.string)

    def predetermine(self, errors: ErrorLog):
        if self.string.is_string:
            try:
                self.value = self.param.parse(self.string.string) if self.param else self.string.string
                self.predetermined = True
            except ArgumentError as e:
                errors.log(e, True)

    async def determine(self, context: Context, scope: ItemScope, errors: ErrorLog) -> T | None:
        if self.predetermined: return self.value

        value, arg_errs = await self.string.evaluate(context, scope)
        errors.extend(arg_errs, context='parameter `{}`'.format(self.name))
        if errors.terminal: return

        try:
            return self.param.parse(value) if self.param else value
        except ArgumentError as e:
            errors.log(e, True)
            return


class DefaultArg(Arg):
    ''' Special-case Arg representing a default argument. '''
    def __init__(self, value):
        self.predetermined = True
        self.value = value


class Arguments:
    ''' A set of parsed Args, meta-information, and the utility to determine them all into a single dict. '''
    args: dict[str, Arg]
    defaults: list[str]
    predetermined: bool
    predetermined_args: dict[str] = None

    def __init__(self, args: dict[str, Arg]):
        self.args = args
        self.defaults = [p for p in args if isinstance(args[p], DefaultArg)]
        self.predetermined = all(args[p].predetermined for p in args)
        if self.predetermined:
            # Special case: Every single arg is already predetermined; we can build the value dict now already.
            self.predetermined_args = EvaluatedArguments((p, args[p].value) for p in args)
            self.predetermined_args.defaults = self.defaults

    @staticmethod
    def from_string(string: str, signature: Signature=None, greedy=True) -> tuple['Arguments', Optional['TemplatedString'], ErrorLog]:
        try:
            parsed = grammar.argument_list.parse_string(string, parseAll=True)
        except ParseException as e:
            return None, None, ErrorLog().log_parse_exception(e)
        return Arguments.from_parsed(parsed, signature, greedy=greedy)

    @staticmethod
    def from_parsed(argList: ParseResults, signature: Signature=None, greedy: bool=True) -> tuple['Arguments', Optional['TemplatedString'], ErrorLog]:
        '''
        Compiles an argList ParseResult into a ParsedArguments object.
        If Signature is not given, will create a "naive" ParsedArguments object that Macros use.
        '''
        errors = ErrorLog()

        ## Step 1: Collect explicitly and implicitly assigned parameters
        remainder_pieces = []
        args: dict[str, Arg] = {}
        start_index = 0

        for arg in argList or []:
            if 'param_name' in arg:
                param = arg['param_name'].lower()
                if param in args:
                    errors.warn(f'Repeated assignment of parameter `{param}`.')
                    continue
                remainder_piece = TemplatedString.from_parsed(arg['value'], start_index)
                errors.extend(remainder_piece.pre_errors, param)
                start_index = remainder_piece.end_index
                args[param] = remainder_piece
            else:
                remainder_piece = TemplatedString.from_parsed(arg['implicit_arg'], start_index)
                errors.extend(remainder_piece.pre_errors, 'implicit arg')
                start_index = remainder_piece.end_index
                remainder_pieces.append(remainder_piece)

        remainder = TemplatedString.join(remainder_pieces)
        
        ## Step 2: Turn into Arg objects
        for param in list(args):
            if signature is None:
                # Special case: Naive Arg
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
                args[param].predetermine(errors)


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

    def adjust_implicit_item_indices(self, new_start_index: int):
        '''
        Upon creation of an Arguments object we assign indices to implicitly indexed items,
        but if it turns out the object is nested inside a TemplatedString, the indices need to be adjusted,
        and the resulting max. index needs to be conveyed to the containing TemplatedString.
        '''
        end_index = new_start_index
        for arg in self.args.values():
            if arg.predetermined: continue
            index = arg.string.adjust_implicit_item_indices(new_start_index)
            end_index = max(index, end_index)
        return end_index

    def __repr__(self):
        return 'Args(%s)' % ', '.join(f'{p}={repr(a)}' for p, a in self.args.items() if p not in self.defaults)
    def __str__(self):
        return ' '.join(f'{p}={a}' for p, a in self.args.items() if p not in self.defaults)

    async def determine(self, context: Context, scope: ItemScope=None) -> tuple[dict[str], ErrorLog]:
        ''' Returns a parsed {parameter: argument} dict ready for use. '''
        errors = ErrorLog()
        if self.predetermined: return self.predetermined_args, errors

        futures = [self.args[p].determine(context, scope, errors) for p in self.args]
        values = await EvaluatedArguments.from_gather(self.args, futures)
        values.defaults = self.defaults
        return values, errors


class EvaluatedArguments(dict):
    '''dict-subclass representing {arg: value} pairs, but with useful meta-info and methods bolted on.'''
    defaults: list[str]

    @staticmethod
    async def from_gather(keys: Iterable[str], futures: Iterable[Awaitable]):
        values = await asyncio.gather(*futures)
        return EvaluatedArguments(zip(keys, values))

    def __str__(self):
        '''Shows only the non-default arguments.'''
        return ' '.join(f'`{p}`={self[p]}' for p in self if p not in self.defaults)


# This lyne ys down here dve to dependencyes cyrcvlaire
from .templated_string import TemplatedString