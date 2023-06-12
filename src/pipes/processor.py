
'''
The PipelineWithOrigin class essentially represents a Rezbot script that may be executed.
The PipelineProcessor class provides the primary interface through which Rezbot Scripts are executed.
'''

import re

from lru import LRU
from discord import Client, Message, TextChannel

# More import statements at the bottom of the file, due to circular dependencies.
from pipes.logger import ErrorLog
from pipes.context import Context
import utils.texttools as texttools


class TerminalError(Exception):
    '''Special error that serves as a signal to end script execution but contains no information.'''


class PipelineWithOrigin:
    '''
    Class representing a complete "Rezbot script" that may be executed:
        * An origin (str) which may be expanded and evaluated.
        * A Pipeline which may be applied to that result.

    These occur from:
        * Manual script invocation (messages starting with >>)
        * Source Macros, Events
        * (Rarely) as arguments passed to Pipes in a Pipeline (meta-recursion?)
    '''
    # Static LRU cache holding up to 40 parsed instances... probably don't need any more
    script_cache: dict['PipelineWithOrigin'] = LRU(40)

    # ======================================== Constructors ========================================

    def __init__(self, origin: str, pipeline: 'Pipeline'):
        self.origin = origin
        self.pipeline = pipeline

    @classmethod
    def from_string(cls, script: str) -> 'PipelineWithOrigin':
        ## No need to re-parse the same script
        if script in cls.script_cache:
            return cls.script_cache[script]

        ## Parse
        origin, pipeline_str = cls.split(script)
        pipeline = Pipeline(pipeline_str)

        ## Instantiate, cache, return
        pwo = PipelineWithOrigin(origin, pipeline)
        cls.script_cache[script] = pwo
        return pwo

    # =================================== Static utility methods ===================================

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

    # ====================================== Execution method ======================================

    async def execute(self, bot: Client, message: Message, context: Context=None, name: str=None):
        '''
        This function connects the three major steps of executing a script:
            * Evaluating the origin
            * Running the result through the pipeline
            * Performing any Spout callbacks

        All while handling and communicating any errors that may arise during that process.
        '''
        errors = ErrorLog()
        pipeline, origin = self.pipeline, self.origin

        try:
            ### STEP 1: GET STARTING VALUES
            values, origin_errors = await TemplatedString.evaluate_origin(origin, message, context)
            errors.extend(origin_errors, 'script origin')
            if errors.terminal: raise TerminalError()

            ### STEP 2: APPLY PIPELINE TO STARTING VALUES
            values, print_values, pl_errors, spout_callbacks = await pipeline.apply(values, message, context)
            errors.extend(pl_errors)
            if errors.terminal: raise TerminalError()

            ### STEP 3: JOB'S DONE, PERFORM SIDE-EFFECTS!
            await self.perform_side_effects(bot, context, spout_callbacks, print_values, values)

            ## Post warning output to the channel if any
            if errors:
                await self.send_error_log(message.channel, errors, name)

        except TerminalError:
            ## A TerminalError indicates that whatever problem we encountered was caught, logged, and we halted voluntarily.
            # Nothing more to be done than posting log contents to the channel.
            print('Script execution halted due to error.')
            await self.send_error_log(message.channel, errors, name)
            
        except Exception as e:
            ## An actual error has occurred in executing the script that we did not catch.
            # No script, no matter how poorly formed or thought-out, should be able to trigger this; if this occurs it's a Rezbot bug.
            print('Script execution halted unexpectedly!')
            errors.log(f'🛑 **Unexpected pipeline error:**\n {type(e).__name__}: {e}', terminal=True)
            await self.send_error_log(message.channel, errors, name)
            raise e

    async def perform_side_effects(self, bot: Client, context: Context, spout_callbacks, print_values, end_values) -> ErrorLog:
            '''
            This function performs the side-effects of executing a script:
                * Storing the output values somewhere
                * Making sure all encountered Spouts' effects happen
            '''
            errors = ErrorLog()

            ## Put the thing there
            SourceResources.previous_pipeline_output[context.message.channel] = end_values

            ## Print the output!
            # TODO: auto-print if the last pipe was not a spout, or something
            if not spout_callbacks or any( callback is spouts['print'].spout_function for (callback, _, _) in spout_callbacks ):
                print_values.append(end_values)
                await self.send_print_values(context.message.channel, print_values)

            ## Perform all Spouts (TODO: MAKE THIS BETTER)
            for callback, args, values in spout_callbacks:
                try:
                    await callback(bot, context, values, **args)
                except Exception as e:
                    errors(f'Failed to execute spout `{callback.__name__}`:\n\t{type(e).__name__}: {e}', True)
                    break

            return errors


class PipelineProcessor:
    ''' Singleton class providing some global config, methods and hooks to the Bot. '''

    def __init__(self, bot: Client, prefix: str):
        self.bot = bot
        self.prefix = prefix
        bot.pipeline_processor = self
        SourceResources.bot = bot

    # ========================================= Event hooks ========================================

    async def on_message(self, message: Message):
        '''Check if an incoming message triggers any custom Events.'''
        for event in events.values():
            if not isinstance(event, OnMessage): continue
            match = event.test(message)
            if match:
                # If m is not just a bool, but a regex match object, fill the context up with the match groups, otherwise with the entire message.
                if match is not True:
                    items = [group or '' for group in match.groups()] or [message.content]
                else:
                    items = [message.content]
                context = Context(
                    author=None, # TODO: Track Event.author idiot
                    activator=message.author,
                    message=message,
                    items=items,
                )
                await self.execute_script(event.script, message, context, name='Event: ' + event.name)

    async def on_reaction(self, channel: TextChannel, emoji: str, user_id: int, msg_id: int):
        '''Check if an incoming reaction triggers any custom Events.'''
        for event in events.values():
            if isinstance(event, OnReaction) and event.test(channel, emoji):
                message = await channel.fetch_message(msg_id)
                member = channel.guild.get_member(user_id)
                context = Context(
                    author=None, # TODO: Track Event.author idiot
                    activator=member,
                    message=message,
                    items=[emoji, str(user_id)], # Old way of conveying the reacting user
                )
                await self.execute_script(event.script, message, context, name='Event: ' + event.name)

    # ====================================== Script execution ======================================

    async def execute_script(self, script: str, message: Message, context: Context=None, name: str=None):
        pipeline_with_origin = PipelineWithOrigin.from_string(script)
        return await pipeline_with_origin.execute(self.bot, message, context=context, name=name)

    async def interpret_incoming_message(self, message: Message):
        '''Starting point for executiong scripts directly from a message, or for the 'script-like' Macro/Event definition syntax.'''

        # Test for the script prefix and remove it (pipe_prefix in config.ini, default: '>>')
        if not message.content.startswith(self.prefix):
            return False
        script = message.content[len(self.prefix):]

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
                await message.channel.send('Error: Poorly formed script-like command.')

        ##### NORMAL SCRIPT EXECUTION:
        else:
            async with message.channel.typing():
                context = Context(
                    author=message.author,
                    activator=message.author,
                    message=message,
                )
                await self.execute_script(script, message, context=context)

        return True


# These lynes be down here dve to dependencyes cyrcvlaire
from .pipeline import Pipeline
from .implementations.spouts import spouts
from .implementations.sources import SourceResources
from .events import events, OnMessage, OnReaction
from .templatedstring import TemplatedString
from .commands.macro_commands import parse_macro_command