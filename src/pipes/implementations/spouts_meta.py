from .spouts import spout_from_func, set_category, Par, Context
from pipes.core.events import events
from pipes.core.context import ContextError


#####################################################
#                   Spouts : META                   #
#####################################################
set_category('META')

@spout_from_func({
    'name': Par(str, None, 'The name of the event to be disabled, empty to disable the triggering event.', required=False)
})
async def disable_event_spout(ctx: Context, values, *, name):
    ''' Disables the specified event, or the current script's triggering event. '''
    if not name:
        event = ctx.origin.event
        if not event:
            raise ContextError('Current script was not triggered by an Event.')
    else:
        if name not in events:
            raise ValueError(f'Event "{name}" does not exist!')
        event = events[name]
    if ctx.channel.id in event.channels:
        event.channels.remove(ctx.channel.id)