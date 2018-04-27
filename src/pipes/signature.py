from functools import wraps
from textwrap import dedent
from utils.texttools import *

class ArgumentError(ValueError):
    '''Special error in case a bad argument is passed.'''
    pass


class Sig:
    '''Class representing a single item in a function signature.'''
    def __init__(self, type, default=None, desc=None, check=None):
        self.type = type
        self.default = default
        self.desc = desc
        self.check = check
        self.str = None

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


def parse_args(signature, text):
    '''Parses and removes args from a string of text.'''
    args = {}

    # Very ungeneral special case for dealing with ordered args:
    # if there's only one argument, it is always ordered!
    # TODO: Parse multiple, ordered, unnamed arguments?
    if len(signature) == 1:
        try:
            s = next(iter(signature))
            sig = signature[s]

            # Just in case, look if the argument isn't given as arg="value"
            # If it is: Leave this special case alone and fall back to the block below
            if re.search('\\b'+s+'=([^\\s"][^\\s]*\\s*|"[^"]*"|\'[^\']*\')', text): raise ValueError()

            # Take the first word and try if that works
            split = text.split(' ', 1)
            val = split[0]
            # if the "found" argument is the empty string we didnt actually find anything
            if val.strip() != '':
                args[s] = sig.type(val)
                if sig.check is None or sig.check(args[s]):
                    return (split[1] if len(split) > 1 else '', args)
        except:
            pass

    for s in signature:
        sig = signature[s]
        try:
            # Try to find and parse the argument value, and remove it from the text
            # This regex matches the following formats:
            #   arg=valueWithoutSpaces
            #   arg="value with spaces"     arg=""  (for the empty string)
            #   arg='value with spaces'     arg=''
            # Doesn't match:
            #   arg=value with spaces
            #   arg="value with "quotes""
            #   arg= (for the empty string)
            given = re.search('\\b'+s+'=([^\\s"\'][^\\s]*\\s*|"[^"]*"|\'[^\']*\')', text)
            val = given.group(0).split('=', 1)[1].strip()
            if val[0] == val[-1] and (val[0] == '\'' or val[0] == '"'):
                val = val[1:-1]
            args[s] = sig.type(val)

            # Verify that the value meets the check function (if one exists)
            if sig.check and not sig.check(args[s]):
                raise ArgumentError('Invalid value "{}" for argument "{}".'.format(args[s], s))

            text = text[:given.start(0)] + text[given.end(0):]

        except ArgumentError as e:
            raise e

        except:
            # Use the default argument value
            args[s] = sig.default
            if args[s] is None:
                raise ArgumentError('Missing or invalid argument "{}".'.format(s))

    return (text, args)
