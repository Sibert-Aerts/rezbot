from functools import wraps

from utils.texttools import *
from utils.ctree import CTree

# A place to put decorators to be used in pipes.py

#########################################################
#                    Argument stuff.                    #
#########################################################

class ArgumentError(ValueError):
    '''Special error in case a pipe gets passed a bad argument.'''
    pass


class Sig:
    '''Class representing a single item in a function signature.'''
    def __init__(self, type, default=None, desc=None, check=None):
        self.type = type
        self.default = default
        self.desc = desc
        self.check = check


def parse_args(signature, text):
    '''Parses and removes args from a string of text.'''
    args = {}

    # Very ungeneral special case for dealing with ordered args:
    # if there's only one argument, it is always ordered.
    if len(signature) == 1:
        try:
            s = next(iter(signature))
            sig = signature[s]
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
            given = re.search('\\b'+s+'='+'[^\\s]+\\s*', text)
            val = given.group(0).split('=')[1].strip()
            args[s] = sig.type(val)

            if sig.check and not sig.check(args[s]):
                # Value doesn't meet the check: Invalid!
                raise ArgumentError('Invalid argument value {} as "{}".'.format(args[s], s))

            text = text[:given.start(0)] + text[given.end(0):]

        except ArgumentError as e:
            raise e

        except:
            # Use the default argument value
            args[s] = sig.default
            if args[s] is None:
                raise ArgumentError('Missing required argument "{}".'.format(s))

    return (text, args)


########################################################
#                  Actual pipe stuff.                  #
########################################################

def signature_docstring(signature):
    '''Adds information about the signature to the function.'''
    def decorate(func):
        sigdocs = []
        simpledocs = []

        for s in signature:
            sig = signature[s]
            sigdoc = s + ':'
            if sig.desc is not None:
                sigdoc += ' ' + sig.desc
            sigdoc += ' (' + sig.type.__name__ + ', '
            sigdoc += 'REQUIRED' if sig.default is None else 'default: {}'.format(sig.default)
            sigdoc += ')'
            sigdocs.append(sigdoc)
            simpledocs.append(s + ': ' + sig.type.__name__)

        func.simpleSignature = simpledocs
        func.signature = sigdocs
        return func
    return decorate


def expandable_signature(func):
    '''
    Decorate a function that takes a signature to also accept expanding signatures.
    e.g. f'("n=[10|20]") → [f("n=10"), f("n=20")]
    '''
    @wraps(func)
    def _exp_sig(text, argstr=None):
        if argstr is None:
            return func(text, None)
        return [f for a in CTree.get_all(argstr) for f in func(text, a)]
    return _exp_sig


def with_signature(sig):
    '''Decorator that turns a string input into a string and arguments input, with the arguments removed from the string.'''
    def decorate(func):
        @signature_docstring(sig)
        @wraps(func)
        def _func(text, argstr=None):
            if argstr is None:
                (text, args) = parse_args(sig, text)
                return func([text], **args)[0]
            else:
                (_, args) = parse_args(sig, argstr)
                return func(text, **args)
        return _func
    return decorate

def as_map(func):
    '''
    Decorate a function to accept an array of first arguments:
    f: (x, *args) -> y      becomes     f': ([x], args) -> [y]
    e.g.
    pow(3, 2) -> 9          becomes     pow'([3, 4, 5], 2) -> [9, 16, 25]
    '''
    @wraps(func)
    def _as_map(input, *args, **kwargs):
        try:
            return [func(input[i], mapIndex=i, *args, **kwargs) for i in range(len(input))]
        except:
            return [func(i, *args, **kwargs) for i in input]
    return _as_map


pipeNames = {}

def make_pipe(sig, expandable=True):
    '''Makes a pipe out of something, with the given signature.'''
    def _make_pipe(func):
        func = with_signature(sig)(func)
        if expandable:
            func = expandable_signature(func)
        global pipeNames
        pipeNames[func.__name__.split('_pipe')[0]] = func
        return func
    return _make_pipe