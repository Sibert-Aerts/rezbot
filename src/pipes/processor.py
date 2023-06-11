import re

from lru import LRU
from discord import Client, Message, TextChannel

# More import statements at the bottom of the file, due to circular dependencies.
from .logger import ErrorLog
import utils.texttools as texttools

'''
The PipelineProcessor class provides the primary interface through which Rezbot Scripts are executed.
'''


class TerminalError(Exception):
    '''Special error that serves as a signal to end script execution but contains no information.'''


class PipelineWithOrigin:
    '''
    Class representing a complete "Rezbot script", overwrought name to indicate is is nothing more than:
        * An origin (str) which may be expanded and evaluated.
        * A Pipeline which may be applied to that result.
    '''

    # Static LRU cache holding up to 40 parsed instances... probably don't need any more
    script_cache: dict['PipelineWithOrigin'] = LRU(40)

    def __init__(self, origin: str, pipeline: 'Pipeline'):
        self.origin = origin
        self.pipeline = pipeline

    @classmethod
    def from_string(cls, script: str):
        # No need to re-parse the same script
        if script in PipelineWithOrigin.script_cache:
            return PipelineWithOrigin.script_cache[script]

        # Parse
        origin, pipeline_str = PipelineProcessor.split(script)
        # NOTE/TODO: Parsing Pipeline() here may fail, but it won't raise an error,
        #   pipeline.parser_errors will simply be flagged as 'terminal'.
        pipeline = Pipeline(pipeline_str)

        # Instantiate, cache, return
        pwo = PipelineWithOrigin(origin, pipeline)
        PipelineWithOrigin.script_cache[script] = pwo
        return pwo


