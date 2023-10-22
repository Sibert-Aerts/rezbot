from datetime import datetime, timezone
from pyparsing import ParseBaseException, ParseSyntaxException, StringEnd
import discord


class TerminalErrorLogException(Exception):
    def __init__(self, errors: 'ErrorLog'):
        self.errors = errors


class ErrorLog:
    '''Class for storing warning and error messages related to Rezbot scripting.'''
    def __init__(self, name=None):
        self.name = name
        self.clear()

    def clear(self):
        self.errors: list[ErrorLog.ErrorMessage] = []
        self.terminal = False
        self.time = datetime.now(tz=timezone.utc)

    class ErrorMessage:
        def __init__(self, message: str, count=1):
            self.message: str = message
            self.count: int = count
        def __str__(self):
            return ('**(%d)** ' % self.count if self.count > 1 else '') + self.message

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
            self.errors.append(ErrorLog.ErrorMessage(message))
        self.terminal |= terminal
        return self

    def __call__(self, message, terminal=False):
        return self.log(message, terminal=terminal)

    def warn(self, message):
        return self.log(message, terminal=False)

    def log_parse_exception(self, e: ParseBaseException):
        ''' Bespoke formatting for a not-uncommon terminal exception. '''
        print('Logging parse exception:', str(e))
        ### Create a human-readable error message
        error_msg = e.msg[0].lower() + e.msg[1:]
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

    def extend(self, other: 'ErrorLog', context=None):
        '''extend another error log, prepending the given 'context' for each error.'''
        self.terminal |= other.terminal
        for e in other.errors:
            if context is not None: message = f'**in {context}:** {e.message}'
            else: message = e.message
            if self.errors and self.errors[-1].message == message:
                self.errors[-1].count += e.count
            else:
                self.errors.append(ErrorLog.ErrorMessage(message, e.count))
        return self

    def steal(self, other, *args, **kwargs):
        self.extend(other, *args, **kwargs)
        other.clear()
        return self

    #############################################
    ## Log viewing and presenting methods
    #############################################

    def __bool__(self): return len(self.errors) > 0
    def __len__(self): return len(self.errors)

    def embed(self, name=None):
        desc = '\n'.join(str(m) for m in self.errors) if self.errors else 'No warnings!'

        if len(desc) > 4000:
            raise Exception('Too many errors to be of reasonable use!')

        if self.terminal:
            embed = discord.Embed(title='Error log', description=desc, color=0xff3366)
        else:
            embed = discord.Embed(title='Warning log', description=desc, color=0xffdd33)
        # embed.timestamp = self.time
        name = name or self.name
        if name: embed.title += ' for ' + name
        return embed
