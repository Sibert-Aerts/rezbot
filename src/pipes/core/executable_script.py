from discord import TextChannel
from pyparsing import ParseResults

# More import statements at the bottom of the file, due to circular dependencies.
from .state.logger import ErrorLog
from .groupmodes import GroupMode
from .state.context import Context, ItemScope
from .state.spout_state import SpoutState
import utils.texttools as texttools


class TerminalError(Exception):
    '''Special error that serves as a signal to end script execution but contains no information.'''


class ExecutableScript:
    '''
    Class representing a complete "Rezbot script" that may be executed.
    Functionally just a wrapper around a parsed Pipeline object with additional methods
        for performing side-effects, catching execution errors, etc.

    These occur from:
        * Manual script invocation (messages starting with >>)
        * Source Macros, Events
        * (Rarely) as arguments passed to Pipes in a Pipeline (meta-recursion?)
    '''

    # ======================================== Constructors ========================================

    def __init__(self, pipeline: 'Pipeline', *, script_str: str=None):
        self.pipeline = pipeline
        self.script_str = script_str

    @staticmethod
    def from_string(script: str) -> 'ExecutableScript':
        pipeline = Pipeline.from_string_with_origin(script)
        return ExecutableScript(pipeline, script_str=script)

    @staticmethod
    def from_parsed_simple_script(parsed: ParseResults) -> 'ExecutableScript':
        parsed_segments = []

        # Parse origin
        simple_origin_parsed = parsed['simple_origin']
        if 'quoted_simple_origin' in simple_origin_parsed:
            origin_tstr = TemplatedString.from_parsed(simple_origin_parsed['quoted_simple_origin'])
        else:
            origin_tstr = TemplatedString.from_parsed(simple_origin_parsed).strip()
        parsed_segments.append(ParsedOrigin([origin_tstr]))

        # Parse pipe segments
        for simple_segment in parsed['simple_segments']:
            if 'simple_pipe' in simple_segment:
                simple_pipe_parsed = simple_segment['simple_pipe']
                groupmode = GroupMode.from_parsed(simple_pipe_parsed['groupmode'])
                parsed_pipe = ParsedPipe.from_parsed(simple_pipe_parsed)
                parsed_segments.append((groupmode, (parsed_pipe,)))
            elif 'simple_origin' in simple_segment:
                simple_origin_parsed = simple_segment['simple_origin']
                if 'quoted_simple_origin' in simple_origin_parsed:
                    origin_tstr = TemplatedString.from_parsed(simple_origin_parsed['quoted_simple_origin'])
                else:
                    origin_tstr = TemplatedString.from_parsed(simple_origin_parsed).strip()
                parsed_segments.append(ParsedOrigin([origin_tstr]))
            elif 'nop' in simple_segment:
                continue
            else:
                raise Exception()

        return ExecutableScript(Pipeline(parsed_segments))

    # =================================== Static utility methods ===================================

    @staticmethod
    async def send_print_values(channel: TextChannel, values: list[list[str]], context: Context=None):
        ''' Nicely print the output in rows and columns and even with little arrows.'''

        # Mince out a special case for sending the message:
        #   Respond to the original Interaction if it would otherwise go unresponded.
        def send(text):
            if context and context.interaction and not context.interaction.response.is_done():
                return context.interaction.response.send_message(text)
            return channel.send(text)

        # Don't apply any formatting if the output is just a single cel.
        if len(values) == 1:
            if len(values[0]) == 1:
                if values[0][0].strip() != '':
                    for chunk in texttools.chunk_text(values[0][0]):
                        await send(chunk)
                else:
                    await send('`empty string`')
                return
            elif len(values[0]) == 0:
                await send('`no output`')
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
            await send(block)

    @staticmethod
    async def send_error_log(context: Context, errors: ErrorLog):
        try:
            await context.channel.send(embed=errors.embed(name=context.origin.name))
        except:
            new_errors = ErrorLog()
            new_errors.terminal = errors.terminal
            new_errors.log(
                f'🙈 {"Error" if errors.terminal else "Warning"} log too big to reasonably display...'
                '\nDoes your script perhaps contain an infinite recursion?'
            )
            await context.channel.send(embed=new_errors.embed(name=context.origin.name))

    # ======================================= Representation =======================================

    def get_static_errors(self) -> ErrorLog:
        '''
        Collects errors that can be known before execution time.
        '''
        return self.pipeline.get_static_errors()

    def __repr__(self):
        return 'ExecutableScript(%s)' % repr(self.pipeline)
    def __str__(self):
        return '>> ' + str(self.pipeline)

    # ========================================= Application ========================================

    async def execute(self, context: 'Context', scope: 'ItemScope'=None):
        '''
        This function connects the three major steps of executing a script:
            * Executing the pipeline
            * Performing side effects

        All while handling and communicating any errors that may arise during that process.
        '''
        errors = ErrorLog()

        try:
            ## Execute the pipeline
            values, exec_errors, spout_state = await self.execute_without_side_effects(context, scope)
            errors.extend(exec_errors)
            if errors.terminal: raise TerminalError()

            ## Perform the side-effects
            side_errors = await self.perform_side_effects(context, spout_state, values)
            errors.extend(side_errors)
            if errors.terminal: raise TerminalError()

            ## Post warning output, if any
            if errors:
                await self.send_error_log(context, errors)

        except TerminalError:
            ## A TerminalError indicates that whatever problem we encountered was caught, logged, and we halted voluntarily.
            # Nothing more to be done than posting log contents to the channel.
            print('Script execution halted due to error.')
            await self.send_error_log(context, errors)

        except Exception as e:
            ## An actual error has occurred in executing the script that we did not catch.
            # No script, no matter how poorly formed or thought-out, should be able to trigger this; if this occurs it's a Rezbot bug.
            print('Script execution halted unexpectedly!')
            errors.log(f'🛑 **Unexpected pipeline error:**\n {type(e).__name__}: {e}', terminal=True)
            await self.send_error_log(context, errors)
            raise e

    async def execute_without_side_effects(self, context: 'Context', scope: 'ItemScope'=None) -> tuple[ list[str], ErrorLog, SpoutState ]:
        '''
        Performs the ExecutableScript purely functionally, with its side-effects and final values to be handled by the caller.
        '''
        initial_values = scope.items if scope is not None else ()
        return await self.pipeline.apply(initial_values, context, scope)

    async def perform_side_effects(self, context: 'Context', spout_state: SpoutState, end_values: list[str]) -> ErrorLog:
            '''
            This function performs the side-effects of executing a script:
                * Storing the output values somewhere
                * Making sure all encountered Spouts' effects happen
            '''
            errors = ErrorLog()

            ## Put the thing there
            if context.origin.type == Context.Origin.Type.DIRECT:
                SourceResources.previous_pipeline_output[context.channel] = end_values

            ## Perform all simple style Spout callbacks
            for spout, values, args in spout_state.callbacks:
                try:
                    await spout.spout_function(context, values, **args)
                except Exception as e:
                    errors.log(f'Failed to execute spout `{spout.name}`:\n\t{type(e).__name__}: {e}', True)
                    return errors

            ## Perform all aggregated-style Spout callbacks
            for spout in spout_state.aggregated_spouts:
                try:
                    await spout.spout_function(context, spout_state.aggregated[spout.name])
                except Exception as e:
                    errors.log(f'Failed to execute spout `{spout.name}`:\n\t{type(e).__name__}: {e}', True)
                    return errors

            ## Perform `print` if either: No other spout has been encountered all script OR if a print spout has been explicitly encountered.
            # Happens after other spouts have resolved because this involves looking at the .interaction and seeing if it's been responded to yet.
            # TODO: This isn't perfect yet
            if not spout_state.anything() or any(spout is NATIVE_SPOUTS['print'] for spout, _, _ in spout_state.callbacks):
                spout_state.print_values.append(end_values)
                await self.send_print_values(context.channel, spout_state.print_values, context=context)

            return errors


# These lynes be down here dve to dependencyes cyrcvlaire
from .pipeline import ParsedOrigin, ParsedPipe, Pipeline
from .templated_string.templated_string import TemplatedString
from pipes.implementations.spouts import NATIVE_SPOUTS
from pipes.implementations.sources import SourceResources