from configparser import ConfigParser
from discord.ext import commands

# Rank objects:
owner = object()
"RANK: People designated as the bot's owner, are allowed everything."
trusted = object()
"RANK: People designated as trusted, are allowed more things than regular users, but not everything."
default = object()
"RANK: Regular users, certain features are restricted from them."
muted = object()
"RANK: Muted users, bot is generally supposed to ignore these."

hierarchy = [muted, default, trusted, owner]
mapping = {
    'owner': owner,
    'default': default,
    'trusted': trusted,
    'muted': muted,
}

user_permissions = {}
"Dict mapping user IDs to their rank."

# ============================= Read out user permissions from config =============================

config = ConfigParser()
config.read('permissions.ini')

for rank in config:
    for user in config[rank]:
        user_permissions[int(config[rank][user])] = mapping[rank.lower()]


# Get the user's permission level, or the default permission level if the user is not found.
def get(user_id):
    return user_permissions.get(user_id, default)


# key function, checks if the user has at least the specified permission
def has(user_id, permission):
    return hierarchy.index(get(user_id)) >= hierarchy.index(permission)


# key function, checks if the user has at most the specified permission.
# The same as doing !has(id, permission + 1) except permissions are strings and not ints (or enums),
# so you can't actually do that unless you know what the +1 permission is (which is adding magic numbers!!!).
def has_at_most(id, permission):
    return hierarchy.index(get(id)) <= hierarchy.index(permission)


def check(permission):
    '''Decorator for bot commands to check if the user has the specified permission.'''
    def _check(ctx):
        if has(ctx.author.id, permission):
            return True
        else:
            print('User {} attempted action that required permission {} but had {}'.format(ctx.author.name, permission, get(ctx.author.id)))
            return False
    return commands.check(_check)


def is_muted(id):
    return has_at_most(id, muted)