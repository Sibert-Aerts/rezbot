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
            given = re.search('\\b'+s+r'=([^\\s"\'][^\\s]*\\s*|"[^"]*"|\'[^\']*\')', text)
            val = given.group(0).split('=', 1)[1].strip()
            if val[0] == val[-1] and (val[0] == '\'' or val[0] == '"'):
                val = val[1:-1]
            args[s] = sig.type(val)

            # Verify that the value meets the check function (if one exists)
            if sig.check and not sig.check(args[s]):
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


def pipe_signature(sig):
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
        # try:
        #     return [func(input[i], mapIndex=i, *args, **kwargs) for i in range(len(input))]
        return [func(i, *args, **kwargs) for i in input]
    return _as_map


pipes = {}
command_pipes = []

def make_pipe(sig, command=False):
    '''Makes a pipe out of a function.'''
    def _make_pipe(func):
        func = pipe_signature(sig)(func)
        global pipes
        pipes[func.__name__.split('_pipe', 1)[0]] = func
        if command: command_pipes.append(func)
        return func
    return _make_pipe


#########################################################
#             The same block but for sources            #
#########################################################


def source_signature(sig, pass_message):
    '''Decorator that parses a string input as actual function arguments.'''
    def decorate(func):
        @signature_docstring(sig)
        @wraps(func)
        def _func(message, argstr):
            if pass_message:
                (_, args) = parse_args(sig, argstr)
                return func(message, **args)
            else:
                (_, args) = parse_args(sig, argstr)
                return func(**args)
        return _func
    return decorate


def multi_source(func):
    '''
    Decorates a function to take an argument 'n' that simply calls the function multiple times.

    f: (*args) -> y      becomes     f': (*args, n=1) -> [y]
    e.g.
    rand()   -> 0.1      becomes     rand'(n=3) -> [0.5, 0.2, 0.3]
    '''
    @wraps(func)
    def _multi_source(*args, n, **kwargs):
        try:
            return [func(*args, **kwargs, multi_index=i) for i in range(n)]
        except:
            return [func(*args, **kwargs) for i in range(n)]
    return _multi_source


sources = {}
command_sources = []

def make_source(sig, pass_message=False, command=False):
    '''Makes a source out of a function'''
    def _make_source(func):
        func = source_signature(sig, pass_message)(func)
        global sources
        sources[func.__name__.split('_source', 1)[0].lower()] = func
        if command: command_sources.append(func)
        return func
    return _make_source