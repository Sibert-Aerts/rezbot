import asyncio
import re
import random
import time
import requests
import html
import sys, traceback

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
from utils.ctree import CTree
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
    @permissions.check('owner')
    async def die(self):
        '''Kill the bot.'''
        await self.say('dead.')
        await self._die()


    @commands.command(hidden=True)
    async def hide(self):
        '''Go invisible.'''
        await self.bot.change_presence(status=discord.Status.invisible)


    @commands.command(hidden=True)
    async def unhide(self):
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


    @commands.command(pass_context=True, hidden=True)
    async def expand(self, ctx):
        '''
        expand.
        
        "[a|b]c[d|e]" -> "acd", "bcd", "ace", "bce"
        '''
        text = util.strip_command(ctx)
        tree = CTree.parse(text)
        all = []
        while not tree.done:
            all.append(tree.next())
        text = '\n'.join(all)
        await self.say(text)

    # TODO: extend this so the bot remembers which of its messages where caused by whom
    # so that you're allowed to >delet the bot's message if you were the one that 'caused' it
    # to self-moderate bot spam, or to fix your own slip-ups
    @commands.command(pass_context=True, hidden=True)
    @permissions.check('owner')
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
            if permissions.has(ctx.message.author.id, 'owner'):
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
    async def youtube(self, ctx):
        '''Get a random caption from a youtube video from a list of saved youtube videos'''
        query = util.strip_command(ctx)
        if query.strip() == '':
            cap, url = youtubeCaps.get_random()
            await self.say(url)
            await self.say(cap)
        else:
            try:
                cap, url = youtubeCaps.search(query)
                await self.say(url)
                await self.say(cap)
            except IndexError:
                await self.say('no results found for search "{}".'.format(query))


    @commands.command(pass_context=True)
    async def youtube_add(self, ctx, url, alias=None, *tags):
        '''Add a video to the list of tracked videos'''
        try:
            if url[0] == '<' and url[-1] == '>': url = url[1:-1]
            title, what = youtubeCaps.download_subs(url, alias, tags)
            aliastext = '' if alias is None else ' with alias "{}"'.format(alias)
            tagstext = '' if len(tags) == 0 else ', tags: ' + ', '.join(tags)
            await self.say('successfully saved {} for youtube video "{}"{}{}'.format(what, title, aliastext, tagstext))
        except ValueError as e:
            await self.say(e)
        except Exception as e:
            print(e)
            await self.say('something went wrong. make sure the url is correct.')


    @commands.command(aliases=['youtube_remove'])
    @permissions.check('owner')
    async def youtube_delete(self, identifier):
        '''Delete a video from the list of tracked videos'''
        try:
            title = youtubeCaps.delete(identifier)
            await self.say('successfully deleted captions for video "{}".'.format(title))
        except ValueError as e:
            await self.say(e)


    @commands.command()
    async def youtube_alias(self, ident, alias):
        '''Give a video (by id or title) an alias'''
        video = youtubeCaps.identify(ident)
        if video is None:
            await self.say('"{}" does not uniquely identify a video.'.format(ident))
            return
        oldAlias = video.alias
        video.alias = alias
        video.write()
        if oldAlias is None:
            await self.say('successfully set the alias for video "{}" to "{}".'.format(video.title, alias))
        else:
            await self.say('successfully changed the alias for video "{}" from "{}" to "{}".'.format(video.title, oldAlias, alias))


    @commands.command(aliases=['youtube_tag', 'youtube_add_tag'])
    async def youtube_add_tags(self, ident, *tags):
        '''Give a video (by id or title or alias) new tags'''
        video = youtubeCaps.identify(ident)
        if video is None:
            await self.say('"{}" does not uniquely identify a video.'.format(ident))
            return
        video.tags = list(set(video.tags).union(tags))
        video.write()
        await self.say('tags successfully added, tags for "{}" are now: {}.'.format(video.title, ', '.join(video.tags)))


    @commands.command(aliases=['youtube_remove_tag', 'youtube_delete_tags', 'youtube_delete_tag'])
    async def youtube_remove_tags(self, ident, *tags):
        '''Remove tags from a video.'''
        video = youtubeCaps.identify(ident)
        if video is None:
            await self.say('"{}" does not uniquely identify a video.'.format(ident))
            return
        video.tags = list(set(video.tags) - set(tags))
        video.write()
        await self.say('tags successfully removed, tags for "{}" are now: {}.'.format(video.title, ', '.join(video.tags)))


    @commands.command()
    async def youtube_info(self, ident=''):
        '''Get info on all loaded videos or a specific loaded video.'''
        if ident == '':
            info = '**Loaded videos:**\n'
            for id in youtubeCaps.videos:
                video = youtubeCaps.videos[id]
                info += '• **{}**'.format(video.title)
                if video.alias:
                    info += ' AKA "{}"'.format(video.alias)
                info += ', tags: `{}`\n'.format(', '.join(video.tags) if video.tags else '(None)')
            await self.say(info)
        else:
            video = youtubeCaps.identify(ident)
            if video is None:
                await self.say('"{}" does not uniquely identify a video.'.format(ident))
                return
            # TODO


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