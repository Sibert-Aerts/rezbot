from .sources import source_from_func, source_from_class, set_category, SourceResources, Context
from ..signature import Par, with_signature


#####################################################
#                   Sources : BOT                   #
#####################################################
set_category('BOT')

@source_from_func
async def output_source(ctx: Context):
    '''The entire set of output from the previous script that ran.'''
    return SourceResources.previous_pipeline_output[ctx.message.channel]


@source_from_class
class SourceGet:
    name = 'get'
    command = True

    @with_signature(
        name    = Par(str, None, 'The variable name'),
        default = Par(str, None, 'The default value in case the variable isn\'t assigned (None to throw an error if it isn\'t assigned)', required=False)
    )
    @staticmethod
    async def source_function(ctx, *, name, default):
        '''Loads variables stored using the "set" pipe'''
        return SourceResources.variables.get(name, None if default is None else [default])
