from .sources import source_from_func, set_category, SourceResources
from ..signature import Par


#####################################################
#                   Sources : BOT                   #
#####################################################
set_category('BOT')

@source_from_func(pass_message=True)
async def output_source(message):
    '''The entire set of output from the previous script that ran.'''
    return SourceResources.previous_pipeline_output[message.channel]


@source_from_func({
    'name'    : Par(str, None, 'The variable name'),
    'default' : Par(str, None, 'The default value in case the variable isn\'t assigned (None to throw an error if it isn\'t assigned)', required=False)
}, command=True)
async def get_source(name, default):
    '''Loads variables stored using the "set" pipe'''
    return SourceResources.variables.get(name, None if default is None else [default])

