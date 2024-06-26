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
from rezbot_commands import RezbotCommands
import utils.texttools as texttools
import utils.util as util

###############################################################
#            A module providing commands for pipes            #
###############################################################

class PipeCommands(RezbotCommands):

    @commands.command(aliases=['pipe_help', 'pipes_info', 'pipe_info', 'pipes_guide', 'pipe_guide'])
    async def pipes_help(self, ctx):
        '''Links the guide to using pipes.'''
        await ctx.send('https://github.com/Sibert-Aerts/rezbot/blob/master/PIPESGUIDE.md')


    # ========================== Pipeoid lookup (message-commands) ==========================

    async def _list_pipeoids(self, ctx: commands.Context, name: str, pipeoids: PipeoidStore, pipeoid_macros: Macros=None):
        '''Generic method used by >pipes, >sources and >spouts commands.'''
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

    @commands.command(aliases=['pipe'])
    async def pipes(self, ctx: commands.Context, name=''):
        '''Print a list of all pipes and their descriptions, or details on a specific pipe.'''
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

    @commands.command(aliases=['source'])
    async def sources(self, ctx: commands.Context, name=''):
        '''Print a list of all sources and their descriptions, or details on a specific source.'''
        await self._list_pipeoids(ctx, name, sources, source_macros)

    @commands.command(aliases=['spout'])
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
    await bot.add_cog(PipeCommands(bot))
