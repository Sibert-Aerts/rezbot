from lru import LRU
from discord import Client, TextChannel

# More import statements at the bottom of the file, due to circular dependencies.
from .logger import ErrorLog
from .context import Context, ItemScope
from .spout_state import SpoutState
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
    script_cache: dict[str, 'PipelineWithOrigin'] = LRU(40)

    # ======================================== Constructors ========================================

    def __init__(self, origin_str: str, pipeline: 'Pipeline', script_str: str=None):
        # NOTE: origin is saved as a string instead of something more advanced and pre-parsed
        #   because the [?] flag on the ChoiceTree means it may not represent the same TemplatedStrings each time
        self.origin = origin_str
        self.pipeline = pipeline
        self.script_str = script_str

    @classmethod
    def from_string(cls, script: str) -> 'PipelineWithOrigin':
        ## No need to re-parse the same script
        if script in cls.script_cache:
            return cls.script_cache[script]

        ## Parse
        origin_str, pipeline_str = cls.split(script)
        pipeline = Pipeline(pipeline_str)

        ## Instantiate, cache, return
        pwo = PipelineWithOrigin(origin_str, pipeline, script)
        cls.script_cache[script] = pwo
        return pwo

    # =================================== Static utility methods ===================================

    def __repr__(self):
        if self.script_str:
            script = self.script_str
            script = script if len(script) < 50 else script[:47] + '...'
            return f'RezbotScript({script})'
        return f'RezbotScript(id={id(self)})'

    @staticmethod
    def split(script: str) -> tuple[str, str]:
        '''Splits a script into the origin and pipeline.'''
        # So here's the deal:
        #    ORIGIN > PIPE > PIPE > PIPE > ETC...
        # We only need to split on the first >, but this can be escaped by wrapping the entire thing in quotes!
        #    "ORI > GIN" > PIPE
        # We want to split on the LAST pipe there... The issue is parsing this is kinda hard maybe, because of weird cases:
        #    ORI ">" GIN    or    "ORI">"GIN" ???
        # AND also: ORIGIN -> PIPE should parse as ORIGIN > print > PIPE
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

    # =================================== Static analysis methods ==================================

    def get_static_errors(self):
        '''Gather static errors from both Origin and Pipeline.'''
        errors = ErrorLog()
        # 1. Origin errors
        origins, origin_errors = TemplatedString.parse_origin(self.origin)
        errors.extend(origin_errors, 'script origin')
        # 2. Pipeline errors
        errors.extend(self.pipeline.parser_errors)
        return errors

    # ====================================== Execution method ======================================

    async def execute(self, context: 'Context', scope: 'ItemScope'=None):
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
            values, origin_errors = await TemplatedString.evaluate_origin(origin, context, scope)
            errors.extend(origin_errors, 'script origin')
            if errors.terminal: raise TerminalError()

            ### STEP 2: APPLY PIPELINE TO STARTING VALUES
            values, pl_errors, spout_state = await pipeline.apply(values, context, scope)
            errors.extend(pl_errors)
            if errors.terminal: raise TerminalError()

            ### STEP 3: JOB'S DONE, PERFORM SIDE-EFFECTS!
            side_errors = await self.perform_side_effects(context, spout_state, values)
            errors.extend(side_errors)

            ## Post warning output to the channel if any
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

    async def perform_side_effects(self, context: 'Context', spout_state: SpoutState, end_values) -> ErrorLog:
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
            if not spout_state.anything() or any(spout is spouts['print'] for spout, _, _ in spout_state.callbacks):
                spout_state.print_values.append(end_values)
                await self.send_print_values(context.channel, spout_state.print_values, context=context)

            return errors


# These lynes be down here dve to dependencyes cyrcvlaire
from .pipeline import Pipeline
from .templated_string import TemplatedString
from pipes.implementations.spouts import spouts
from pipes.implementations.sources import SourceResources