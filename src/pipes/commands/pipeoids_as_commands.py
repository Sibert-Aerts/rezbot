from discord.ext import commands

from pipes.core.executable_script import ExecutableScript
from pipes.core.pipe import Pipe, Source, Spout
from pipes.core.context import Context
from pipes.implementations.pipes import NATIVE_PIPES
from pipes.implementations.sources import NATIVE_SOURCES
from pipes.implementations.spouts import NATIVE_SPOUTS


# Load the bot cog
async def setup(bot: commands.Bot):
    # This part is icky but basically, take the pipes/sources/spouts from this library and
    # shoe-horn them into Discord.py's command module thingamajig
    # This may break some kind of weird use case for command modules but I don't care...
    #
    # But by doing this we get that discord.py does the command parsing for us,
    # and the commands show up in the "help" menu automatically, and behave nicely like
    # regular discord commands. Cool!

    ###############################################################
    #                  Turn pipes into commands!                  #
    ###############################################################

    def pipe_to_func(pipe: Pipe):
        async def func(ctx: commands.Context, *, text: str=''):
            script_context = Context(
                origin=Context.Origin(
                    name=pipe.name,
                    type=Context.Origin.Type.COMMAND,
                    activator=ctx.author,
                ),
                author=ctx.author,
                message=ctx.message,
            )
            # Parse and process arguments from the command string
            args, text, err = await pipe.signature.parse_and_determine(text, script_context, greedy=False)
            err.name = f'`{pipe.name}`'
            if err:
                await ctx.send(embed=err.embed())
                if err.terminal: return

            if not pipe.may_use(ctx.author):
                err.log(f'User lacks permission to use Pipe `{pipe.name}`.', True)
                return await ctx.send(embed=err.embed())

            try:
                # Apply the pipe to what remains of the command string
                results = await pipe.apply([text], **args)
                await ExecutableScript.send_print_values(ctx.channel, [results])

            except Exception as e:
                err.log(f'With args {args}:\n\t{type(e).__name__}: {e}', True)
                await ctx.send(embed=err.embed())

        func.__name__ = pipe.name
        func.__doc__ = pipe.get_command_doc()
        return func

    # Turn those pipes into discord.py bot commands!
    for pipe in NATIVE_PIPES.commands:
        func = pipe_to_func(pipe)
        # manually call the function decorator to make func into a command
        command = commands.command()(func)
        bot.add_command(command)

    ###############################################################
    #                 Turn sources into commands!                 #
    ###############################################################

    def source_to_func(source: Source):
        async def func(ctx: commands.Context, *, text: str=''):
            script_context = Context(
                origin=Context.Origin(
                    name=source.name,
                    type=Context.Origin.Type.COMMAND,
                    activator=ctx.author,
                ),
                author=ctx.author,
                message=ctx.message,
            )
            # Parse and process arguments from the command string
            args, _, err = await source.signature.parse_and_determine(text, script_context, greedy=True)
            err.name = f'`{source.name}`'
            if err:
                await ctx.send(embed=err.embed())
                if err.terminal: return

            if not source.may_use(ctx.author):
                err.log(f'User lacks permission to use Source `{source.name}`.', True)
                return await ctx.send(embed=err.embed())

            try:
                # Apply the source with the given arguments
                results = await source.generate(script_context, args)
                await ExecutableScript.send_print_values(ctx.channel, [results])

            except Exception as e:
                err.log(f'With args {args}:\n\t{type(e).__name__}: {e}', True)
                await ctx.send(embed=err.embed())

        func.__name__ = source.name
        func.__doc__ = source.get_command_doc()
        return func

    # Turn those sources into discord.py bot commands!
    for source in NATIVE_SOURCES.commands:
        func = source_to_func(source)
        # manually call the function decorator to make func into a command
        command = commands.command()(func)
        bot.add_command(command)

    ###############################################################
    #                  Turn spouts into commands!                 #
    ###############################################################

    def spout_to_func(spout: Spout):
        async def func(ctx: commands.Context, *, text: str=''):
            script_context = Context(
                origin=Context.Origin(
                    name=spout.name,
                    type=Context.Origin.Type.COMMAND,
                    activator=ctx.author,
                ),
                author=ctx.author,
                message=ctx.message,
            )
            # Parse and process arguments from the command string
            args, text, err = await spout.signature.parse_and_determine(text, script_context, greedy=False)
            err.name = f'`{spout.name}`'
            if err:
                await ctx.send(embed=err.embed())
                if err.terminal: return

            if not spout.may_use(ctx.author):
                err.log(f'User lacks permission to use Spout `{spout.name}`.', True)
                return await ctx.send(embed=err.embed())

            try:
                # Execute the spout with what remains of the argstr
                await spout.do_simple_callback(ctx.bot, script_context, [text], **args)

            except Exception as e:
                err.log(f'With args {args}:\n\t{type(e).__name__}: {e}', True)
                await ctx.send(embed=err.embed())

        func.__name__ = spout.name
        func.__doc__ = spout.get_command_doc()
        return func

    # Turn those spouts into discord.py bot commands!
    for spout in NATIVE_SPOUTS.commands:
        func = spout_to_func(spout)
        # manually call the function decorator to make func into a command
        command = commands.command()(func)
        bot.add_command(command)
