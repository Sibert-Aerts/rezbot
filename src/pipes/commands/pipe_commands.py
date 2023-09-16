from discord.ext import commands

from pipes.core.pipeline_with_origin import PipelineWithOrigin
from pipes.core.pipe import Pipe, Source, Spout, PipeoidStore
from pipes.core.context import Context
from pipes.implementations.pipes import pipes
from pipes.implementations.sources import sources, SourceResources
from pipes.implementations.spouts import spouts
from pipes.core.macros import pipe_macros, source_macros, Macros
from pipes.core.signature import Arguments
from pipes.views import MacroView
from mycommands import MyCommands
import utils.texttools as texttools
import utils.util as util

###############################################################
#            A module providing commands for pipes            #
###############################################################

class PipeCommands(MyCommands):

    @commands.command(aliases=['pipe_help', 'pipes_info', 'pipe_info', 'pipes_guide', 'pipe_guide'])
    async def pipes_help(self, ctx):
        '''Links the guide to using pipes.'''
        await ctx.send('https://github.com/Sibert-Aerts/rezbot/blob/master/PIPESGUIDE.md')

    
    # ========================== Pipeoid lookup (message-commands) ==========================

    async def _list_pipeoids(self, ctx: commands.Context, name: str, pipeoids: PipeoidStore, pipeoid_macros: Macros=None):
        '''Print a list of all pipes and their descriptions, or details on a specific pipe.'''
        name = name.lower()
        uname = name.upper()
        type_name = pipeoids._name_singular
        types_name = pipeoids._name_plural

        ## Info on a specific pipeoid
        if name and name in pipeoids:
            embed = pipeoids[name].embed(bot=self.bot)
            return await ctx.send(embed=embed)

        ## Info on a specific pipeoid macro
        if pipeoid_macros and name and name in pipeoid_macros:
            macro = pipeoid_macros[name]
            view = MacroView(macro, pipeoid_macros)
            embed = macro.embed(bot=self.bot, channel=ctx.channel)
            return view.set_message(await ctx.send(embed=embed, view=view))

        ## List pipeoids in a specific category
        elif uname and uname in pipeoids.categories:
            infos = []
            infos.append(f'{types_name} in category {uname}:\n')
            
            category = pipeoids.categories[uname]
            col_w = len(max((p.name for p in category), key=len)) + 3
            for pipe in category:
                info = pipe.name.ljust(col_w)
                if pipe.doc: info += pipe.small_doc
                infos.append(info)

            infos.append('')
            infos.append(f'Use >{types_name.lower()} [{type_name.lower()} name] to see more info on a specific {type_name.lower()}.')
            if pipeoid_macros:
                infos.append(f'Use >{type_name.lower()}_macros for a list of user-defined {types_name.lower()}.\n')
            return await ctx.send(texttools.block_format('\n'.join(infos)))

        ## List all categories
        else:
            infos = []
            infos.append('Categories:\n')
            
            col_w = len(max(pipeoids.categories, key=len)) + 2
            for category in pipeoids.categories:
                info = category.ljust(col_w)
                cat = pipeoids.categories[category]
                MAX_PRINT = 10
                if len(cat) > MAX_PRINT:
                    info += ', '.join(p.name for p in cat[:MAX_PRINT - 1]) + '... (%d more)' % (len(cat) - MAX_PRINT + 1)
                else:
                    info += ', '.join(p.name for p in cat)
                infos.append(info)
                
            infos.append('')
            infos.append(f'Use >{types_name.lower()} [category name] for the list of {types_name.lower()} in a specific category.')
            infos.append(f'Use >{types_name.lower()} [{type_name.lower()} name] to see more info on a specific {type_name.lower()}.')
            if pipeoid_macros:
                infos.append(f'Use >{type_name.lower()}_macros for a list of user-defined {types_name.lower()}.\n')
            return await ctx.send(texttools.block_format('\n'.join(infos)))


    @commands.command(aliases=['pipe'], hidden=True)
    async def pipes(self, ctx: commands.Context, name=''):
        name = name.lower()

        # SPECIAL CASE: >pipe also allows you to look up ANY kind of pipeoid or macro, for convenience
        ## Info on a specific pipe, spout or source
        if name and name in pipes or name in spouts or name in sources:
            embed = (pipes if name in pipes else spouts if name in spouts else sources)[name].embed(bot=self.bot)
            return await ctx.send(embed=embed)

        ## Info on a pipe macro or source macro
        elif name and name in pipe_macros or name in source_macros:
            macros = pipe_macros if name in pipe_macros	else source_macros
            macro = macros[name]
            view = MacroView(macro, macros)
            embed = macro.embed(bot=self.bot, channel=ctx.channel)
            return view.set_message(await ctx.send(embed=embed, view=view))

        await self._list_pipeoids(ctx, name, pipes, pipe_macros)

    @commands.command(aliases=['source'], hidden=True)
    async def sources(self, ctx: commands.Context, name=''):
        '''Print a list of all sources and their descriptions, or details on a specific source.'''
        await self._list_pipeoids(ctx, name, sources, source_macros)

    @commands.command(aliases=['spout'], hidden=True)
    async def spouts(self, ctx, name=''):
        '''Print a list of all spouts and their descriptions, or details on a specific source.'''
        await self._list_pipeoids(ctx, name, spouts)


    # ========================== Variables management (message-commands) ==========================
    
    @commands.command(aliases=['list_persistent'])
    async def persistent_variables(self, ctx, pattern=None):
        await ctx.send( SourceResources.variables.list_names(pattern, True) )
    
    @commands.command(aliases=['list_transient'])
    async def transient_variables(self, ctx, pattern=None):
        await ctx.send( SourceResources.variables.list_names(pattern, False) )
    
    @commands.command(aliases=['list_all'])
    async def all_variables(self, ctx, pattern=None):
        await ctx.send( SourceResources.variables.list_names(pattern, True) +'\n'+ SourceResources.variables.list_names(pattern, False) )


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
    
    await bot.add_cog(PipeCommands(bot))
