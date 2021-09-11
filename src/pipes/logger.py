from datetime import datetime, timezone
import discord


class ErrorLog:
    '''Class for logging warnings & error messages from a pipeline's execution.'''
    def __init__(self):
        self.clear()

    def clear(self):
        self.errors = []
        self.terminal = False
        self.time = datetime.now(tz=timezone.utc)

    class ErrorMessage:
        def __init__(self, message, count=1):
            self.count = count
            self.message = message
        def __str__(self):
            return ('**(%d)** ' % self.count if self.count > 1 else '') + self.message

    def __call__(self, message, terminal=False):
        ''' The error-logging method '''
        message = str(message)
        if self.errors and self.errors[-1].message == message:
            self.errors[-1].count += 1
        else:
            print(datetime.now().strftime('[%X]'), 'Error' if terminal else 'Warning', 'logged:', message)
            self.errors.append(ErrorLog.ErrorMessage(message))
        self.terminal |= terminal

    log = __call__
    def warn(self, message):
        self.log(message, terminal=False)

    def extend(self, other, context=None):
        '''extend another error log, prepending the given 'context' for each error.'''
        self.terminal |= other.terminal
        for e in other.errors:
            if context is not None: message = '**in {}:** {}'.format(context, e.message)
            else: message = e.message
            if self.errors and self.errors[-1].message == message:
                self.errors[-1].count += e.count
            else:
                self.errors.append(ErrorLog.ErrorMessage(message, e.count))

    def steal(self, other, *args, **kwargs):
        self.extend(other, *args, **kwargs)
        other.clear()

    def __bool__(self): return len(self.errors) > 0
    def __len__(self): return len(self.errors)

    def embed(self, name=None):
        desc = '\n'.join(str(m) for m in self.errors) if self.errors else 'No warnings!'
        if self.terminal:
            embed = discord.Embed(title='Error log', description=desc, color=0xff3366)
        else:
            embed = discord.Embed(title='Warning log', description=desc, color=0xffdd33)
        # embed.timestamp = self.time
        if name: embed.title += ' for ' + name
        return embed
