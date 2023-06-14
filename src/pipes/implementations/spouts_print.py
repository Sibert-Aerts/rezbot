from .spouts import set_category, spout_from_func


#####################################################
#                  Spouts : SPECIAL                 #
#####################################################
set_category('PRINT')


@spout_from_func
async def print_spout(bot, ctx, values):
    ''' Appends the values to the output message. (WIP: /any/ other spout suppresses print output right now!) '''
    # The actual implementation of "print" is hardcoded into the pipeline processor code
    # This definition is just here so it shows up in the list of spouts
    pass


@spout_from_func
async def suppress_print_spout(bot, ctx, values):
    '''
    (WIP) Prevents the default behaviour of printing output to a Discord message.
    Useful for Event scripts that silently modify variables, or that don't do anything in certain circumstances.
    '''
    # NOP, just having *any* spout is enough to prevent the default "print" behaviour
    pass