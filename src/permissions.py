from configparser import ConfigParser
from discord.ext import commands

# Rank objects:
owner = object()
'RANK: People designated as the bot\'s owner, are allowed everything.'
trusted = object()
'RANK: People designated as trusted, are allowed more things than regular users, but not everything.'
default = object()
'RANK: Regular users, certain features are restricted from them.'
muted = object()
'RANK: Muted users, bot is generally supposed to ignore these.'

hierarchy = [muted, default, trusted, owner]
mapping = {
    'owner': owner,
    'default': default,
    'trusted': trusted,
    'muted': muted,
}

user_permissions: dict[int] = {}
'Dict mapping user IDs to their rank.'

# ============================= Read out user permissions from config =============================

config = ConfigParser()
config.read('permissions.ini')
for rank in config:
    for user in config[rank]:
        user_permissions[int(config[rank][user])] = mapping[rank.lower()]


def get(user_id):
    '''Get the user's permission level, or the default permission level if the user is not found.'''
    return user_permissions.get(user_id, default)

def has(user_id, permission):
    '''Checks if the user has at least the specified permission'''
    return hierarchy.index(get(user_id)) >= hierarchy.index(permission)

def set(user_id: int, rank: str, user_name: str=None):
    '''Sets the user's permission level and stores it in permissions.ini.'''
    # Sanitize input values
    if rank not in mapping:
        raise ValueError(f'Invalid rank "{rank}"')
    if rank == 'owner':
        raise ValueError(f'Cannot assign owner this way.')
    if not isinstance(user_id, int):
        raise ValueError(f'user_id must be int, got {repr(user_id)}')

    # Unset any existing rank assignments for this user
    for rank_iter in list(config):
        for user_iter in list(config[rank_iter]):
            if str(user_id) in config[rank_iter][user_iter] == str(user_id):
                if rank_iter.lower() == 'owner':
                    raise ValueError('Cannot reassign an owner\'s rank this way.')
                del config[rank_iter][user_iter]

    # Create a rank assignment for this user
    config[rank.upper()][str(user_name or user_id)] = str(user_id)
    # Update the actual user permissions index that we use at runtime
    user_permissions[user_id] = mapping[rank.lower()]

    # Write config back to file
    with open('permissions.ini', 'w') as file:
        config.write(file)


# key function, checks if the user has at most the specified permission.
# The same as doing !has(id, permission + 1) except permissions are strings and not ints (or enums),
# so you can't actually do that unless you know what the +1 permission is (which is adding magic numbers!!!).
def has_at_most(user_id, permission):
    '''Checks if the user has at most the specified permission'''
    return hierarchy.index(get(user_id)) <= hierarchy.index(permission)


def check(permission):
    '''Decorator for bot commands to check if the user has the specified permission.'''
    def _check(ctx):
        if has(ctx.author.id, permission):
            return True
        else:
            print('User {} attempted action that required permission {} but had {}'.format(ctx.author.name, permission, get(ctx.author.id)))
            return False
    return commands.check(_check)


def is_muted(user_id):
    '''Check if the user is muted'''
    return has_at_most(user_id, muted)