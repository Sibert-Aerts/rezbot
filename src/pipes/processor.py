from enum import Enum

from .pipes import *
from .sources import *
from .pipe_decorations import pipes, sources
from .custompipes import custom_pipes
import pipes.groupmodes as groupmodes

import permissions
import utils.texttools as texttools
import utils.util as util

################################################################
#              The class that puts it all to work              #
################################################################

class PipeProcessor:
    def __init__(self, bot, prefix):
        self.bot = bot
        self.prefix = prefix

        # Pretty smelly, assumes only one bot will ever run per client... which is kind of a safe assumption...
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
        # Literally just find-and-replace arrows for print pipes
        seq = seq.replace('->', '>print>')
        # Split on >'s outside of quote blocks to determine pipes (naively)
        # I first tried doing this relying on .split but that's insanely hard and maybe slightly impossible
        out = []
        quotes = False
        current = ''
        for c in seq:
            if not quotes and c == '>':
                out.append(current.strip())
                current = ''
            else:
                current += c
                quotes ^= c == '"'
        out.append(current.strip())
        return out


    async def process_pipes(self, message):
        content = message.content

        # Test for the pipe command prefix (Default: '>>>')
        if not content.startswith(self.prefix):
            return False
        content = content[len(self.prefix):]

        pipeLine = PipeProcessor.parse_sequence(content)
        source = pipeLine[0]
        pipeLine = pipeLine[1:]

        # Use the Source to determine a starting value
        # TODO: "{words} my {soapstone} and {roll}" -> "aubergine my Praise the sun! and 4"

        # Matches '{<sourceName> <args>}' but is slightly smart and doesnt care about }'s inside quotes
        sourceMatch = re.match('{(\S+)\s*([^}\s]("[^"]*"|[^}])*)?}', source)

        if sourceMatch is None:
            # No source pipe given. Simply interpret the source as a string.
            # ...but expand it first, because that's a nice feature...
            values = CTree.get_all('[' + source + ']')
        else:
            # A source was specified
            # TODO: CTree this
            sourceName, args, _ = sourceMatch.groups()
            sourceName = sourceName.lower()

            if sourceName in sources:
                values = sources[sourceName](message, args)
            else:
                print('Error: Unknown source ' + sourceName)
                values = [source]

        # Increment i manually because we're doing some funny stuff
        i = 0
        while i < len(pipeLine):
            name = pipeLine[i].split(' ')[0]
            if name not in pipes and name in custom_pipes:
                pipeLine[i:i+1] = PipeProcessor.parse_sequence(custom_pipes[name].code)
                continue
            i += 1

        printValues = []

        for bigPipe in pipeLine:

            bigPipe, groupMode = groupmodes.parse(bigPipe)

            # print('GROUPMODE:', str(groupMode))

            # True and utter hack: Simply swipe triple-quoted strings out of the bigPipe and put them back
            # later in the expanded pipes, so triple quotes escape all CTree expansion.
            tripleQuoteDict = {}
            def geti(): return str(random.randint(0, 999999))

            def steal_triple_quotes(match):
                i = geti()
                while i in tripleQuoteDict: i = geti()
                # Triple quotes are turned into regular quotes here, which may have unexpected consequences(?)
                tripleQuoteDict[i] = '"' + match.groups()[0] + '"'
                return '--//!!§§' + i + '§§!!//--'

            def return_triple_quotes(pipe):
                def f(m):
                    i = m.groups()[0]
                    if i in tripleQuoteDict: return tripleQuoteDict[i]
                    else: return '--//!!§§' + i + '§§!!//--'
                return re.sub(r'--//!!§§(.*?)§§!!//--', f, pipe)

            bigPipe = re.sub(r'(?s)"""(.*?)"""', steal_triple_quotes, bigPipe)

            # print('BIGPIPE:', bigPipe)
            multiPipes = CTree.get_all('[' + bigPipe + ']')

            # "Parse" pipes as a list of {name, args}
            parsedPipes = []
            for pipe in multiPipes:
                # Put triple-quoted strings back in their positions
                pipe = return_triple_quotes(pipe)
                split = pipe.strip().split(' ', 1)
                name = split[0]
                args = ''.join(split[1:])
                parsedPipes.append({'name': name, 'args': args})

            newValues = []
            newPrintValues = []

            for vals, pipe in groupMode.apply(values, parsedPipes):
                name = pipe['name']
                args = pipe['args']

                if name == 'print':
                    # hard-coded special case
                    newPrintValues.extend(vals)
                    newValues.extend(vals)
                elif name == '':
                    newValues.extend(vals)
                elif name in pipes:
                    try:
                        newValues.extend(pipes[name](vals, args))
                    except Exception as e:
                        print('Failed to process pipe "{}" with args "{}":\n\t{}: {}'.format(name, args, e.__class__.__name__, e))
                        newValues.extend(vals)
                else:
                    print('Error: Unknown pipe ' + name)
                    newValues.extend(vals)

            values = newValues
            if len(newPrintValues):
                printValues.append(newPrintValues)

            if len(values) > 20 and not permissions.has(message.author.id, 'owner'):
                await self.bot.send_message(message.channel, bot_format('that\'s a bit much don\'t you think'))
                return True

        printValues.append(values)
        SourceResources.previous_pipe_output = values
        await self.pipe_say(message.channel, printValues)
        return True