import random

import discord
from discord.ext import commands

from mycommands import MyCommands
import permissions
import utils.util as util
import utils.texttools as texttools
import utils.wordle as wordle
from utils.rand import *
from utils.frinkiac import simpsons, futurama
from utils.emojifight import EmojiFight
import resource.tweets as tweets
from resource.jerkcity import JERKCITY
from resource.upload import uploads

'''
Main command module, contains a bunch of random functionality.
'''

class BotCommands(MyCommands):

    ###################################
    ##        HIDDEN COMMANDS        ##
    ###################################

    @commands.command(hidden=True)
    @permissions.check(permissions.owner)
    async def die(self, ctx):
        '''Kill the bot.'''
        await ctx.send('dead.')
        await self._die()


    @commands.command(hidden=True)
    async def hide_self(self, ctx):
        '''Go invisible.'''
        await self.bot.change_presence(status=discord.Status.invisible)


    @commands.command(hidden=True)
    async def unhide_self(self, ctx):
        '''Go visible.'''
        await self.bot.change_presence(status=discord.Status.online)


    @commands.command(hidden=True)
    async def play(self, ctx: commands.Context):
        '''Set the currently played game.'''
        game = util.strip_command(ctx)
        if game == '':
            await self.bot.change_presence(activity=None)
        else:
            await self.bot.change_presence(activity=discord.Game(name=game))


    @commands.command(hidden=True)
    async def echo(self, ctx):
        '''Repeat your message in a code block (for emoji related purposes).'''
        await ctx.send('`{}`'.format(util.strip_command(ctx)))


    # TODO: extend this so the bot remembers which of its messages where caused by whom
    # so that you're allowed to >delet the bot's message if you were the one that 'caused' it
    # to self-moderate bot spam, or to fix your own slip-ups
    @commands.command(hidden=True)
    @permissions.check(permissions.owner)
    async def delet(self, ctx: commands.Context, upperBound = 1, lowerBound = 0):
        '''delet (owner only)'''
        name = 'this DM' if isinstance(ctx.channel, discord.abc.PrivateChannel) else ctx.author.name
        print('Deleting messages in #{0} between {1} and {2}'.format(name, lowerBound, upperBound))
        i = 0
        async for log in ctx.channel.history(limit=upperBound+100):
            if log.author == self.bot.user:
                if i == upperBound:
                    return
                elif i >= lowerBound:
                    await log.delete()
                i += 1
                

    colourRoles = [
        403542818456600577, # red
        911917474025447434, # orange
        403543018612981781, # yellow
        403543056181231626, # green
        403543084010569739, # cyan
        403543156760772618, # blue
        403543179699290112, # purple
        911920677148303422, # magenta
    ]
    colourExempt = [
        430477870180204545, # Rezbot 2 (kick)
        274202462884331520  # Rezbot (mine)
    ]

    @commands.command(hidden=True, aliases=['update_color_roles', 'update_colours', 'update_colors', 'refresh_colors', 'refresh_colours'])
    @permissions.check(permissions.owner)
    async def update_colour_roles(self, ctx):
        '''Automatically (un)assign colour roles to members of the rezbot server.'''
        if ctx.guild.id != 382291692864274432: return

        ## Filter and sort members
        members: List[discord.Member] = [m for m in ctx.guild.members if m.id not in BotCommands.colourExempt]
        members.sort( key=lambda m: m.display_name.lower() )

        ## Get colour roles
        colours: List[discord.Role] = [ discord.utils.get(ctx.guild.roles, id=id) for id in self.colourRoles ]

        ## Assign colour roles
        n = len(members) / len(colours) # Need not be an integer!
        updates = 0
        for i in range(len(members)):
            member = members[i]
            intendedColour = colours[ int(i//n) ]
            otherColours = colours[:int(i//n)] + colours[int(i//n)+1:]
            intersect = set(otherColours) & set(member.roles)
            updated = False
            if intersect:
                updated = True
                await member.remove_roles(*intersect)
            if intendedColour not in member.roles:
                updated = True
                await member.add_roles(intendedColour)

            if updated:
                updates += 1

        await ctx.send('Updated the colours of %d members :rainbow:' % updates)

    @commands.command(hidden=True)
    @permissions.check(permissions.owner)
    async def sync(self, ctx: commands.Context):
        print('Publishing commands:', ' '.join(c.name for c in self.bot.tree.get_commands()))
        await self.bot.tree.sync()
        await ctx.message.add_reaction('✅')
        
    @commands.command(hidden=True)
    @permissions.check(permissions.owner)
    async def unsync(self, ctx: commands.Context):
        print('Unpublishing all commands.')
        self.bot.tree.clear_commands(guild=None)
        await self.bot.tree.sync()
        await ctx.message.add_reaction('✅')
        
    @commands.command(hidden=True)
    @permissions.check(permissions.owner)
    async def sync_guild(self, ctx: commands.Context):
        print('Syncing guild commands:', ' '.join(c.name for c in self.bot.tree.get_commands(guild=ctx.guild)))
        await self.bot.tree.sync(guild=ctx.guild)
        await ctx.message.add_reaction('✅')


    ###################################
    ##          TOY COMMANDS         ##
    ###################################

    @commands.command()
    async def kill(self, ctx):
        '''Kill someone'''
        subject = util.strip_command(ctx)
        if subject.lower() in ["yourself", "self", "myself", "rezbot"]:
            if permissions.has(ctx.author.id, permissions.owner):
                await ctx.send('killing self.')
                await self._die()
            else:
                await ctx.send('no')
        else:
            await ctx.send('killed {0}'.format( ctx.author.name if (subject == "me") else subject))


    @commands.command()
    async def word_gradient(self, ctx, w1:str, w2:str, n:int=5):
        '''gradient between two words'''
        if n > 20: return
        text = '\n'.join(util.remove_duplicates([w1] + texttools.dist_gradient(w1, w2, n) + [w2]))
        await ctx.send(texttools.block_format(text))


    @commands.command()
    async def weapons(self, ctx):
        '''Show all weapons the bot recognises to start emoji fights.'''
        text = "`left-facing weapons:` " + " ".join(EmojiFight.leftWeapons)
        text += "\n`right-facing weapons:` " + " ".join(EmojiFight.rightWeapons)
        text += "\n`duel-starting weapons:` " + " ".join(EmojiFight.dualWeapons)
        await ctx.send(text)


    @commands.command(hidden=True)
    async def sheriff(self, ctx, *bodyParts):
        '''Makes a sheriff using the given emoji.'''
        mySheriff = '⠀' + util.theSheriff
        if len(bodyParts):
            for i in range(12):
                mySheriff = mySheriff.replace(':100:', bodyParts[i % len(bodyParts)], 1)
        await ctx.send(mySheriff)


    @commands.command()
    async def simpsons(self, ctx):
        '''Search for a Simpsons screencap and caption matching a query (or a random one if no query is given).'''
        query = util.strip_command(ctx)
        if query == '':
            im, cap = simpsons.random()
        else:
            im, cap = simpsons.search(query)
        await ctx.send(im)
        await ctx.send(cap)


    @commands.command()
    async def futurama(self, ctx):
        '''Search for a Futurama screencap and caption matching a query (or a random one if no query is given).'''
        query = util.strip_command(ctx)
        if query == '':
            im, cap = futurama.random()
        else:
            im, cap = futurama.search(query)
        await ctx.send(im)
        await ctx.send(cap)


    @commands.command()
    async def dril(self, ctx):
        '''Search for a dril (@wint) tweet matching a query (or a random one if no query is given).'''
        query = util.strip_command(ctx)
        if query == '':
            tweet = tweets.dril.random()
        else:
            tweet = choose(tweets.dril.search(query, 8))
        await ctx.send(tweet['href'])


    @commands.command()
    async def derek(self, ctx):
        '''Search for a derek (@eedrk) tweet matching a query (or a random one if no query is given).'''
        query = util.strip_command(ctx)
        if query == '':
            tweet = tweets.derek.random()
        else:
            tweet = choose(tweets.derek.search(query, 8))
        # TODO: output as faux tweet embed, since these are HISTORY
        await ctx.send(tweet['text'])


    @commands.command()
    async def dril_ebook(self, ctx, max_length=140):
        '''Generate a random dril tweet'''
        await ctx.send(tweets.dril_model.make_short_sentence(max_length))


    @commands.command()
    async def JERKCITY(self, CTX):
        '''SEARCH FOR A JERKCITY COMIC BASED ON TITLE OR DIALOGUE (OR NO QUERY FOR A RANDOM ONE)'''
        QUERY = util.strip_command(CTX)
        if QUERY == '':
            ISSUE = JERKCITY.GET_RANDOM()
        else:
            ISSUE = JERKCITY.SEARCH(QUERY)
        await CTX.send(ISSUE.URL())


    def trump_embed(text):
        embed = discord.Embed(description=text, color=0x1da1f2)
        embed.set_author(name='Donald J. Trump (@realDonaldTrump)', url='https://twitter.com/realDonaldTrump', icon_url='https://pbs.twimg.com/profile_images/874276197357596672/kUuht00m_bigger.jpg')
        embed.set_footer(text='Twitter', icon_url='https://abs.twimg.com/icons/apple-touch-icon-192x192.png')
        embed.add_field(name='Retweets', value=random.randint(5000, 50000))
        embed.add_field(name='Likes', value=random.randint(25000, 150000))
        return embed


    @commands.command(hidden=True)
    async def drump(self, ctx):
        query = util.strip_command(ctx)
        if query == '': tweet = tweets.dril.random()
        else: tweet = choose(tweets.dril.search(query, 8))
        embed = BotCommands.trump_embed(tweet['text'])
        await ctx.send(embed=embed)


    @commands.command()
    async def solve_wordle(self, ctx, theWord, file='wordle_guesses'):
        '''
        Make the bot try to solve a wordle, semi-naively.
        
        First argument is the word to solve for, wrap it in ||'s to make the bot treat the word as secret. 
        Second, optional argument is a file name (see `>files`) to use as its corpus of allowed guesses.
        '''
        spoilers = False
        if theWord[:2] == theWord[-2:] == '||':
            spoilers = True
            theWord = theWord[2:-2]
        theWord = theWord.lower()
        n = len(theWord)

        try:
            file = uploads[file]
        except Exception as e:
            await ctx.send(e); return
        corpus = [word.lower() for word in file.get() if len(word) == n]
        if theWord not in corpus: corpus.append(theWord)

        output = []

        if len(corpus) == 1:
            await ctx.send('Corpus contains no entries of the same length as the target word.')
            return

        ## Simulate solving the wordle
        for i in range(6):
            if len(corpus) == 0:
                print('RAN OUT OF WORDS?????')
                break
            guess = random.choice(corpus)
            print('CORPUS SIZE:', len(corpus))
            info = wordle.create_info(theWord, guess)
            output.append( info.emoji + '   ' + (f'||`{guess}`||' if spoilers else f'`{guess}`'))
            if info.solved:
                break
            corpus = [word for word in corpus if info.test(word)]
        print()

        ## Formatting
        turns = str(i+1) if info.solved else 'X'
        output = ['Rezbot Wordle {}/6*'.format(turns), ''] + output
        smiley = {'1': '🤯', '2': '🤩', '3': '😃', '4': '🙂', '5': '😐', '6': '😟', 'X': '😢'}[turns] or '🤔'

        await (await ctx.send('\n'.join(output))).add_reaction(smiley)


async def setup(bot):
    await bot.add_cog(BotCommands(bot))