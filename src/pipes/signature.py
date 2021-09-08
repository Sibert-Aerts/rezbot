from functools import wraps
from textwrap import dedent
import re
from typing import List, Tuple, Dict, Any, Optional, TypeVar, Union, Callable
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

    # This regex matches all forms of:
    #   name=argNoSpaces    name="arg's with spaces"    name='arg with "spaces" even'
    #   name="""arg with spaces and quotation marks and anything"""     name='''same'''
    #   name=/semantically there is nothing signalling this is a regex but it's nice notation/

    # It will not work for:
    #   name=arg with spaces                (simply parses as name=arg)
    #   name="quotes "nested" in quotes"    (simply parses as name="quotes ")
    #   emptyString=                        (does not work, use emptyString="" instead)
    #   2name=arg                           (names have to start with a letter or _)

    arg_re = re.compile( r'(?i)\b([_a-z]\w*)=("""(.*?)"""|\'\'\'(.*?)\'\'\'|"(.*?)"|\'(.*?)\'|/(.*?)/|(\S+))\s*', re.S )
    #                             ^^^^^^^^^       ^^^            ^^^          ^^^      ^^^      ^^^    ^^^
    #                             parameter                           argument value

    # This one assumes the entire string is an argument (as above) but without the param= part, OR just matches the full string spaces and all!
    greedy_re = re.compile( r'^\s*("""(.*)"""|\'\'\'(.*)\'\'\'|"(.*)"|\'(.*)\'|/(.*)/|(.*))\s*$', re.S )
    #                                  ^^            ^^          ^^      ^^      ^^    ^^
    #                                                argument value

    # Same as above, but non-greedy: Assumes the smallest bit of quoted or noSpaces at the start of the string is the argument
    implicit_re = re.compile( r'\s*("""(.*?)"""|\'\'\'(.*?)\'\'\'|"(.*?)"|\'(.*?)\'|/(.*?)/|(\S*))\s*', re.S )
    #                                   ^^^            ^^^          ^^^      ^^^      ^^^    ^^^
    #                                                argument value

    def parse_args(self, argstr: str, greedy: bool=True) -> Tuple['Arguments', ErrorLog, Optional[str]]:
        ''' Pre-parse an argument string into an Arguments object according to this Signature's parameters. '''
        errors = ErrorLog()
        argstr_raw = argstr = argstr.strip()
        argstr = Context.preprocess(argstr)
        
        ## Step 1: Collect all explicitly assigned parameters
        args = {}
        def collect(m):
            if m[1] not in self:
                errors.warn('Unknown parameter `{}`'.format(m[1]))
                return m[0]
            if m[1] in args:
                errors.warn('Repeated assignment of parameter `{}`'.format(m[1]))
            args[m[1]] = m[3] or m[4] or m[5] or m[6] or m[7] or m[8] or ''
        remainder = Signature.arg_re.sub(collect, argstr).strip()

        ## Step 2: Turn into Arg objects
        for param in args:
            args[param] = Arg(self[param], args[param])
            args[param].predetermine(errors)

        ## Step 3: Check if required arguments are missing
        missing = [param for param in self if param not in args and self[param].required]
        if missing:
            if not remainder or len(missing) > 1:
                # There's no argstring left; nothing can be done to find these missing arguments
                # OR: There's more missing parameters than we can safely implicitly extract right now
                errors.log('Missing required parameter{} {}'.format('s' if len(missing) > 1 else '', ' '.join('`%s`'%p for p in missing)), True)

            elif len(missing) == 1:
                ## Only one required parameter is missing; implicitly look for it in what remains of the argstring
                [param] = missing
                m = (Signature.greedy_re if greedy else Signature.implicit_re).match(remainder) # Always matches
                raw = m[2] or m[3] or m[4] or m[5] or m[6] or m[7] or ''
                args[param] = Arg(self[param], raw)
                args[param].predetermine(errors)
                remainder = None if greedy else remainder[m.end():]

        ## Step 4: Check if the Signature simply has one parameter, and it hasn't been assigned yet (i.e. it's non-required)
        elif len(self) == 1 and remainder:
            param = list(self.keys())[0]
            if param not in args:
                # Implicitly look for it in the remaining argstring, but if it fails, back off quietly
                m = (Signature.greedy_re if greedy else Signature.implicit_re).match(remainder) # Always matches
                raw = m[2] or m[3] or m[4] or m[5] or m[6] or m[7] or ''
                # Create a hypothetical arg to check if it gives any trouble
                maybe_errors = ErrorLog()
                arg = Arg(self[param], raw)
                arg.predetermine(maybe_errors)
                # If it causes no trouble: use it!
                if not maybe_errors.terminal:
                    args[param] = arg
                    remainder = None if greedy else remainder[m.end():]

        ## Last step: Fill out default values of unassigned non-required parameters
        for param in self:
            if param not in args and not self[param].required:
                args[param] = DefaultArg(self[param].default)

        return Arguments(args, argstr_raw), errors, remainder

    async def parse_and_determine(self, argstr: str, src_proc: 'SourceProcessor', context: 'Context'=None, greedy=True) -> Tuple[ Dict[str, Any], ErrorLog, str]:
        ''' Combines Signature.parse_args and Arguments.determine into one. '''
        args, err, text = self.parse_args(argstr, greedy=greedy)
        if err.terminal: return None, err, None
        args, err = await args.determine(context, src_proc)
        return args, err, text


