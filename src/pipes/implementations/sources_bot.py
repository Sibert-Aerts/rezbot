from .sources import make_source, set_category, SourceResources
from ..signature import Par


#####################################################
#                   Sources : BOT                   #
#####################################################
set_category('BOT')

@make_source({}, pass_message=True)
async def output_source(message):
    '''The entire set of output from the previous script that ran.'''
    return SourceResources.previous_pipeline_output[message.channel]


@make_source({
    'name'    : Par(str, None, 'The variable name'),
    'default' : Par(str, None, 'The default value in case the variable isn\'t assigned (None to throw an error if it isn\'t assigned)', required=False)
}, command=True)
async def get_source(name, default):
    '''Loads variables stored using the "set" pipe'''
    return SourceResources.variables.get(name, None if default is None else [default])

