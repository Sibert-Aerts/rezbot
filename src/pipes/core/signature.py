import asyncio
from typing import Awaitable, Iterable, Optional, TypeVar, Callable
from pyparsing import ParseBaseException, ParseResults

from . import grammar
from .state import ErrorLog, Context, ItemScope
from .templated_string.templated_string import TemplatedString

# Make all the signature_types types available through this import
from .signature_types import *


#####################################################
#                     Signature                     #
#####################################################

T = TypeVar('T')

class Par:
    ''' Represents a single declared parameter in a signature. '''
    type: Callable[[str], T]
    name: str
    default: T
    desc: str | None
    checkfun: Callable[[T], bool] | None
    required: bool

    def __init__(self, type: Callable[[str], T], default: str | T=None, desc: str=None, check: Callable[[T], bool]=None, required: bool=True):
        '''
        Arguments:
            * type: A "type" as described in `signature_types.py`; a callable `(str -> T)` with a `__name__`.
            * default: The default value of type str or T to be used in case the parameter is not assigned, if `None` the parameter is assumed required.
            * desc: The signature's description string.
            * check: A function `(T -> bool)` that verifies if the output of `type` meets some arbitrary requirement.
            * required: Set to `False` if `default=None` should be interpreted literally; using `None` as the default value.
        '''
        self.type = type
        self.name = None # Set by Signature
        self.default = default if not isinstance(default, str) else type(default)
        self.desc = desc
        self.checkfun = check
        self.required = required and (default is None)

    def __repr__(self):
        attrs = {
            'name': self.name,
            'default': self.default,
            'desc': self.desc,
            'checkfun': self.checkfun,
        }
        if self.default is None:
            attrs['required'] = self.required
        attrstr = ', '.join(f'{a}={repr(v)}' for a, v in attrs.items())
        return f'Par({attrstr})'

    def __str__(self):
        ''' Markdown representation string. '''
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

    def simple_str(self):
        ''' Non-markdown representation string. '''
        out = [f'{self.name}:']
        if self.desc:
            out.append(' ' + self.desc)
        out.append(' (' + self.type.__name__ + '')
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
    def __init__(self, params=None, **kwargs):
        if params and kwargs:
            raise Exception('Only create a Signature from either a dict or kwargs.')
        params = params or kwargs
        # Force all keys lowercase
        params  = {k.lower(): v for k, v in params.items()}
        super().__init__(params)
        # Tell each Parameter its name
        for param in params:
            params[param].name = param

    def __repr__(self):
        return 'Signature(%s)' % ', '.join(f'{p}={repr(a)}' for p, a in self.items())
    def __str__(self):
        return '\n'.join(f'• {p}: {a}' for p, a in self.items())

    async def parse_and_determine(self, string: str, ctx: Context, greedy=True) -> tuple[dict[str], str, ErrorLog]:
        ''' Shortcuts the process of parsing/checking an argstring, determining each argument, and producing an args dict. '''
        # 1. Creates Arguments object by parsing the string according to the Signature
        arguments, remainder, errors = Arguments.from_string(string, self, greedy=greedy)
        if errors.terminal:
            return None, None, errors
        # 2. (Optionally) evaluating the remainder string
        if not greedy and remainder is not None:
            remainder, rem_errors = await remainder.evaluate(ctx)
            errors.extend(rem_errors, 'input string')
        # 3. Evaluate each given argument
        args, det_errors = await arguments.determine(ctx)
        errors.extend(det_errors, 'arguments')
        # Return
        return args, remainder, errors


def with_signature(arg=None, **kwargs: dict[str, Par]):
    ''' Creates a Signature from the given dict or kwargs and stores it on the given function. '''
    if arg and kwargs:
        raise ValueError('with_signature should either specify one arg, or a set of kwargs, not both.')
    signature = arg if isinstance(arg, Signature) else Signature(arg or kwargs)
    def _with_signature(f: Callable):
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

    def try_predetermine(self, errors: ErrorLog):
        if self.string.is_string:
            try:
                self.value = self.param.parse(self.string.string) if self.param else self.string.string
                self.predetermined = True
            except ArgumentError as e:
                errors.log(e, True)

    async def determine(self, context: Context, scope: ItemScope, errors: ErrorLog) -> T | None:
        if self.predetermined: return self.value

        value, arg_errs = await self.string.evaluate(context, scope)
        if arg_errs: errors.extend(arg_errs, context=f'parameter `{self.name}`')
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
    '''
    A set of parsed Args, meta-information, and the utility to determine them all into a single dict.
    `args` maps every single parameter to an Arg, even ones not assigned, which will be a DefaultArg instance.
    '''
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
        except ParseBaseException as e:
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
            elif arg._name == 'quoted_implicit_arg':
                remainder_piece = TemplatedString.from_parsed(arg, start_index)
                errors.extend(remainder_piece.pre_errors, 'implicit arg')
                start_index = remainder_piece.end_index
                remainder_pieces.append(remainder_piece)
            elif arg._name == 'implicit_arg':
                remainder_piece = TemplatedString.from_parsed(arg['implicit_arg'], start_index).strip()
                errors.extend(remainder_piece.pre_errors, 'implicit arg')
                start_index = remainder_piece.end_index
                remainder_pieces.append(remainder_piece)
            else:
                Exception()

        remainder = TemplatedString.join(remainder_pieces)

        ## Step 2: Turn into Arg objects
        for param in list(args):
            if signature is None:
                # Special case: Naive Arg
                args[param] = Arg(args[param], param)
                args[param].try_predetermine(errors)
            elif param in signature:
                args[param] = Arg(args[param], signature[param])
                args[param].try_predetermine(errors)
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
                args[param].try_predetermine(errors)

        ## Step 4: Check if the Signature's first parameter hasn't been assigned yet and try to use the remainder for it
        elif not errors.terminal and greedy and remainder and len(signature) >= 1:
            param = next(p for p in signature)
            if param not in args:
                # Try using the implicit parameter, but if it causes errors, pretend we didn't see anything!
                maybe_errors = ErrorLog()
                implicit, remainder = remainder.split_implicit_arg(greedy)
                arg = Arg(implicit, signature[param])
                arg.try_predetermine(maybe_errors)

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
    def __bool__(self):
        # Truthy if and only if it contains any non-default arguments
        return len(self.args) > len(self.defaults)

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
