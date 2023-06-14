from .spouts import Par, Context, spout_from_func, set_category
from pipes.signature import parse_bool
from resource.upload import uploads

from .sources import SourceResources


#####################################################
#                   Spouts : STATE                  #
#####################################################
set_category('STATE')

@spout_from_func({
    'name' :   Par(str, None, 'The variable name'),
    'persist': Par(parse_bool, False, 'Whether the variable should persist indefinitely.')
}, command=True)
async def set_spout(bot, ctx, values, name, persist):
    '''
    Stores the input as a variable with the given name.
    Variables can be retrieved via the `get` Source.
    If `persist`=True, variables will never disappear until manually deleted by the `delete_var` Spout.
    '''
    SourceResources.variables.set(name, values, persistent=persist)


@spout_from_func({
    'name' :  Par(str, None, 'The variable name'),
    'strict': Par(parse_bool, False, 'Whether an error should be raised if the variable does not exist.')
}, command=True)
async def delete_var_spout(bot, ctx, values, name, strict):
    ''' Deletes the variable with the given name. '''
    try:
        SourceResources.variables.delete(name)
    except:
        if strict:
            raise KeyError(f'No variable "{name}" found.')


@spout_from_func({
    'name' : Par(str, None, 'The new file\'s name'),
    'sequential': Par(parse_bool, True, 'Whether the order of entries matters when retrieving them from the file later.'),
    'sentences': Par(parse_bool, False, 'Whether the entries should be split based on sentence recognition instead of a splitter regex.'),
    'editable': Par(parse_bool, False, 'Whether the file should be able to be modified at a later time.'),
    'categories': Par(str, '', 'Comma-separated, case insensitive list of categories the file should be filed under.')
})
async def new_file_spout(bot, ctx: Context, values, name, sequential, sentences, editable, categories):
    '''Writes the input to a new txt file.'''
    # Files are stored as raw txt's, but we want to make sure our list of strings remain distinguishable.
    # So we join the list of strings by a joiner that we determine for sure is NOT a substring of any of the strings,
    # so that if we split on the joiner later we get the original list of strings.
    if not sentences:
        joiner = '\n'
        while any(joiner in value for value in values):
            joiner += '&'
        if len(joiner) > 1: joiner += '\n'
    else:
        joiner = '\n'

    uploads.add_file(name, joiner.join(values), ctx.activator.display_name, ctx.activator.id,
        editable=editable, splitter=joiner, sequential=sequential, sentences=sentences, categories=categories)
