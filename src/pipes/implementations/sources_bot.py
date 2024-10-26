from .sources import source_from_func, source_from_class, set_category, SourceResources, Context
from pipes.core.context import ContextError
from pipes.core.signature import Par, with_signature, parse_bool


#####################################################
#                   Sources : BOT                   #
#####################################################
set_category('BOT')

@source_from_func
async def output_source(ctx: Context):
    '''The full output from the previous script that was ran in this channel.'''
    return SourceResources.previous_pipeline_output[ctx.channel]


@source_from_class
class SourceGet:
    '''Loads variables stored using the `set` spout.'''
    name = 'get'
    command = True

    @with_signature(
        name    = Par(str, None, 'The variable name'),
        default = Par(str, None, 'The default value in case the variable isn\'t assigned (None to throw an error if it isn\'t assigned)', required=False),
        required = Par(parse_bool, True, 'If False, when the name is not found and no default is given, '
            'will produce an empty list of items instead of raising an error.'),
    )
    @staticmethod
    async def source_function(ctx: Context, *, name, default, required):
        default = [default] if default is not None else [] if not required else None
        return SourceResources.variables.get(name, default)


@source_from_class
class SourceArg:
    '''
    A scripting argument in the context of a Macro or Event.

    In the context of a Macro:
    The available args are the ones that were assigned by the invoking script, or were configured with defaults on the Macro itself.

    In the context of an Event:
    OnMessage: The available args are the match groups of the regex;
    `{arg 0}` for the full match, `{arg 1}` for the first group, and so on, and named groups are available by name.
    OnReact: `{arg emoji}` is the emoji that was reacted with.
    '''
    name = 'arg'

    @with_signature(
        name    = Par(str, None, 'The parameter name'),
        default = Par(str, None, 'Default value to use in case the parameter was not given, raises an error otherwise.', required=False),
    )
    @staticmethod
    async def source_function(ctx: Context, *, name, default):
        if ctx.arguments is None:
            raise ContextError('No arguments exist in the current context.')

        value = ctx.arguments.get(name)
        if value is None: value = default

        if value is None:
            # Be descriptive with our error
            if ctx.macro:
                _ctx = f'call to Macro `{ctx.macro.name}`.'
            elif ctx.origin.event:
                _ctx = f'callback for Event `{ctx.origin.event.name}`.'
            else:
                _ctx = f'the current Context, arguments only make sense inside Macro or Event scripts.'
            raise ContextError(f'Argument `{name}` not found in {_ctx}')

        return [value]