class PipelineProcessor:
    ''' Singleton class providing some global state and methods essential to the bot's scripting integration. '''

    def __init__(self, bot, prefix):
        self.bot = bot
        self.prefix = prefix
        SourceResources.bot = bot

    async def on_message(self, message):
        '''Check if an incoming message triggers any custom Events.'''
        for event in events.values():
            if not isinstance(event, OnMessage): continue
            m = event.test(message)
            if m:
                # If m is not just a bool, but a regex match object, fill the context up with the match groups, otherwise with the entire message.
                if m is not True:
                    items = [group or '' for group in m.groups()] or [message.content]
                else:
                    items = [message.content]
                context = Context(items=items)
                await self.execute_script(event.script, self.bot, message, context, name='Event: ' + event.name)

    async def on_reaction(self, channel, emoji, user_id, msg_id):
        '''Check if an incoming reaction triggers any custom Events.'''
        for event in events.values():
            if isinstance(event, OnReaction) and event.test(channel, emoji):
                message = await channel.fetch_message(msg_id)
                context = Context(items=[emoji, str(user_id)])
                await self.execute_script(event.script, self.bot, message, context, name='Event: ' + event.name)

    @staticmethod
    def split(script: str) -> tuple[str, str]:
        '''Splits a script into the source and pipeline.'''
        # So here's the deal:
        #    SOURCE > PIPE > PIPE > PIPE > ETC...
        # We only need to split on the first >, but this can be escaped by wrapping the entire thing in quotes!
        #    "SOU > RCE" > PIPE
        # We want to split on the LAST pipe there... The issue is parsing this is kinda hard maybe, because of weird cases:
        #    SOU ">" RCE    or    "SOU">"RCE" ???
        # AND also: SOURCE -> PIPE should parse as SOURCE > print > PIPE
        # So I would simply like to assume people don't put enough quotes AND >'s in their texts for this to be a problem....
        # ...because what we've been doing so far is: look at quotes as non-nesting and just split on the first non-wrapped >
        # Anyway here is a neutered version of the script used to parse Pipelines.
        quoted = False
        p = None
        for i in range(len(script)):
            c = script[i]
            if c == '"': quoted ^= True; continue
            if not quoted and c =='>':
                if p == '-':
                    return script[:i-1].strip(), 'print>'+script[i+1:]
                return script[:i].strip(), script[i+1:]
            p = c
        return script.strip(), ''

    @staticmethod
    async def send_print_values(channel: TextChannel, values: list[list[str]]):
        ''' Nicely print the output in rows and columns and even with little arrows.'''

        # Don't apply any formatting if the output is just a single cel.
        if len(values) == 1:
            if len(values[0]) == 1:
                if values[0][0].strip() != '':
                    for chunk in texttools.chunk_text(values[0][0]):
                        await channel.send(chunk)
                else:
                    await channel.send('`empty string`')
                return
            elif len(values[0]) == 0:
                await channel.send('`no output`')
                return

        # Simple "arrow table" layout
        row_count = len(max(values, key=len))
        rows = [''] * row_count
        for c in range(len(values)):
            col = values[c]
            if len(col) == 0: continue
            colWidth = len(max(col, key=len))
            for r in range(row_count):
                if r < len(col):
                    rows[r] += col[r] + ' ' * (colWidth - len(col[r]))
                else:
                    rows[r] += ' ' * colWidth
                try:
                    values[c+1][r]
                    rows[r] += ' → '
                except:
                    rows[r] += '   '

        # Remove unnecessary padding at line ends
        rows = [row.rstrip() for row in rows]
        for block in texttools.block_chunk_lines(rows):
            await channel.send(block)

    @staticmethod
    async def send_error_log(channel: TextChannel, errors: ErrorLog, name: str):
        try:
            await channel.send(embed=errors.embed(name=name))
        except:
            newErrors = ErrorLog()
            newErrors.terminal = errors.terminal
            newErrors.log(
                f'🙈 {"Error" if errors.terminal else "Warning"} log too big to reasonably display...'
                '\nDoes your script perhaps contain an infinite recursion?'
            )
            await channel.send(embed=newErrors.embed(name=name))

    @classmethod
    async def execute_script(cls, script: str, bot: Client, message: Message, context=None, name=None):
        pipeline_wo = PipelineWithOrigin.from_string(script)
        return await cls.execute_pipeline_with_origin(pipeline_wo, bot, message, context=context, name=name)

    @classmethod
    async def execute_pipeline_with_origin(cls, pipeline_wo: PipelineWithOrigin, bot: Client, message: Message, context=None, name=None):
        # TODO: Pull this into PipelineWithOrigin, obviously
        errors = ErrorLog()
        pipeline, origin = pipeline_wo.pipeline, pipeline_wo.origin

        try:
            ### STEP 1: GET STARTING VALUES
            values, origin_errors = await TemplatedString.evaluate_origin(origin, message, context)
            errors.extend(origin_errors, 'script origin')
            if errors.terminal: raise TerminalError()

            ### STEP 2: APPLY PIPELINE TO STARTING VALUES
            values, printValues, pl_errors, spout_callbacks = await pipeline.apply(values, message, context)
            errors.extend(pl_errors)
            if errors.terminal: raise TerminalError()

            ### STEP 3: JOB'S DONE, PERFORM SIDE-EFFECTS!

            ## Put the thing there
            SourceResources.previous_pipeline_output[message.channel] = values

            ## Print the output!
            # TODO: auto-print if the last pipe was not a spout, or something
            if not spout_callbacks or any( callback is spouts['print'].spout_function for (callback, _, _) in spout_callbacks ):
                printValues.append(values)
                await cls.send_print_values(message.channel, printValues)

            ## Perform all Spouts (TODO: MAKE THIS BETTER)
            for callback, args, values in spout_callbacks:
                try:
                    await callback(bot, message, values, **args)
                except Exception as e:
                    errors(f'Failed to execute spout `{callback.__name__}`:\n\t{type(e).__name__}: {e}', True)
                    break

            ## Post warning output to the channel if any
            if errors:
                await cls.send_error_log(message.channel, errors, name)

        except TerminalError:
            ## A TerminalError indicates that whatever problem we encountered was caught, logged, and we halted voluntarily.
            # Nothing more to be done than posting log contents to the channel.
            print('Script execution halted due to error.')
            await cls.send_error_log(message.channel, errors, name)
            
        except Exception as e:
            ## An actual error has occurred in executing the script that we did not catch.
            # No script, no matter how poorly formed or thought-out, should be able to trigger this; if this occurs it's a Rezbot bug.
            print('Script execution halted unexpectedly!')
            errors.log(f'🛑 **Unexpected pipeline error:**\n {type(e).__name__}: {e}', terminal=True)
            await cls.send_error_log(message.channel, errors, name)
            raise e

    async def process_script(self, message: Message):
        '''This is the starting point for all script execution.'''
        text = message.content

        # Test for the script prefix and remove it (pipe_prefix in config.ini, default: '>>')
        if not text.startswith(self.prefix):
            return False
        script = text[len(self.prefix):]

        ## Check if it's a script or some kind of script-like command
        if re.match(r'\s*(NEW|EDIT|DESC).*::', script, re.I):
            ##### MACRO DEFINITION:
            # >> (NEW|EDIT|DESC) <type> <name> :: <code>
            if await parse_macro_command(self.bot, script, message):
                pass
            ##### EVENT DEFINITION:
            # >> (NEW|EDIT) EVENT <name> ON MESSAGE <regex> :: <code>
            elif await events.parse_command(script, message.channel):
                pass
            ##### ERROR:
            # Our script clearly resembles a script-like command but isn't one!
            else:
                await message.channel.send('Error: Poorly formed command.')

        ##### NORMAL SCRIPT EXECUTION:
        else:
            async with message.channel.typing():
                await self.execute_script(script, self.bot, message)

        return True


# These lynes be down here dve to dependencyes cyrcvlaire
from .pipeline import Pipeline
from .implementations.spouts import spouts
from .implementations.sources import SourceResources
from .events import events, OnMessage, OnReaction
from .context import Context
from .templatedstring import TemplatedString
from .commands.macro_commands import parse_macro_command