import asyncio
import re
import random
import time
import requests
import html

import discord
from discord.ext import commands

import permissions
import utils.util as util
import utils.texttools as texttools
import utils.benedict as benedict
import utils.soapstone as soapstone
from utils.frinkiac import simpsons, futurama
import resource.tweets as tweets
from resource.youtubecaps import youtubeCaps
from resource.jerkcity import JERKCITY
import utils.biogenerator
from utils.rand import *
from utils.meal import Meal
from utils.attack import Attack
from mycommands import MyCommands

'''
Main command module, contains a bunch of random functionality.
'''

triviaCategories = {
    'general' : 9 , 'books' : 10, 'film' : 11, 'music' : 12, 'musicals' : 13, 'tv' : 14, 'videogames' : 15,
    'board games' : 16, 'science' : 17, 'computers' : 18, 'maths' : 19, 'mythology' : 20, 'sports' : 21,
    'geography' : 22, 'history' : 23, 'politics' : 24, 'art' : 25, 'celebrities' : 26, 'animals' : 27,
    'vehicles' : 28, 'comics' : 29, 'gadgets' : 30, 'anime' : 31, 'cartoon' : 32,
}

class BotCommands(MyCommands):
    def __init__(self, bot):
        super().__init__(bot)

    ###################################
    ##        HIDDEN COMMANDS        ##
    ###################################

    @commands.command(hidden=True)
    @permissions.check(permissions.owner)
    async def die(self):
        '''Kill the bot.'''
        await self.say('dead.')
        await self._die()


    @commands.command(hidden=True)
    async def hide_self(self):
        '''Go invisible.'''
        await self.bot.change_presence(status=discord.Status.invisible)


    @commands.command(hidden=True)
    async def unhide_self(self):
        '''Go visible.'''
        await self.bot.change_presence(status=discord.Status.online)


    @commands.command(pass_context=True, hidden=True)
    async def play(self, ctx):
        '''Set the currently played game.'''
        game = util.strip_command(ctx)
        if game == '':
            await self.bot.change_presence(game=None)
        else:
            await self.bot.change_presence(game=discord.Game(name=game))


    @commands.command(pass_context=True, hidden=True)
    async def echo(self, ctx):
        '''Repeat your message in a code block (for emoji related purposes).'''
        await self.say('`{}`'.format(util.strip_command(ctx)))


    # TODO: extend this so the bot remembers which of its messages where caused by whom
    # so that you're allowed to >delet the bot's message if you were the one that 'caused' it
    # to self-moderate bot spam, or to fix your own slip-ups
    @commands.command(pass_context=True, hidden=True)
    @permissions.check(permissions.owner)
    async def delet(self, ctx, upperBound = 1, lowerBound = 0):
        '''delet (owner only)'''
        print('Deleting messages in #{0} between {1} and {2}'.format(ctx.message.channel.name, lowerBound, upperBound))
        i = 0
        async for log in self.bot.logs_from(ctx.message.channel, limit = 100):
            if log.author == self.bot.user:
                if i == upperBound:
                    return
                elif i >= lowerBound:
                    await self.bot.delete_message(log)
                i += 1

    ###################################
    ##          TOY COMMANDS         ##
    ###################################

    @commands.command(pass_context=True)
    async def kill(self, ctx):
        '''Kill someone'''
        subject = ctx.message.content[6:]
        if subject.lower() in ["yourself", "self", "myself", "rezbot"]:
            if permissions.has(ctx.message.author.id, permissions.owner):
                await self.say('killing self.')
                await self._die()
            else:
                await self.say('no')
        else:
            await self.say('killed {0}'.format( ctx.message.author.name if (subject == "me") else subject))


    @commands.command()
    async def cat(self, category:str=None):
        '''
        Posts a random cat picture, courtesy of http://thecatapi.com/
        
        Optional categories: hats, space, funny, sunglasses, boxes, caturday, ties, dream, kittens, sinks, clothes
        '''
        params = {'api_key': 'MjE4MjM2'}
        if category is not None:
            params['category'] = category
        r = requests.get('http://thecatapi.com/api/images/get', params=params, allow_redirects=False)
        await self.say(r.headers['Location'])


    @commands.command()
    @util.format_doc(categories=', '.join([c for c in triviaCategories]))
    async def trivia(self, category:str=None):
        '''
        Posts an absolutely legitimate trivia question.

        Categories: {categories}
        '''
        amount = 2
        params = {'amount': amount + 1}
        if category is not None:
            params['category'] = triviaCategories[category.lower()]
        r = requests.get('https://opentdb.com/api.php', params=params)
        results = r.json()['results']

        decode = html.unescape

        question = decode(results[0]['question'])

        wrongAnswerPool = []
        incorrect = [decode(i) for i in results[0]['incorrect_answers']]
        wrongAnswerPool += incorrect

        other_question = [decode(a) for i in range(amount) for a in results[i+1]['incorrect_answers'] + [results[i+1]['correct_answer']]]
        wrongAnswerPool += other_question
        
        correctAnswer = decode(results[0]['correct_answer'])
        wrongAnswerPool += [texttools.letterize(i, 0.4) for i in [correctAnswer]*3]

        if chance(0.4):
            wrongAnswerPool += ['Maybe']

        wrongAnswerPool = [x for x in util.remove_duplicates(wrongAnswerPool) if x != correctAnswer]

        random.shuffle(wrongAnswerPool)
        chosenAnswers = wrongAnswerPool[:3] + [correctAnswer]
        random.shuffle(chosenAnswers)

        text = question + '\n'
        for answ in chosenAnswers:
            text += '\n 🔘 ' + answ
        await self.say(text)


    @commands.command()
    async def bio(self, count:int=1):
        '''Post a random twitter bio, credit to Jon Hendren (@fart)'''
        messages = []
        for _ in range(min(count, 10)):
            messages.append(utils.biogenerator.get())
        await self.say('\n'.join(messages))


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


    @commands.command()
    async def sheriff(self, *bodyParts):
        '''Makes a sheriff using the given emoji.'''
        mySheriff = '⠀' + util.theSheriff
        if len(bodyParts):
            for i in range(12):
                mySheriff = mySheriff.replace(':100:', bodyParts[i % len(bodyParts)], 1)
        await self.bot.say(mySheriff)


    @commands.command(pass_context=True)
    async def simpsons(self, ctx):
        '''Search for a Simpsons screencap and caption matching a query (or a random one if no query is given).'''
        query = util.strip_command(ctx)
        if query == '':
            im, cap = simpsons.random()
        else:
            im, cap = simpsons.search(query)
        await self.say(im)
        await self.say(cap)


    @commands.command(pass_context=True)
    async def futurama(self, ctx):
        '''Search for a Futurama screencap and caption matching a query (or a random one if no query is given).'''
        query = util.strip_command(ctx)
        if query == '':
            im, cap = futurama.random()
        else:
            im, cap = futurama.search(query)
        await self.say(im)
        await self.say(cap)


    @commands.command(pass_context=True)
    async def dril(self, ctx):
        '''Search for a dril tweet matching a query (or a random one if no query is given).'''
        query = util.strip_command(ctx)
        if query == '':
            tweet = tweets.dril.random()
        else:
            tweet = choose(tweets.dril.search(query, 8))
        await self.say(tweet['href'])


    @commands.command()
    async def dril_ebook(self, max_length=140):
        '''Generate a random dril tweet'''
        await self.say(tweets.dril_model.make_short_sentence(max_length))


    @commands.command(pass_context=True)
    async def JERKCITY(self, CTX):
        '''SEARCH FOR A JERKCITY COMIC BASED ON TITLE OR DIALOGUE (OR NO QUERY FOR A RANDOM ONE)'''
        QUERY = util.strip_command(CTX)
        if QUERY == '':
            ISSUE = JERKCITY.GET_RANDOM()
        else:
            ISSUE = JERKCITY.SEARCH(QUERY)
        await self.say(ISSUE.URL())


    def trump_embed(text):
        embed = discord.Embed(description=text, color=0x4f545c)
        embed.set_author(name='Donald J. Trump (@realDonaldTrump)', url='https://twitter.com/realDonaldTrump', icon_url='https://pbs.twimg.com/profile_images/874276197357596672/kUuht00m_bigger.jpg')
        embed.set_footer(text='Twitter', icon_url='https://abs.twimg.com/icons/apple-touch-icon-192x192.png')
        embed.add_field(name='Retweets', value=random.randint(5000, 50000))
        embed.add_field(name='Likes', value=random.randint(25000, 150000))
        return embed

    @commands.command(pass_context=True, hidden=True)
    async def drump(self, ctx):
        query = util.strip_command(ctx)
        if query == '': tweet = tweets.dril.random()
        else: tweet = choose(tweets.dril.search(query, 8))
        embed = BotCommands.trump_embed(tweet['text'])
        await self.bot.say(embed=embed)


    @commands.command()
    async def lunch(self, kind='regular'):
        '''Generate a fake lunch menu in Dutch. If the first argument is "weird" it will produce a weirder menu.'''
        await self.bot.say(Meal.generateMenu(kind))


    @commands.command(pass_context=True)
    async def image_split(self, ctx):
        '''Splits a series of image urls into groups of 5 and posts them.'''
        urls = list(filter(lambda t: re.match('https?://', t) is not None, util.strip_command(ctx).split()))[5:]
        for i in range(0, len(urls), 5):
            await self.say(' '.join(urls[i:i+5]))


def setup(bot):
    bot.add_cog(BotCommands(bot))