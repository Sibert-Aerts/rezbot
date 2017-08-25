from .pipes import *

import permissions
import utils.texttools as texttools

################################################################
#              The class that puts it all to work              #
################################################################

class PipeProcessor:
    def __init__(self, bot):
        self.bot = bot
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

    async def process_pipes(self, message):
        content = message.content

        if content[:3] != '>>>': 
            return False
        content = content[3:]

        # Literally just find-and-replace arrows for print pipes
        content = re.sub('->', '>print>', content)

        # Split on > to determine pipes
        pipes = [p.strip() for p in content.split('>')]

        printValues = []

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

        for pipe in pipes[1:]:
            split = pipe.split(' ', 1)
            name = split[0]
            args = split[1] if len(split) > 1 else ''
            
            if name == 'print':
                # hard-coded special case
                printValues.append(values)
                continue
            try:
                values = pipeNames[name](values, args)
            except KeyError:
                print('Error: Unknown pipe ' + name)

            if len(values) > 10 and not permissions.has(message.author.id, 'owner'):
                await self.bot.send_message(message.channel, bot_format('that\'s a bit much don\'t you think'))
                return True

        printValues.append(values)
        self.prevOutput = values
        await self.pipe_say(message.channel, printValues)
        return True