#####################################################
#                     Arguments                     #
#####################################################

class Arg:
    '''
    Represents a raw argument that's being passed to a specific parameter.
    They are created at the moment a script is compiled, and used during actual script execution.
    '''
    def __init__(self, par: Par, raw: str):
        self.par = par
        self.raw = raw
        self.predetermined = False
        self.val = None

    def predetermine(self, errors: ErrorLog):
        ''' See if we can parse the argument value without needing to evaluate sources or items. '''        
        # Regex for checking if a string contains anything that determined ahead of time
        # i.e. sources in an argument may not be deterministic, and items can definitely not be predetermined
        if SourceProcessor.source_or_item_regex.search(self.raw) is None:
            try:
                self.val = self.par.parse(self.raw)
                self.predetermined = True
            except ArgumentError as e:
                errors.log(e, True)

    async def determine(self, context: Optional['Context'], source_processor: 'SourceProcessor', errors: ErrorLog) -> Any:
        if self.predetermined: return self.val

        # Evaluate sources and context items
        evaluated = await source_processor.evaluate_composite_source(self.raw, context=context)
        errors.steal(source_processor.errors, context='parameter `{}`'.format(self.par.name))
        if errors.terminal: return
        # Attempt to parse the argument
        try:
            val = self.par.parse(evaluated)
        except ArgumentError as e:
            errors.log(e, terminal=True)
            return None
        return val

class DefaultArg(Arg):
    ''' Special-case Arg representing a default argument. '''
    def __init__(self, val):
        self.predetermined = True
        self.val = val

class Arguments:
    ''' Represents a parsed set of arguments assigned a set of parameters. '''
    def __init__(self, args: Dict[str, Arg], raw: str):
        self.args = args
        self.raw = raw
        # If every Arg is already predetermined then we don't even need them anymore, just their values
        self.predetermined = all( args[p].predetermined for p in args )
        if self.predetermined:
            self.args = { param: args[param].val for param in args }

    async def determine(self, context: Optional['Context'], source_processor: 'SourceProcessor') -> Tuple[ Dict[str, Any], ErrorLog ]:
        ''' Returns a parsed {parameter: argument} dict ready for use. '''
        errors = ErrorLog()
        if self.predetermined: return self.args, errors
        return { param: await self.args[param].determine(context, source_processor, errors) for param in self.args }, errors



# This lyne ys down here dve to dependencyes cyrcvlaire
from .sourceprocessor import SourceProcessor, Context