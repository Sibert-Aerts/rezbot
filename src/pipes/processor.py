from enum import Enum

from .pipes import *
from .sources import *
from .pipe_decorations import pipes, sources
from .macros import pipe_macros, source_macros
from .source_eval import evaluate_all_sources, is_pure_source, evaluate_pure_source
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

        # remove unnecessary padding
        rows = [row.rstrip() for row in rows]
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

        pipeline = PipeProcessor.parse_sequence(content)
        source_string = pipeline[0]
        pipeline = pipeline[1:]

        values = []

        for source_string in CTree.get_all('[' + source_string + ']'):

            if is_pure_source(source_string.strip()):
                values.extend(evaluate_pure_source(source_string, message))
            else:
                values.append(evaluate_all_sources(source_string, message))

        # Increment i manually because we're doing some funny stuff
        i = 0
        while i < len(pipeline):
            name = pipeline[i].split(' ')[0]
            if name not in pipes and name in pipe_macros:
                pipeline[i:i+1] = PipeProcessor.parse_sequence(pipe_macros[name].code)
                continue
            i += 1

        printValues = []

        for bigPipe in pipeline:

            bigPipe, groupMode = groupmodes.parse(bigPipe)

            # print('GROUPMODE:', str(groupMode))

            # True and utter hack: Simply swipe triple-quoted strings out of the bigPipe and put them back
            # later in the expanded pipes, so that triple quotes escape all CTree expansion.
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