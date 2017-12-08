from functools import wraps
import pickle

import discord
from discord.ext import commands

from .pipes import *
from mycommands import MyCommands
import utils.texttools as texttools
import utils.util as util

infoText = '''
Pipes are a weird text-manipulation tool/toy I came up with in a dream.
The idea is that you give some kind of text input, and put it through a series of pipes,
each of which takes text input, changes it and gives it to the next pipe.
Like a game of telephone.

You can execute a series of pipes by typing something like this:
  `>>> [start] > [pipe] > [pipe] > ...`

Where:
  [start] can just be plain text, e.g. `Quentin Tarantino`.
    or it can be **`{prev}`** to use the output from the previous pipe command.
  Each [pipe] is an item from the list of pipes (which you can see by typing `>pipes`).
    Some pipes take arguments by typing `argument=value` (or ignore the first bit if it only takes one argument.)
    e.g. `translate from=en to=ja`, `print`, `repeat n=3` or just `repeat 3`

For example, a valid pipe command could be:
  `>>> Quentin Tarantino > repeat 4 -> letterize p=0.5 > min_dist`

Note that `->` is shorthand for `> print >`, and that after the final pipe a `> print` is automatically added.
'''

customPipes = {}
try:
    customPipes = pickle.load(open('custompipes.p', 'rb'))
    print(len(customPipes), 'custom pipes loaded.')
except:
    print('Could not load custompipes.p!')
    pass

###############################################################
#              An extra command module for pipes              #
###############################################################

class PipesCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)

    @commands.command()
    async def languages(self, name=''):
        '''Print the list of languages applicable for the translate command/pipe.'''
        await self.say(' '.join(texttools.translateLanguages))

    @commands.command()
    async def pipe(self):
        '''Print general info on how to use my wacky system of pipes.'''
        await self.say(infoText)

    @commands.command()
    async def pipes(self, name=''):
        '''Print a list of all pipes and their descriptions, or details on a specific pipe.'''
        infos = []

        # Info on a specific pipe
        if name != '' and pipeNames.get(name) is not None:
            pipe = pipeNames[name]
            info = name
            if pipe.__doc__ is not None:
                info += ':\n\t' + pipe.__doc__
            if pipe.signature:
                info += '\n\tArguments:'
                info += '\n\t • ' + '\n\t • '.join(pipe.signature)
            infos.append(info)

        # Info on all pipes
        else:
            infos.append('Here\'s a list of pipes, use >pipes [pipe name] to see more info on a specific one.\n')
            colW = len(max(pipeNames, key=len)) + 2
            for name in pipeNames:
                pipe = pipeNames[name]
                info = name + ' ' * (colW-len(name))
                if pipe.__doc__ is not None:
                    info += pipe.__doc__
                infos.append(info)
        
        text = texttools.block_format('\n'.join(infos))
        await self.say(text)

    # Custom pipes down here

    @commands.command(pass_context=True)
    async def define(self, ctx, name=''):
        '''Define a custom pipe. First argument is the name, everything after that is the code.'''
        name = name.lower()
        if name in pipeNames or name in customPipes:
            await self.say('A pipe by that name already exists, try >redefine instead.')
            return
        code = re.split('\s+', ctx.message.content, 2)[2]
        customPipes[name] = {'desc': None, 'code': code}
        await self.say('Defined a new pipe called `{}` as `{}`'.format(name, customPipes[name]['code']))
        pickle.dump(customPipes, open('custompipes.p', 'wb'))


    @commands.command(pass_context=True)
    async def redefine(self, ctx, name=''):
        '''Redefine a custom pipe. First argument is the name, everything after that is the code.'''
        name = name.lower()
        if name not in customPipes:
            await self.say('A custom pipe by that name was not found!')
            return
        code = re.split('\s+', ctx.message.content, 2)[2]
        customPipes[name]['code'] = code
        await self.say('Redefined `{}` as `{}`'.format(name, customPipes[name]['code']))
        pickle.dump(customPipes, open('custompipes.p', 'wb'))


    @commands.command(pass_context=True)
    async def describe(self, ctx, name=''):
        '''Describe a custom pipe. First argument is the name, everything after that is the description.'''
        name = name.lower()
        if name not in customPipes:
            await self.say('A custom pipe by that name was not found!')
            return
        desc = re.split('\s+', ctx.message.content, 2)[2]
        customPipes[name]['desc'] = desc
        await self.say('Described `{}` as `{}`'.format(name, customPipes[name]['desc']))
        pickle.dump(customPipes, open('custompipes.p', 'wb'))


    @commands.command()
    async def custom_pipes(self, name=''):
        '''Print a list of all custom pipes and their descriptions, or details on a specific custom pipe.'''
        infos = []

        # Info on a specific pipe
        if name != '' and name in customPipes:
            pipe = customPipes[name]
            info = name + ':'
            if pipe['desc'] is not None:
                info += '\n\t' + pipe['desc']
            info += '\nCode:'
            info += '\n\t' + pipe['code']
            # if pipe.signature:
            #     info += '\n\tArguments:'
            #     info += '\n\t • ' + '\n\t • '.join(pipe.signature)
            infos.append(info)

        # Info on all pipes
        else:
            infos.append('Here\'s a list of all custom pipes, use >custom_pipes [name] to see more info on a specific one.\n')
            colW = len(max(customPipes, key=len)) + 2
            for name in customPipes:
                pipe = customPipes[name]
                info = name + ' ' * (colW-len(name))
                if pipe['desc'] is not None:
                    info += pipe['desc']
                infos.append(info)
        
        text = texttools.block_format('\n'.join(infos))
        await self.say(text)

# List of pipes that are also usable as a regular command:
command_pipes = \
    [ vowelize_pipe, consonize_pipe, letterize_pipe, min_dist_pipe, katakana_pipe, romaji_pipe, demoji_pipe, translate_pipe, convert_pipe]

# Turn those pipes into discord.py bot commands!
for pipe in command_pipes:
    async def func(self, ctx):
        text = util.get_args(ctx)
        text = pipe(text)
        await self.say(text)
    func.__name__ = pipe.__name__.split('_pipe', 1)[0]
    func.__doc__ = pipe.__doc__
    # manually call the function decorator to make func into a bot command
    command = commands.command(pass_context=True)(func)
    setattr(PipesCommands, func.__name__, command)

def setup(bot):
    bot.add_cog(PipesCommands(bot))