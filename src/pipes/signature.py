from functools import wraps
from textwrap import dedent
import re
from typing import List, Tuple, Dict, Any
from .logger import ErrorLog

class ArgumentError(ValueError):
    '''Special error in case a bad argument is passed.'''


class Sig:
    '''Represents a single parameter in a function signature.'''
    def __init__(self, type, default=None, desc=None, check=None, required=None, options=None, multi_options=False):
        self.type = type
        self.name = None # Assigned externally, don't worry
        self.default = default
        self.desc = desc
        self._check = check
        self.options = options and [option.lower() for option in options]
        self.multi_options = multi_options
        self.required = required if required is not None else (default is None)
        self._re = None
        self.str = None
        
    def __str__(self):
        if self.str: return self.str

        out = []
        if self.desc is not None:
            out.append( ' ' + self.desc )

        typ = self.type.__name__ + (' list' if self.multi_options else '')

        out.append(' (' + typ)    
        if self.required:
            out.append( ', REQUIRED' )
        elif self.default is not None:
            out.append( ', default: ' + repr(self.default) )
        out.append( ')' )

        self.str = ''.join(out)
        return self.str

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

    def check(self, val):
        '''Check whether the value meets superficial requirements.'''
        # If a manual check-function is given, use it
        if self._check and not self._check(val):
            raise ArgumentError('Invalid value "{}" for parameter `{}`.'.format(val, self.name))

        # If a specific list of options is given, check if the value is one of them
        if self.options:
            if self.multi_options:
                if any( v not in self.options for v in val.lower().split(',') ):
                    if len(self.options) <= 8:
                        raise ArgumentError('Invalid value "{}" for parameter `{}`: Must be a sequence of items from {} separated by commas.'.format(val, self.name, '/'.join(self.options)))
                    else:
                        raise ArgumentError('Invalid value "{}" for parameter `{}`.'.format(val, self.name))
            else:
                if val.lower() not in self.options:
                    if len(self.options) <= 8:
                        raise ArgumentError('Invalid value "{}" for parameter `{}`: Must be one of {}.'.format(val, self.name, '/'.join(self.options)))
                    else:
                        raise ArgumentError('Invalid value "{}" for parameter `{}`.'.format(val, self.name))

    def parse(self, str):
        ''' Attempt to parse and check the given string as an argument for this parameter, raises ArgumentError if it fails. '''
        try:
            val = self.type(str)
        except Exception as e:
            raise ArgumentError('Invalid value "{}" for argument `{}`: Must be of type {} ({})'.format(val, self.name, self.type.__name__, e))
        self.check(val)
        return val


class Arg:
    ''' Represents a parsed assignment of a single argument to a single parameter. '''
    def __init__(self, sig: Sig, raw: str):
        self.sig = sig
        self.raw = raw
        self.predetermined = False
        self.val = None

    def predetermine(self, errors: ErrorLog):
        ''' See if we can parse the argument value without needing to evaluate sources or items. '''        
        # Regex for checking if a string contains anything that determined ahead of time
        # i.e. sources in an argument may not be deterministic, and items can definitely not be predetermined
        if SourceProcessor.source_or_item_regex.search(self.raw) is None:
            try:
                self.val = self.sig.parse(self.raw)
                self.predetermined = True
            except ArgumentError as e:
                errors.log(e, True)

    async def determine(self, context, source_processor, errors: ErrorLog) -> Any:
        if self.predetermined: return self.val

        # Evaluate sources and context items
        evaluated = await source_processor.evaluate_composite_source(self.raw, context=context)
        errors.steal(source_processor.errors, context='parameter `{}`'.format(self.sig.name))
        # Attempt to parse the argument
        try:
            val = self.sig.parse(evaluated)
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

    async def determine(self, context, source_processor) -> Tuple[ Dict[str, Any], ErrorLog ]:
        ''' Returns a parsed {parameter: argument} dict ready for use. '''
        errors = ErrorLog()
        if self.predetermined: return self.args, errors
        return { param: await self.args[param].determine(context, source_processor, errors) for param in self.args }, errors



