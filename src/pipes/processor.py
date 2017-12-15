from .pipes import *
from .sources import *
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

        # Pretty smelly, assumes only one bot will ever run per client... which is kind of a safe assumption tbh...
        SourceResources.bot = bot

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
        # TODO: Instead of just splitting on > make it SMARTER for BETTER BRANCHES (pyparsing or something?!)
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
        source = pipes[0]
        pipes = pipes[1:]

        # Use the Source to determine a starting value

        # Matches: '{<sourceName> <args>}'
        sourceMatch = re.match('{([^}\s]+)(\s+([^\s][^{]*)?)?}', source)

        if sourceMatch is None:
            # No source pipe given. Simply interpret the source as a string.
            # ...but expand it first, because that's a nice feature...
            values = CTree.get_all('[' + source + ']')
        else:
            # A source was specified
            sourceName, _, args = sourceMatch.groups()
            sourceName = sourceName.lower()

            if sourceName in sourceNames:
                values = sourceNames[sourceName](message, args)
            else:
                print('Error: Unknown source ' + sourceName)
                print([i for i in sourceNames])
                return

        # Increment i manually because we're doing some funny stuff
        i = 0
        while i < len(pipes):
            name = pipes[i].split(' ')[0]
            if name not in pipeNames and name in customPipes:
                pipes[i:i+1] = PipeProcessor.parse_sequence(customPipes[name]['code'])
                continue
            i += 1

        printValues = []

        for bigPipe in pipes:
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
                    try:
                        newValues.extend(pipeNames[name](values, args))
                    except:
                        print('Failed to process pipe "{}" with args "{}"'.format(name, args))
                        newValues.extend(values)
                else:
                    print('Error: Unknown pipe ' + name)
                    newValues.extend(values)
            values = newValues
            if len(values) > 20 and not permissions.has(message.author.id, 'owner'):
                await self.bot.send_message(message.channel, bot_format('that\'s a bit much don\'t you think'))
                return True

        printValues.append(values)
        SourceResources.previous_pipe_output = values
        await self.pipe_say(message.channel, printValues)
        return True