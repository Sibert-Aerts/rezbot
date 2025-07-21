from datetime import datetime
from pyparsing import ParseBaseException, ParseSyntaxException, StringEnd
import discord


class TerminalErrorLogException(Exception):
    def __init__(self, errors: 'ErrorLog', context=None):
        self.errors = errors
        self.context = context


class ErrorLog:
    '''
    Class for storing, conveying and combining warning and error messages in Rezbot scripting.
    '''

    class Message:
        __slots__ = ('message', 'count')
        def __init__(self, message: str, count=1):
            self.message = message
            self.count = count
        def __str__(self):
            return ('**(%d)** ' % self.count if self.count > 1 else '') + self.message
        def __repr__(self):
            entries = [self.message]
            if self.count > 1:
                entries.append(self.count)
            return f'ErrorLog.Message({", ".join(entries)})'

    __slots__ = ('name', 'errors', 'terminal')

    name: str | None
    errors: list['ErrorLog.Message']
    terminal: bool

    def __init__(self, name=None):
        self.name = name
        self.clear()

    def clear(self):
        self.errors = []
        self.terminal = False

    #############################################
    ## Error logging methods
    #############################################

    def log(self, message, terminal=False, context=None):
        ''' The error-logging method '''
        message = str(message)
        if context is not None: message = f'**in {context}:** {message}'
        if self.errors and self.errors[-1].message == message:
            self.errors[-1].count += 1
        else:
            print(datetime.now().strftime('[%X]'), 'Error' if terminal else 'Warning', 'logged:', message)
            self.errors.append(ErrorLog.Message(message))
        self.terminal |= terminal
        return self

    def __call__(self, message, terminal=False):
        # DEPRECATED
        return self.log(message, terminal=terminal)

    def warn(self, message):
        return self.log(message, terminal=False)

    def log_exception(self, message, e: Exception, terminal=True):
        if isinstance(e, TerminalErrorLogException):
            self.log(message, terminal=terminal)
            return self.extend(e.errors, e.context)
        else:
            message = f'{message}:\n\t{type(e).__name__}: {e}'
            return self.log(message, terminal=terminal)

    def log_parse_exception(self, e: ParseBaseException):
        ''' Bespoke formatting for a not-uncommon terminal exception. '''
        print('Logging parse exception:', str(e))
        ### Create a human-readable error message
        error_msg = e.msg and (e.msg[0].lower() + e.msg[1:])
        if isinstance(e.parserElement, StringEnd):
            message = f'ParseException: Likely unclosed expression at position {e.loc}:\n­\t'
        elif e.col-1 == len(e.line):
            message = f'ParseSyntaxException: Unexpected end of code, {error_msg}:\n­\t'
        elif isinstance(e, ParseSyntaxException):
            message = f'ParseSyntaxException: Invalid syntax at position {e.loc}, {error_msg}:\n­\t'
        else:
            message = f'{type(e).__name__}: Unexpected ParseException at position {e.loc}, {error_msg}:\n­\t'
        ### Create a highlighted piece of code
        if e.col-1 == len(e.line):
            message += f'{e.line} **[(?)](http://0)**'
        else:
            bad_char = e.line[e.col-1]
            if bad_char in '[]':
                message += f'{e.line[:e.col-1]}**{bad_char}**{e.line[e.col:]}'
            else:
                message += f'{e.line[:e.col-1]}**[{bad_char}](http://0)**{e.line[e.col:]}'
        return self.log(message, True)

    #############################################
    ## Log transfering methods
    #############################################

    def extend(self, other: 'ErrorLog | None', context: str=None):
        '''Extend another ErrorLog, prepending the given 'context' for each error. Returns `self` for chaining'''
        if other is None:
            return self
        self.terminal |= other.terminal
        for e in other.errors:
            if context is not None: message = f'**in {context}:** {e.message}'
            else: message = e.message
            if self.errors and self.errors[-1].message == message:
                self.errors[-1].count += e.count
            else:
                self.errors.append(ErrorLog.Message(message, e.count))
        return self

    def steal(self, other: 'ErrorLog', *args, **kwargs):
        '''Extend another ErrorLog and clear it, on the assumption that we "own" the object in question.'''
        self.extend(other, *args, **kwargs)
        if other is not None:
            other.clear()
        return self

    def raise_exception(self, context=None):
        raise TerminalErrorLogException(self, context)

    #############################################
    ## Log viewing and presenting methods
    #############################################

    def __bool__(self): return len(self.errors) > 0
    def __len__(self): return len(self.errors)
    def __str__(self):
        return '\n'.join(str(m) for m in self.errors) if self.errors else 'No warnings!'
    def __repr__(self):
        msgs = '\n'.join('\n    ' + repr(m) + ',' for m in self.errors)
        if msgs: msgs += '\n'
        return f'ErrorLog(name={self.name}, terminal={self.terminal}, errors=[{msgs}])'

    def embed(self, name=None) -> discord.Embed:
        desc = str(self)
        if len(desc) > 4000:
            raise Exception('Too many errors to be of reasonable use!')

        if self.terminal:
            embed = discord.Embed(title='Error log', description=desc, color=0xff3366)
        else:
            embed = discord.Embed(title='Warning log', description=desc, color=0xffdd33)

        name = name or self.name
        if name:
            embed.title += ' for ' + name

        return embed