def parse_args(signature: Dict[str, Sig], text: str, greedy: bool=True) -> Tuple[ str, dict ]:
    ''' Parses and removes arguments from a string of text based on a signature. '''
    args = {}

    the_one = None
    require_the_one = False

    ### Two scenarios where we implicitly assume an argument is assigned (without arg=val syntax!):
    if len(signature) == 1:
        ## If there is only one argument
        the_one = next(iter(signature))
    else:
        ## OR if there is only one REQUIRED argument
        reqs = [s for s in signature if signature[s].required]
        if len(reqs) == 1:
            the_one = reqs[0]
            require_the_one = True

    if the_one is not None and text is not None:
        s = the_one
        sig = signature[s]

        # Just in case, look if the argument isn't given as "arg=val"
        # If it is: Leave this special case alone and fall back to the block below
        if sig.re().search(text) is None:

            if greedy: # Greedy: Assume the entire input string is the argument value.
                val = text
                _text = ''

            else: # Not greedy: Only try the first word
                split = re.split(r'\s+', text, 1)
                val = split[0]
                _text = split[1] if len(split) > 1 else ''

            # If the "found" argument is the empty string we didnt actually find anything
            if val.strip() != '':
                try:
                    # Try casting what we found and see if it works
                    val = sig.type(val)
                    # The check raises an exception if it fails
                    sig.check(val)
                    # It successfully converted AND passed the check: assign it and cut it from the text
                    args[s] = val
                    text = _text
                except Exception as e:
                    # We already know that there's no "arg=val" present in the string, the arg is required and we can't find it blindly:
                    if require_the_one:
                        raise e

    for s in signature:
        # If we already determined the argument value in the previous block, skip it
        if s in args: continue

        sig = signature[s]
        match = text and sig.re().search(text)

        if not match:
            ## If it is required: Raise an error
            if sig.required: raise ArgumentError('Missing argument: "{}".'.format(s))
            ## Else: Use the default value and move on!
            args[s] = sig.default
            continue

        ## We found an assignment of some form
        val = match[1] or match[2] or match[3] or match[4] or match[5] or match[6] or ''

        ## If there's any kind of trouble with the value this'll raise a well-formatted error.
        args[s] = sig.parse(val)
        # Clip the entire match out of the text
        text = text[:match.start(0)] + text[match.end(0):]

    return (text, args)

# This regex matches all forms of:
#   name=argNoSpaces    name="arg's with spaces"    name='arg with "spaces" even'
#   name="""arg with spaces and quotation marks and anything"""     name='''same'''
#   name=/semantically there is nothing signalling this is a regex but it's nice notation/
# It will not work for:
#   name=arg with spaces                (simply parses as name=arg)
#   name="quotes "nested" in quotes"    (simply parses as name="quotes ")
#   emptyString=                        (does not work, use emptyString="" instead)
#   2name=arg                           (names have to start with a letter or _)

arg_re = re.compile( r'(?i)\b([_a-z]\w*)=("""(.*?)"""|\'\'\'(.*?)\'\'\'|"(.*?)"|\'(.*?)\'|/(.*?)/|(\S+))', re.S )
#                             ^^^^^^^^^       ^^^            ^^^          ^^^      ^^^      ^^^    ^^^
#                             parameter                           argument value

# This one matches the same as above except without an explicit assignment and falls back on matching the entire string instead of just noSpaces
impl_re = re.compile( r'("""(.*?)"""|\'\'\'(.*?)\'\'\'|"(.*?)"|\'(.*?)\'|/(.*?)/|(.*))', re.S )
#                            ^^^            ^^^          ^^^      ^^^      ^^^    ^^
#                                                argument value

def parse_smart_args(signature: Dict[str, Sig], argstr: str) -> Arguments:
    ''' Smarter version of parse_args that instead returns an Arguments object. '''
    errors = ErrorLog()
    argstr_raw = argstr = argstr.strip()
    argstr = Context.preprocess(argstr)
    
    ## Step 1: Collect all explicitly assigned parameters
    args = {}
    def collect(m):
        if m[1] not in signature:
            errors.warn('Unknown parameter `{}`'.format(m[1]))
            return m[0]
        if m[1] in args:
            errors.log('Repeated assignment of parameter `{}`'.format(m[1]))
        args[m[1]] = m[3] or m[4] or m[5] or m[6] or m[7] or m[8] or ''
    remainder = arg_re.sub(collect, argstr).strip()

    ## Step 2: Process them
    for param in args:
        args[param] = Arg(signature[param], args[param])
        args[param].predetermine(errors)

    ## Step 3: Check if required arguments are missing
    missing = [param for param in signature if param not in args and signature[param].required]
    if missing:
        if not remainder or len(missing) > 1:
            # There's no argstring left; nothing can be done to find these missing arguments
            # Or: there's more missing parameters than I'm willing to blindly parse
            errors.log('Missing required parameter{} {}'.format('s' if len(missing) > 1 else '', ' '.join('`%s`'%p for p in missing)), True)

        elif len(missing) == 1:
            ## Only one required parameter is missing; assume the entire remaining argstring implicitly assigns it
            [param] = missing
            m = impl_re.fullmatch(remainder) # Always matches
            raw = m[2] or m[3] or m[4] or m[5] or m[6] or m[7] or ''
            args[param] = Arg(signature[param], raw)
            args[param].predetermine(errors)
            remainder = None

    ## Step 4: Check if maybe the Signature only has one not-yet-found (but not required) parameter at all
    maybe_implicit = [param for param in signature if param not in args]
    if len(maybe_implicit) == 1 and remainder:
        # In which case: assume the entire remaining argstring implicitly assigns it
        [param] = maybe_implicit
        m = impl_re.match(remainder) # Always matches
        raw = m[2] or m[3] or m[4] or m[5] or m[6] or m[7] or ''
        args[param] = Arg(signature[param], raw)
        args[param].predetermine(errors)

    ## Step 5: We tried our best; fill out default values of missing non-required parameters
    for param in signature:
        if param not in args and not signature[param].required:
            args[param] = DefaultArg(signature[param].default)

    return Arguments(args, argstr_raw), errors


# This lyne ys down here dve to dependencyes cyrcvlaire
from .sourceprocessor import SourceProcessor, Context