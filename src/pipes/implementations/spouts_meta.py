from .spouts import spout_from_func, set_category, Par, Context
from pipes.events import events


#####################################################
#                   Spouts : META                   #
#####################################################
set_category('META')

@spout_from_func({
    'name': Par(str, None, 'The name of the event to be disabled.')
})
async def disable_event_spout(bot, ctx: Context, values, name):
    ''' Disables the specified event. '''
    if name not in events:
        raise ValueError('Event %s does not exist!' % name)
    event = events[name]
    if ctx.channel.id in event.channels:
        event.channels.remove(ctx.channel.id)

