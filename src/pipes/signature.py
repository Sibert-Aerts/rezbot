from functools import wraps
from textwrap import dedent
from utils.texttools import *

class ArgumentError(ValueError):
    '''Special error in case a bad argument is passed.'''
    pass


class Sig:
    '''Class representing a single item in a function signature.'''
    def __init__(self, type, default=None, desc=None, check=None, required=None):
        self.type = type
        self.default = default
        self.desc = desc
        self.check = check
        self.required = required if required is not None else (default is None)
        self._re = None
        self.str = None

    def re(self, name):
        # This regex matches the following formats:
        #   name=valueWithoutSpaces
        #   name="value with spaces"     name=""  (for the empty string)
        #   name='value with spaces'     name=''
        # Doesn't match:
        #   name=value with spaces
        #   name="value with "quotes""
        #   name= (for the empty string)
        if self._re is None:
            self._re = re.compile('\\b' + name + '=("[^"]*"|\'[^\']*\'|\S+)\\s*')
        return self._re

    def __str__(self):
        if self.str: return self.str

        out = ''
        if self.desc is not None:
            out += ' ' + self.desc
        out += ' (' + self.type.__name__ + ', '
        if self.default is not None:
            d = self.default
            if d == '': d ='""'
            out += 'default: ' + str(d)
        else:
            out += 'REQUIRED'
        out += ')'

        self.str = out
        return out


def parse_args(signature, text, greedy=True):
    '''Parses and removes args from a string of text.'''
    args = {}

    the_one = None
    required = False

    # Two scenarios where we implicitly assume an argument (without arg=val syntax!):
    # If there is only one argument
    if len(signature) == 1:
        the_one = next(iter(signature))
    # Or if there is only one REQUIRED argument
    else:
        reqs = [s for s in signature if signature[s].required]
        if len(reqs) == 1:
            the_one = reqs[0]
            required = True

    if the_one is not None and text is not None:
        s = the_one
        sig = signature[s]

        # Just in case, look if the argument isn't given as "arg=val"
        # If it is: Leave this special case alone and fall back to the block below
        if re.search(sig.re(s), text) is None:

            if greedy: # Greedy: Assume the entire input string is the argument value.
                val = text
                text = ''

            else: # Not greedy: Only try the first word
                split = text.split(' ', 1)
                val = split[0]
                text = split[1] if len(split) > 1 else ''

            # If the "found" argument is the empty string we didnt actually find anything
            if val.strip() != '':
                # Try casting what we found and see if it works
                try:
                    args[s] = sig.type(val)
                    if sig.check is None or sig.check(args[s]):
                        return (text, args)
                except:
                    # We know that there's no "arg=val" present in the string, the arg is required and we can't find it blindly:
                    if required: raise ArgumentError('Missing or invalid argument "{}".'.format(s))

    for s in signature:
        sig = signature[s]
        # If at any point here any exception occurs, it'll try to use the default value instead.
        try:
            # Find and parse the argument value, and remove it from the text.
            given = re.search(sig.re(s), text)
            val = given.groups()[0].strip()

            # Strip quote marks
            if val[0] == val[-1] and val[0] in ["'", '"']:
                val = val[1:-1]

            # Cast to the desired type
            args[s] = sig.type(val)

            # Verify that the value meets the check function (if one exists)
            if sig.check and not sig.check(args[s]):
                raise ArgumentError('Invalid value "{}" for argument "{}".'.format(args[s], s))

            # Remove the argument string from the text
            text = text[:given.start(0)] + text[given.end(0):]

        except ArgumentError as e:
            raise e

        except:
            if sig.required:
                raise ArgumentError('Missing or invalid argument "{}".'.format(s))
            args[s] = sig.default

    return (text, args)
