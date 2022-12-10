from datetime import datetime, timezone
from pyparsing import ParseException, StringEnd
import discord


class ErrorLog:
    '''Class for logging warnings & error messages from a pipeline's execution.'''
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

    def __call__(self, message, terminal=False):
        self.log(message, terminal=terminal)

    def warn(self, message):
        self.log(message, terminal=False)

    def parseException(self, e: ParseException):
        ''' Bespoke formatting for a not-uncommon terminal exception. '''
        if isinstance(e.parserElement, StringEnd):
            message = f'ParseException: Likely unclosed brace at position {e.loc}:\n­\t'
            message += f'{e.line[:e.col-1]}**[{e.line[e.col-1]}](http://0)**{e.line[e.col:]}'
            self.log(message, True)
        else:
            self.log('An unexpected ParseException occurred!')
            self.log(e, True)

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

    def steal(self, other, *args, **kwargs):
        self.extend(other, *args, **kwargs)
        other.clear()

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
