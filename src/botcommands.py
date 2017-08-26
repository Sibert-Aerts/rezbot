import asyncio
import re
import random
import time
import requests

import discord
from discord.ext import commands

import permissions
import utils.util as util
import utils.texttools as texttools
import utils.benedict as benedict
from utils.ctree import CTree
from utils.meal import Meal
from utils.attack import Attack
from mycommands import MyCommands

'''
Main command module, contains a bunch of random functionality.
'''

class BotCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)


    @commands.command()
    @permissions.check('owner')
    async def die(self):
        '''Kill the bot.'''
        await self.say('dead.')
        await self._die()


    @commands.command(pass_context=True)
    async def echo(self, ctx):
        '''Repeat your message in a code block (for emoji related purposes).'''
        await self.say('`{}`'.format(util.get_args(ctx)))


    # toy command
    @commands.command(pass_context=True)
    async def kill(self, ctx):
        '''Kill someone'''
        subject = ctx.message.content[6:]
        if subject.lower() in ["yourself", "self", "myself", "rezbot"]:
            if permissions.has(ctx.message.author.id, 'owner'):
                await self.say('killing self.')
                await self._die()
            else:
                await self.say('no')
        else:
            await self.say('killed {0}'.format( ctx.message.author.name if (subject == "me") else subject))


    @commands.command(pass_context=True)
    async def cat(self, ctx):
        '''Posts a random cat picture, courtesy of http://thecatapi.com/'''
        r = requests.get('http://thecatapi.com/api/images/get',
            params={'api_key': 'MjE4MjM2'})
        await self.say(r.url)


    @commands.command(pass_context=True)
    async def expand(self, ctx):
        '''
        expand.
        
        "[a|b]c[d|e]" -> "acd", "bcd", "ace", "bce"
        '''
        text = util.get_args(ctx)
        tree = CTree.parse(text)
        all = []
        while not tree.done:
            all.append(tree.next())
        text = '\n'.join(all)
        await self.say(text)


    @commands.command()
    async def word_gradient(self, w1:str, w2:str, n:int=5):
        '''gradient between two words'''
        if n > 9: return
        text = '\n'.join(util.remove_duplicates([w1] + texttools.dist_gradient(w1, w2, n) + [w2]))
        await self.say(texttools.block_format(text))


    @commands.command()
    async def weapons(self):
        '''Show all weapons the bot recognises to start emoji fights.'''
        text = "`left-facing weapons:` " + " ".join(Attack.leftWeapons)
        text += "\n`right-facing weapons:` " + " ".join(Attack.rightWeapons)
        await self.say(text)


    @commands.command(pass_context=True)
    async def play(self, ctx):
        '''Set the currently played game.'''
        game = util.get_args(ctx)
        if game == '':
            await self.bot.change_presence(game=None)
        else:
            await self.bot.change_presence(game=discord.Game(name=game))


    @commands.command()
    async def sheriff(self, *bodyParts):
        '''Makes a sheriff using the given emoji.'''
        mySheriff = '⠀' + util.theSheriff
        if len(bodyParts):
            for i in range(12):
                mySheriff = mySheriff.replace(':100:', bodyParts[i % len(bodyParts)], 1)
        await self.bot.say(mySheriff)

    @commands.command()
    async def hide(self):
        '''Go invisible.'''
        await self.bot.change_presence(status=discord.Status.invisible)


    @commands.command()
    async def unhide(self):
        '''Go visible.'''
        await self.bot.change_presence(status=discord.Status.online)


    @commands.command(pass_context=True)
    async def lunch(self, ctx, kind='regular'):
        '''Generate a fake lunch menu in Dutch. If the first argument is "weird" it will produce a weirder menu.'''
        await self.bot.say(Meal.generateMenu(kind))


    @commands.command()
    async def cumberbatch(self, count=1):
        '''Generate a name that mimics "Benedict Cumberbatch".'''
        if count > 10:
            await self.say('that\'s a bit much don\'t you think')
            return
        text = '\n'.join([benedict.generate() for _ in range(count)])
        await self.say(text)


    @commands.command(pass_context=True)
    async def image_split(self, ctx):
        '''Splits a series of image urls into groups of 5 and posts them.'''
        urls = list(filter(lambda t: re.match('https?://', t) is not None, util.get_args(ctx).split()))[5:]
        for i in range(0, len(urls), 5):
            await self.say(' '.join(urls[i:i+5]))

    # todo: extend this so the bot remembers which of its messages where caused by whom
    # so that you're allowed to >delet the bot's message if you were the one that 'caused' it
    # to self-moderate bot spam, or to fix your own slip-ups
    @commands.command(pass_context=True)
    @permissions.check('owner')
    async def delet(self, ctx, upperBound = 1, lowerBound = 0):
        '''delet'''
        print('Deleting messages in #{0} between {1} and {2}'.format(ctx.message.channel.name, lowerBound, upperBound))
        i = 0
        async for log in self.bot.logs_from(ctx.message.channel, limit = 100):
            if log.author == self.bot.user:
                if i == upperBound:
                    return
                elif i >= lowerBound:
                    await self.bot.delete_message(log)
                i += 1

def setup(bot):
    bot.add_cog(BotCommands(bot))