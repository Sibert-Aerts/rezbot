from discord.ext import commands

import utils.util as util

from pipes.core.pipeline_with_origin import PipelineWithOrigin
from pipes.core.pipe import Pipe, Source, Spout
from pipes.core.context import Context
from pipes.core.signature import Arguments
from pipes.implementations.pipes import pipes
from pipes.implementations.sources import sources
from pipes.implementations.spouts import spouts


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
        async def func(ctx: commands.Context):
            text = util.strip_command(ctx)
            execution_context = Context(
                origin=Context.Origin(
                    name=pipe.name,
                    type=Context.Origin.Type.COMMAND,
                    activator=ctx.author,
                ),
                author=ctx.author,
                message=ctx.message,
            )
            # Parse and process arguments from the command string
            args, text, err = Arguments.from_string(text, pipe.signature, greedy=False)
            err.name = f'`{pipe.name}`'
            if err.terminal: return await ctx.send(embed=err.embed())
            args, err2 = await args.determine(execution_context)
            err.extend(err2, 'arguments'); 
            if text is not None:
                text, err3 = await text.evaluate(execution_context)
                err.extend(err3, 'input string')
            if err.terminal: return await ctx.send(embed=err.embed())

            if not pipe.may_use(ctx.author):
                err.log(f'User lacks permission to use Pipe `{pipe.name}`.', True)
                return await ctx.send(embed=err.embed())

            try:
                # Apply the pipe to what remains of the command string
                results = pipe.apply([text], **args)
                await PipelineWithOrigin.send_print_values(ctx.channel, [results])

            except Exception as e:
                err.log(f'With args {args}:\n\t{type(e).__name__}: {e}', True)
                await ctx.send(embed=err.embed())

        func.__name__ = pipe.name
        func.__doc__ = pipe.get_command_doc()
        return func

    # Turn those pipes into discord.py bot commands!
    for pipe in pipes.commands:
        func = pipe_to_func(pipe)
        # manually call the function decorator to make func into a command
        command = commands.command()(func)
        bot.add_command(command)

    ###############################################################
    #                 Turn sources into commands!                 #
    ###############################################################

    def source_to_func(source: Source):
        async def func(ctx: commands.Context):
            text = util.strip_command(ctx)            
            execution_context = Context(
                origin=Context.Origin(
                    name=source.name,
                    type=Context.Origin.Type.COMMAND,
                    activator=ctx.author,
                ),
                author=ctx.author,
                message=ctx.message,
            )
            # Parse and process arguments from the command string
            args, _, err = Arguments.from_string(text, source.signature, greedy=True)
            err.name = f'`{source.name}`'
            if err.terminal: return await ctx.send(embed=err.embed())
            args, err2 = await args.determine(execution_context)
            err.extend(err2, 'arguments')
            if err.terminal: return await ctx.send(embed=err.embed())

            if not source.may_use(ctx.author):
                err.log(f'User lacks permission to use Source `{source.name}`.', True)
                return await ctx.send(embed=err.embed())

            try:
                # Apply the source with the given arguments
                results = await source.generate(execution_context, args)
                await PipelineWithOrigin.send_print_values(ctx.channel, [results])
    
            except Exception as e:
                err.log(f'With args {args}:\n\t{type(e).__name__}: {e}', True)
                await ctx.send(embed=err.embed())

        func.__name__ = source.name
        func.__doc__ = source.get_command_doc()
        return func

    # Turn those sources into discord.py bot commands!
    for source in sources.commands:
        func = source_to_func(source)
        # manually call the function decorator to make func into a command
        command = commands.command()(func)
        bot.add_command(command)

    ###############################################################
    #                  Turn spouts into commands!                 #
    ###############################################################

    def spout_to_func(spout: Spout):
        async def func(ctx: commands.Context):
            text = util.strip_command(ctx)
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
            args, text, err = Arguments.from_string(text, spout.signature, greedy=False)
            err.name = f'`{spout.name}`'
            if err.terminal: return await ctx.send(embed=err.embed())
            args, err2 = await args.determine(script_context)
            text, err3 = await text.evaluate(script_context)
            err.extend(err2, 'arguments'); err.extend(err3, 'input string')
            if err.terminal: return await ctx.send(embed=err.embed())
            
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
    for spout in spouts.commands:
        func = spout_to_func(spout)
        # manually call the function decorator to make func into a command
        command = commands.command()(func)
        bot.add_command(command)
