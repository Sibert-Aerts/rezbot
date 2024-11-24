import sys
from typing import TYPE_CHECKING, Callable

from discord.ext import commands

from pipes.core.state.context import Context
from pipes.core.signature import Signature, Par

if TYPE_CHECKING:
    import bot as rezbot


def command_with_signature(arg=None, **kwargs: dict[str, Par]):
    '''
    Makes a discord.py command work with a Rezbot scripting signature.
    '''
    if arg and kwargs:
        raise ValueError('command_with_signature should either specify one arg, or a set of kwargs, not both.')
    signature = arg if isinstance(arg, Signature) else Signature(arg or kwargs)

    def _command_with_signature(f: Callable):
        async def _f(self: commands.Bot, ctx: commands.Context, *, argstr=''):
            # Parse and determine the entire argstring according to the given Signature
            script_ctx = Context(
                origin=Context.Origin(
                    name=ctx.command.name,
                    type=Context.Origin.Type.COMMAND,
                    activator=ctx.author,
                ),
                author=ctx.author,
                message=ctx.message,
            )
            args, _, errs = await signature.parse_and_determine(argstr, script_ctx)
            errs.name = f'`{ctx.command.name}`'
            if errs:
                await ctx.send(embed=errs.embed())
            if errs.terminal:
                return

            # Invoke f() with the newly parsed args
            return await f(self, ctx, **args)

        # Extend docstring
        signature_doc = ''
        if signature:
            signature_doc = '\nParameters:\n'
            signature_doc += '\n'.join(f'• {s.simple_str()}' for s in signature.values())

        # Discord.py does too much introspection so we can't actually use functools.wraps,
        #   but it does want these fields to carry over to the wrapper function.
        _f.__module__ = f.__module__
        _f.__name__ = f.__name__
        _f.__qualname__ = f.__qualname__
        _f.__doc__ = (f.__doc__ + '\n' if f.__doc__ else '') + signature_doc

        return _f

    return _command_with_signature


class RezbotCommands(commands.Cog):
    '''Class holding useful methods for bot commands.'''
    bot: 'rezbot.Rezbot'

    def __init__(self, bot):
        self.bot = bot

    async def _die(self):
        '''Kill the bot.'''
        await self.bot.close()
        print('Bot killed.')
        sys.exit()