from .pipes import *
from .pipecommands import customPipes

import permissions
import utils.texttools as texttools

################################################################
#              The class that puts it all to work              #
################################################################

class PipeProcessor:
    def __init__(self, bot, prefix):
        self.bot = bot
        self.prefix = prefix
        self.prevOutput = []

    async def pipe_say(self, dest, output):
        ''' Nicely print the output in rows and columns and even with little arrows.'''

        # Don't apply any formatting if the output is just a single string
        if len(output) == 1 and len(output[0]) == 1:
            await self.bot.send_message(dest, output[0][0])
            return

        rowCount = len(max(output, key=len))
        rows = [''] * rowCount
        for c in range(len(output)):
            col = output[c]
            colWidth = len(max(col, key=len))
            for r in range(rowCount):
                if r < len(col):
                    rows[r] += col[r] + ' ' * (colWidth - len(col[r]))
                else:
                    rows[r] += ' ' * colWidth 
                try:
                    output[c+1][r]
                    rows[r] += ' → '
                except:
                    rows[r] += '   '
                    pass

        output = texttools.block_format('\n'.join(rows))
        await self.bot.send_message(dest, output)

    def parse_sequence(seq):
        # Literally just find-and-replace arrows for print pipes
        seq = seq.replace('->', '>print>')
        # Split on > to determine pipes
        seq = [p.strip() for p in seq.split('>')]
        return seq

    async def process_pipes(self, message):
        content = message.content

        if not content.startswith(self.prefix):
            return False
        content = content[len(self.prefix):]

        pipes = PipeProcessor.parse_sequence(content)

        # Determine our starting values
        # todo: genericize this
        if pipes[0][:6] == '{prev}':
            # prev: use the previous output
            values = self.prevOutput
            index = re.match('\[\d*\]', pipes[0][6:])
            if index is not None:
                try:
                    index = int(index.group(0)[1:-1].strip())
                    print(index)
                    values = [values[index]]
                except:
                    pass
                    
        elif pipes[0][:6] == '{that}':
            # that: use the contents of the previous message in chat
            # (requires the bot to have been online when it was posted since I don't want to mess with logs...)
            msg = [m for m in self.bot.messages if m.channel == message.channel][-2]
            values = [msg.content]
        else:
            # Expand the input value, that's a neat trick
            values = CTree.get_all('[' + pipes[0] + ']')

        printValues = []
        i = 1
        while i < len(pipes):
            name = pipes[i].split(' ')[0]
            if name not in pipeNames and name in customPipes:
                pipes[i:i+1] = PipeProcessor.parse_sequence(customPipes[name]['code'])
                continue
            i += 1

        for bigPipe in pipes[1:]:
            simulPipes = CTree.get_all('['+bigPipe+']')
            newValues = []
            for pipe in simulPipes:
                pipe = pipe.strip()
                split = pipe.split(' ', 1)
                name = split[0]
                args = split[1] if len(split) > 1 else ''
                
                if name == 'print':
                    # hard-coded special case
                    printValues.append(values)
                    newValues.extend(values)
                elif name in pipeNames:
                    newValues.extend(pipeNames[name](values, args))
                else:
                    print('Error: Unknown pipe ' + name)
                    newValues.extend(values)
            values = newValues
            if len(values) > 10 and not permissions.has(message.author.id, 'owner'):
                await self.bot.send_message(message.channel, bot_format('that\'s a bit much don\'t you think'))
                return True

        printValues.append(values)
        self.prevOutput = values
        await self.pipe_say(message.channel, printValues)
        return True