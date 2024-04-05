import discord
from discord.ext import commands

from rezbot_commands import RezbotCommands, Par, command_with_signature
import permissions
from utils.emojifight import EmojiBattle, EmojiFight, EmojiOutput


EMOJI_BATTLES: dict[str, EmojiBattle] = {}
CURRENT_BATTLE: EmojiBattle = None


def count_reactions(reactions: list[discord.Reaction], *emoji: str):
    total = 0
    for reaction in reactions:
        if str(reaction.emoji) in emoji:
            total += reaction.count
    return total


class EmojiFightCommands(RezbotCommands):

    @commands.command()
    async def emoji_fight(self, ctx, left: str, right: str, rigged=None):
        if not left or not right:
            raise ValueError('Please give two combattants.')
        if rigged not in (None, 'left', 'right', 'both'):
            raise ValueError('Invalid value for "rigged".')

        fight = EmojiFight(left, '⚔️', right, rigged=rigged)
        fight.perform_fight()
        for line in fight.output.get_clustered():
            await ctx.send(line)

    @commands.group('emoji_battle')
    async def emoji_battle(self, ctx: commands.Context):
        pass

    @emoji_battle.command('start')
    @command_with_signature(
        name = Par(str, 'the big fight'),
        contestants = Par(str, None),
    )
    async def emoji_battle_start(self, ctx: commands.Context, *, name: str, contestants: str):
        contestants = [c.strip() for c in contestants.split(",")]
        await ctx.send(f'## EMOJI BATTLE "{name.upper()}"\n### Contestants:')
        await ctx.send('  '.join(contestants))

        battle = EmojiBattle(name, contestants)

        global EMOJI_BATTLES, CURRENT_BATTLE
        EMOJI_BATTLES[name.lower()] = battle
        CURRENT_BATTLE = battle

    @emoji_battle.command("status")
    @command_with_signature(
        name = Par(str, None, required=False),
    )
    async def emoji_battle_status(self, ctx: commands.Context, name):
        global EMOJI_BATTLES, CURRENT_BATTLE
        battle = EMOJI_BATTLES[name.lower()] if name else CURRENT_BATTLE
        CURRENT_BATTLE = battle

        output = EmojiOutput()

        output.add_text(f'## Status of {battle.name}:')
        if battle.winners:
            output.add_text('### Victors:')
            output.add_emoji('  '.join(battle.winners))
        if battle.competing:
            output.add_text('### Still competing:')
            output.add_emoji('  '.join(battle.competing))
        if battle.losers:
            output.add_text('### Losers:')
            output.add_emoji('  '.join(battle.losers))

        if battle.current_round_state == 'started' and battle.current_round_message:
            output.add_text(f'A battle is currently ongoing, vote for it here: {battle.current_round_message.jump_url} !')

        for line in output.get_clustered():
            await ctx.send(line)

    @emoji_battle.command("round")
    @command_with_signature(
        name = Par(str, None, required=False),
    )
    async def emoji_battle_round(self, ctx: commands.Context, name):
        global EMOJI_BATTLES, CURRENT_BATTLE
        battle = EMOJI_BATTLES[name.lower()] if name else CURRENT_BATTLE
        CURRENT_BATTLE = battle

        battle.next_round()

        if battle.current_solo:
            # CASE: Solo
            await ctx.send('**One contestant remains, decide their fate:**')
            message = battle.current_round_message = await ctx.send(f"{battle.current_solo}")
            await message.add_reaction('☮️')
            await message.add_reaction('☠')

        else:
            # CASE: Duel
            await ctx.send('**Two contestants emerge, decide who survives:**')
            message = battle.current_round_message = await ctx.send(f"{battle.current_left}:vs:{battle.current_right}")
            try: await message.add_reaction(battle.current_left)
            except: await message.add_reaction('⬅️')
            await message.add_reaction('☮️')
            try: await message.add_reaction(battle.current_right)
            except: await message.add_reaction('➡️')

    @emoji_battle.command("call")
    @command_with_signature(
        name = Par(str, None, required=False),
    )
    async def emoji_battle_call(self, ctx, name):
        global EMOJI_BATTLES, CURRENT_BATTLE
        battle = EMOJI_BATTLES[name.lower()] if name else CURRENT_BATTLE
        CURRENT_BATTLE = battle

        if battle.current_round_state != 'started':
            return await ctx.send('This battle has no round to call.')

        battle.current_round_state = 'done'
        # Re-fetch message to update the Reactions
        message = battle.current_round_message = await battle.current_round_message.fetch()
        output = EmojiOutput()

        if battle.current_solo:
            live_votes = count_reactions(message.reactions, '☮️') - 1
            die_votes = count_reactions(message.reactions, '☠') - 1
            if die_votes > live_votes:
                output.add_text(f'**The tally is clear: This contestant dies!**')
                output.add_emoji(f'{battle.current_solo}\n:boom:\n:coffin:')
                battle.losers.append(battle.current_solo)
            else:
                output.add_text('**The tally is clear: This contestant lives!**')
                output.add_emoji(f':sparkles:{battle.current_solo}:sparkles:')
                battle.winners.append(battle.current_solo)

        else:
            left_votes = count_reactions(message.reactions, battle.current_left, '⬅️') - 1
            tie_votes = count_reactions(message.reactions, '☮️') - 1
            right_votes = count_reactions(message.reactions, battle.current_right, '➡️') - 1
            fight = EmojiFight(battle.current_left, '⚔️', battle.current_right)

            if tie_votes >= left_votes and tie_votes >= right_votes:
                output.add_text('**The tally is clear: Both contestants win!**')
                fight.rigged = 'both'
                battle.winners.append(battle.current_left)
                battle.winners.append(battle.current_right)
            elif left_votes == right_votes:
                output.add_text('**The tally is clear: Both contestants live to die another day!**')
                fight.rigged = 'both'
                battle.competing.append(battle.current_left)
                battle.competing.append(battle.current_right)
            elif left_votes > right_votes:
                output.add_text('**The tally is clear: The left contestant wins!**')
                fight.rigged = 'left'
                battle.competing.append(battle.current_left)
                battle.losers.append(battle.current_right)
            elif left_votes < right_votes:
                output.add_text('**The tally is clear: The right contestant wins!**')
                fight.rigged = 'right'
                battle.losers.append(battle.current_left)
                battle.competing.append(battle.current_right)

            # TODO: Refactor/optimize so non-emoji and emoji-lines are bundled in one message
            fight.perform_fight()
            output += fight.output

        if len(battle.competing) == 0:
            output.add_text(f'## ...and with that, {battle.name} ends!')
            if battle.winners:
                output.add_text('### Victors:')
                output.add_emoji('  '.join(battle.winners))
            if battle.losers:
                output.add_text('### Losers:')
                output.add_emoji('  '.join(battle.losers))

            del EMOJI_BATTLES[battle.name.lower()]
            CURRENT_BATTLE = None

        for line in output.get_clustered():
            await ctx.send(line)


async def setup(bot):
    await bot.add_cog(EmojiFightCommands(bot))