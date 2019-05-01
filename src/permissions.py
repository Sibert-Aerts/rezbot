from functools import wraps

import discord
from discord.ext import commands

# Allowed permission values:
# I prefer having these as variables instead of strings
# I think this is the python approach to enums anyway
owner = object()
default = object()
muted = object()

hierarchy = [muted, default, owner]

# hard coded lol
# need to change this to an ini file someday
# and maybe add commands to change them
# PUT YOUR CUSTOM USER PERMISSIONS HERE:
userPermissions = {
    154597714619793408: owner,   # Rezuaq
    147011940558831616: default, # Goat (note: default entries aren't needed)
    155029762404777984: muted,   # Ellen
}

# Get the user's permission level, or the default permission level if the user is not found.
def get(id):
    try:
        return userPermissions[id]
    except KeyError:
        return default


# key function, checks if the user has at least the specified permission
def has(id, permission):
    return hierarchy.index(get(id)) >= hierarchy.index(permission)


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