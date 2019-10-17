from functools import wraps
from textwrap import dedent
from utils.texttools import *

class ArgumentError(ValueError):
    '''Special error in case a bad argument is passed.'''
    pass


class Sig:
    '''Class representing a single item in a function signature.'''
    def __init__(self, type, default=None, desc=None, check=None, required=None, options=None, multi_options=False):
        self.type = type
        self.default = default
        self.desc = desc
        self._check = check
        self.options = options and [option.lower() for option in options]
        self.multi_options = multi_options
        self.required = required if required is not None else (default is None)
        self._re = None
        self.str = None

    def re(self):
        # This regex matches the following formats:
        #   name=valueWithoutSpaces
        #   name="value with spaces"  and  name=""  (for the empty string)
        #   name='value with spaces'  and  name=''
        # Doesn't match:
        #   name=value with spaces
        #   name="value with "quotes""
        #   name= (for the empty string)
        if self._re is None:
            self._re = re.compile(r'\b' + self.name + r'=("[^"]*"|\'[^\']*\'|\S+)\s*')
        return self._re

    def check(self, val):
        '''Check whether the value meets superficial requirements.'''
        # If a manual check-function is given, use it
        if self._check and not self._check(val):
            raise ArgumentError('Invalid value "{}" for argument "{}".'.format(val, s))

        # If a specific list of options is given, check if the value is one of them
        if self.options:
            if self.multi_options:
                if any( v not in self.options for v in val.lower().split(',') ):
                    if len(self.options) <= 8:
                        raise ArgumentError('Invalid value "{}" for argument "{}": Must be a sequence of items from {} separated by commas.'.format(val, self.name, '/'.join(self.options)))
                    else:
                        raise ArgumentError('Invalid value "{}" for argument "{}".'.format(val, self.name))
            else:
                if val.lower() not in self.options:
                    if len(self.options) <= 8:
                        raise ArgumentError('Invalid value "{}" for argument "{}": Must be one of {}.'.format(val, self.name, '/'.join(self.options)))
                    else:
                        raise ArgumentError('Invalid value "{}" for argument "{}".'.format(val, self.name))

    def __str__(self):
        if self.str: return self.str

        out = []
        if self.desc is not None:
            out.append( ' ' + self.desc )

        typ = self.type.__name__ + (' list' if self.multi_options else '')
        out.append(' (' + typ + ', ' )
        
        if self.default is not None:
            d = self.default
            out.append( 'default: ' + repr(d) )
        else:
            out.append( 'REQUIRED' )
        out.append( ')' )

        self.str = ''.join(out)
        return self.str


def parse_args(signature, text, greedy=True):
    '''Parses and removes args from a string of text.'''
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
        match = sig.re().search(text)

        if match is None:
            ## If it is required: Raise an error
            if sig.required:
                raise ArgumentError('Missing argument: "{}".'.format(s))
            ## Else: Use the default value and move on!
            args[s] = sig.default
            continue

        ## We found an assignment of some form
        val = match.group(1)

        # Strip quote marks
        if val[0] == val[-1] in ["'", '"']: # This works I swear
            val = val[1:-1]

        try:
            # Cast to the desired type (raises an exception if the value is bad)
            val = sig.type(val)
        except:
            raise ArgumentError('Invalid value "{}" for argument "{}": Must be of type {}'.format(val, s, sig.type.__name__))

        # Check whether the value meets certain requirements (raises an exception if not)
        sig.check(val)

        # It passed the checks, assign the value and clip it from the text
        args[s] = val
        text = text[:match.start(0)] + text[match.end(0):]

    return (text, args)
