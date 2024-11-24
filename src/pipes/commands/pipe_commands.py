from discord.ext import commands

from pipes.core.state.bot_state import BOT_STATE
from pipes.core.pipe import PipeoidStore
from pipes.implementations.pipes import NATIVE_PIPES
from pipes.implementations.sources import NATIVE_SOURCES
from pipes.implementations.spouts import NATIVE_SPOUTS
from pipes.core.macros import MACRO_PIPES, MACRO_SOURCES, Macros
from pipes.views import MacroView
from rezbot_commands import RezbotCommands
import utils.texttools as texttools

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
        if name and name in NATIVE_PIPES or name in NATIVE_SPOUTS or name in NATIVE_SOURCES:
            embed = (NATIVE_PIPES if name in NATIVE_PIPES else NATIVE_SPOUTS if name in NATIVE_SPOUTS else NATIVE_SOURCES)[name].embed(bot=self.bot)
            return await ctx.send(embed=embed)

        ## Info on a pipe macro or source macro
        elif name and name in MACRO_PIPES or name in MACRO_SOURCES:
            macros = MACRO_PIPES if name in MACRO_PIPES	else MACRO_SOURCES
            macro = macros[name]
            view = MacroView(macro, macros)
            embed = macro.embed(bot=self.bot, channel=ctx.channel)
            return view.set_message(await ctx.send(embed=embed, view=view))

        await self._list_pipeoids(ctx, name, NATIVE_PIPES, MACRO_PIPES)

    @commands.command(aliases=['source'])
    async def sources(self, ctx: commands.Context, name=''):
        '''Print a list of all sources and their descriptions, or details on a specific source.'''
        await self._list_pipeoids(ctx, name, NATIVE_SOURCES, MACRO_SOURCES)

    @commands.command(aliases=['spout'])
    async def spouts(self, ctx, name=''):
        '''Print a list of all spouts and their descriptions, or details on a specific source.'''
        await self._list_pipeoids(ctx, name, NATIVE_SPOUTS)


    # ========================== Variables management (message-commands) ==========================

    @commands.command(aliases=['list_persistent'])
    async def persistent_variables(self, ctx, pattern=None):
        await ctx.send( BOT_STATE.variables.list_names(pattern, True) )

    @commands.command(aliases=['list_transient'])
    async def transient_variables(self, ctx, pattern=None):
        await ctx.send( BOT_STATE.variables.list_names(pattern, False) )

    @commands.command(aliases=['list_all'])
    async def all_variables(self, ctx, pattern=None):
        await ctx.send( BOT_STATE.variables.list_names(pattern, True) +'\n'+ BOT_STATE.variables.list_names(pattern, False) )


# Load the bot cog
async def setup(bot: commands.Bot):
    await bot.add_cog(PipeCommands(bot))
