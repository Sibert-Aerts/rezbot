from .rand import choose, chance
import re

class DarkSouls1:
    phrases = [
        '% ahead', 'Be wary of %', 'Try %', 'Need %', 'Imminent %...', 'Weakness: %', '%', '%?', 
        'Good luck', 'I did it!', 'Here!', 'I can\'t take this...', 'Praise the Sun!'
    ]

    characters = [
        'Enemy', 'Tough enemy', 'Hollow', 'Soldier', 'Knight', 'Sniper', 'Caster', 'Giant', 'Skeleton',
        'Ghost', 'Bug', 'Poison bug', 'Lizard', 'Drake', 'Flier', 'Golem', 'Statue', 'Monster', 'Strange creature',
        'Demon', 'Darkwraith', 'Dragon', 'Boss', 'Saint', 'Wretch', 'Charmer', 'Miscreant', 'Liar', 'Fatty',
        'Beanpole', 'Merchant', 'Blacksmith', 'Master', 'Prisoner'
    ]

    objects = [
        'Bonfire', 'Fog wall', 'Humanity', 'Lever', 'Switch', 'Key', 'Treasure', 'Chest', 'Weapon', 'Shield', 'Projectile', 'Armour', 
        'Item', 'Ring', 'Sorcery scroll', 'Pyromancy scroll', 'Miracle scroll', 'Ember', 'Trap', 'Covenant', 'Amazing key',
        'Amazing treasure', 'Amazing chest', 'Amazing weapon', 'Amazing armour', 'Amazing item', 'Amazing ring',
        'Amazing sorcery scroll', 'Amazing pyromancy scroll', 'Amazing miracle scroll', 'Amazing ember', 'Amazing trap'
    ]

    techniques = [
        'Close-ranged battle', 'Ranged battle', 'Eliminating one at a time', 'Luring it out', 'Beating to a pulp', 'Lying in ambush',
        'Stealth', 'Mimicry', 'Pincer attack', 'Hitting them in one swoop', 'Fleeing', 'Charging', 'Stabbing in the back',
        'Sweeping attack', 'Shield breaking', 'Head shots', 'Sorcery', 'Pyromancy', 'Miracles', 'Jumping off', 'Sliding down', 'Dashing through'
    ]

    actions = ['Rolling', 'Backstepping', 'Jumping', 'Attacking', 'Holding with both hands', 'Kicking', 'A plunging attack', 'Blocking', 'Parrying', 'Locking-on']

    geography = [
        'Path', 'Hidden path', 'Shortcut', 'Detour', 'Illusory wall', 'Shortcut', 'Dead end', 'Swamp', 'Lava', 'Forest', 'Cave', 'Labyrinth', 'Safe zone', 'Danger zone',
        'Sniper spot', 'Bright spot', 'Dark spot', 'Open area', 'Tight spot', 'Hiding place', 'Exchange', 'Gorgeous view', 'Fall'
    ]

    orientation = ['Front', 'Back', 'Left', 'Right', 'Up', 'Down', 'Feet', 'Head', 'Back']

    bodyParts = ['Head', 'Neck', 'Stomach', 'Back', 'Arm', 'Leg', 'Heel', 'Rear', 'Tail', 'Wings', 'Anywhere']

    attribute = [
        'Strike', 'Thrust', 'Slash', 'Magic', 'Fire', 'Lightning', 'Critical hits',
        'Bleeding', 'Poison', 'Strong poison', 'Curses', 'Divine', 'Occult', 'Crystal'
    ]

    concepts = [
        'Chance', 'Hint', 'Secret', 'Happiness', 'Sorrow', 'Life', 'Death', 'Undead', 'Elation', 'Grief', 'Hope', 'Despair', 'Light', 'Dark',
        'Bravery', 'Resignation', 'Comfort', 'Tears'
    ]

    categories = [characters, objects, techniques, actions, geography, orientation, bodyParts, attribute, concepts]

    def get():
        phrase = choose(DarkSouls1.phrases)
        if phrase.find('%') > -1:
            phrase = phrase.replace('%', choose(choose(DarkSouls1.categories)))
        return phrase

class DarkSouls2:
    phrases = ['%', '% and then %', '% but %', '% therefore %', '% in short %', '% or %', '% by the way %', '% , %']

    subPhrases = [
        '$ ahead', '$ required ahead', 'be wary of $', 'try $', 'weakness: $', 'visions of $...', '£', '£!', '£?', '£...', 'hurrah for $!'
    ]

    creatures = [
        'enemy', 'monster', 'lesser foe', 'tough enemy', 'boss', 'Hollow', 'skeleton', 'ghost', 'bug', 'Gyrm', 'beast', 'giant', 'dwarf', 'sniper', 'caster', 'duo',
        'trio', 'saint', 'wretch', 'charmer', 'poor soul', 'oddball', 'nimble one', 'laggard', 'moneybags', 'beggar', 'miscreant', 'liar', 'fatty', 'beanpole',
        'merchant', 'artisan', 'master', 'friend', 'ally', 'Dark Spirit', 'Phantom', 'Shade'
    ]

    objects = [
        'bonfire', 'fog wall', 'lever', 'switch', 'key', 'trap', 'torch', 'door', 'treasure', 'chest', 'something', 'quite something', 'weapon',
        'shield', 'projectile', 'armor', 'item', 'ring', 'scroll', 'ore', 'message', 'bloodstain', 'illusion'
    ]

    techniques = [
        'close-ranged battle', 'ranged battle', 'eliminating one at a time', 'luring it out', 'beating to a pulp', 'ambush', 'pincer attack',
        'hitting them in one swoop', 'dual-wielding', 'stealth', 'mimicry', 'fleeing', 'charging', 'jumping off', 'dashing through',
        'circling around', 'trapping inside', 'rescue', 'sorcery', 'pyromancy', 'miracles', 'hexes', 'pure luck', 'prudence', 'brief respite', 'play dead'
    ]

    actions = [
        'jog', 'dash', 'rolling', 'backstepping', 'jumping', 'attacking', 'jump attack', 'dash attack', 'counter attack', 'stabbing in the back',
        'guard stun & stab', 'parry stun & stab', 'plunging attack', 'sweeping attack', 'shield breaking', 'blocking', 'parrying', 'spell parry',
        'locking-on', 'no lock-on', 'two-handing', 'gesture', 'control', 'destroy'
    ]

    geography = [
        'boulder', 'lava', 'poison gas', 'enemy horde', 'forest', 'cave', 'arena', 'hidde path', 'detour', 'shortcut', 'dead end', 'labyrinth', 'hole',
        'bright spot', 'dark spot', 'open area', 'tight spot', 'safe zone', 'danger zone', 'sniper spot', 'hiding place', 'illusory wall', 'ladder',
        'lift', 'exchange', 'gorgeous view', 'looking away', 'overconfidence', 'slip-up', 'oversight', 'fatigue', 'bad luck', 'inattention', 'loss of stamina'
    ]

    orientation = ['front', 'back', 'left', 'right', 'up', 'down', 'below', 'above', 'behind']

    bodyParts = [
        'head', 'neck', 'stomach', 'back', 'arm', 'leg', 'rear', 'tail', 'wings', 'anywhere', 'tongue', 'right arm', 'left arm', 'right leg', 'left leg',
        'right side', 'left side', 'pincer', 'wheel', 'core', 'horse'
    ]

    attribute = [
        'strike', 'thrust', 'slash', 'magic', 'sorcery', 'fire', 'lightning', 'critical hits', 'bleeding', 'poison', 'toxic', 'curse', 'equipment breakage'
    ]

    concepts = [
        'chance', 'quagmire', 'hint', 'secret', 'happiness', 'misfortune', 'life', 'death', 'joy', 'sadness', 'tears', 'hope', 'despair', 'victory', 'defeat',
        'light', 'dark', 'bravery', 'overconfidence', 'vigor', 'revenge', 'resignation', 'overwhelming', 'regret', 'pointless', 'man', 'woman', 'recklessness',
        'composure', 'guts', 'comfort', 'silence'
    ]

    musings = [
        'good luck', 'fine work', 'I did it!', 'I\'ve failed...', 'here!', 'not here!', 'I can\'t take this...', 'don\'t you dare!', 'do it!', 'look carefully',
        'listen carefully', 'think carefully', 'this place again?', 'now the real fight begins', 'keep moving', 'pull back', 'give it up', 'don\'t give up',
        'help me...', 'impossible...', 'bloody expensive...', 'nice job', 'let me out of here...', 'stay calm', 'like a dream...', 'are you ready?', 'praise the Sun!'
    ]

    categories = [creatures, objects, techniques, actions, geography, orientation, bodyParts, attribute, concepts]

    def get():
        phrase = choose(DarkSouls2.phrases)
        while phrase.find('%') > -1:
            phrase = phrase.replace('%', choose(DarkSouls2.subPhrases), 1)
        while phrase.find('$') > -1:
            phrase = phrase.replace('$', choose(choose(DarkSouls2.categories)), 1)
        while phrase.find('£') > -1:
            phrase = phrase.replace('£', choose(choose(DarkSouls2.categories + [DarkSouls2.musings])), 1)
        return phrase


class DarkSouls3:
    phrases = [
        '% ahead', 'No % ahead', '% required ahead', 'be wary of %', 'try %', 'Could this be a %?', 'If only I had a %...',
        'visions of %... ', 'Time for %', '%', '%!', '%?', '%...', 'Huh. It\'s a %...', 'praise the %!', 'Let there be %', 'Ahh, %...'
    ]

    conjunctions = [' and then ', ' but ', ' therefore ', ' in short ', ' or ', ' only ', ' by the way ', ' so to speak ', ' all the more ', ', ']

    creatures = [
        'enemy', 'monster', 'mob enemy', 'tough enemy', 'critical foe', 'Hollow', 'pilgrim', 'prisoner', 'monstrosity', 'skeleton', 'ghost', 'beast', 'lizard',
        'bug', 'grub', 'crab', 'dwarf', 'giant', 'demon', 'dragon', 'knight', 'sellsword', 'warrior', 'herald', 'bandit', 'assassin', 'sorcerer', 'pyromancer',
        'cleric', 'deprived', 'sniper', 'duo', 'trio', 'you', 'you bastard', 'good fellow', 'saint', 'wretch', 'charmer', 'poor soul', 'oddball', 'nimble one',
        'laggard', 'moneybags', 'beggard', 'miscreant', 'liar', 'fatty', 'beanpole', 'youth', 'elder', 'old codger', 'old dear', 'merchant', 'artisan', 'master',
        'sage', 'champion', 'Lord of Cinder', 'king', 'queen', 'prince', 'princess', 'angel', 'god', 'friend', 'ally', 'spouse', 'covenantor', 'Phantom', 'Dark Spirit'
    ]

    objects = [
        'bonfire', 'ember', 'fog wall', 'lever', 'contraption', 'key', 'trap', 'torch', 'door', 'treasure', 'chest', 'something', 'quite something', 'rubbish',
        'filth', 'weapon', 'shield', 'projectile', 'armor', 'item', 'ring', 'ore', 'coal', 'transposing kiln', 'scroll', 'umbral ash', 'throne', 'rite',
        'coffin', 'cinder', 'ash', 'moon', 'eye', 'brew', 'soup', 'message', 'bloodstain', 'illusion'
    ]

    techniques = [
        'close-ranged battle', 'ranged battle', 'eliminating one at a time', 'luring it out', 'beating to a pulp', 'ambush', 'pincer attack',
        'hitting them in one swoop', 'dual-wielding', 'stealth', 'mimicry', 'fleeing', 'charging', 'jumping off', 'dashing through', 'circling around',
        'trapping inside', 'rescue', 'Skill', 'sorcery', 'pyromancy', 'miracles', 'pure luck', 'prudence', 'brief respite', 'play dead'
    ]

    actions = [
        'jog', 'dash', 'rolling', 'backstepping', 'jumping', 'attacking', 'jump attack', 'dash attack', 'counter attack', 'stabbing in the back',
        'guard stun & stab', 'plunging attack', 'sweeping attack', 'shield breaking', 'blocking', 'parrying', 'locking-on', 'no lock-on',
        'two-handing', 'gesture', 'control', 'destroy'
    ]

    geography = [
        'boulder', 'lava', 'poison gas', 'enemy horde', 'forest', 'swamp', 'cave', 'shortcut', 'detour', 'hidden path', 'secret passage', 'dead end',
        'labyrinth', 'hole', 'bright spot', 'dark spot', 'open area', 'tight spot', 'safe zone', 'danger zone', 'sniper spot', 'hiding place', 'illusory wall',
        'ladder', 'lift', 'gorgeous view', 'looking away', 'overconfidence', 'slip-up', 'oversight', 'fatigue', 'bad luck', 'inattention', 'loss of stamina',
        'chance encounter', 'planned encounter'
    ]

    orientation = ['front', 'back', 'left', 'right', 'up', 'down', 'below', 'above', 'behind']

    bodyParts = [
        'head', 'neck', 'stomach', 'back', 'arm', 'finger', 'leg', 'rear', 'tail', 'wings', 'anywhere', 'tongue', 'right arm', 'left arm', 'thumb',
        'indexfinger', 'longfinger', 'ringfinger', 'smallfinger', 'right leg', 'left leg', 'right side', 'left side', 'pincer', 'wheel', 'core', 'mount'
    ]

    attribute = [
        'regular', 'strike', 'thrust', 'slash', 'magic', 'crystal', 'fire', 'chaos', 'lightning', 'blessing', 'dark',
        'critical hits', 'bleeding', 'poison', 'toxic', 'frost', 'curse', 'equipment breakage'
    ]

    concepts = [
        'chance', 'quagmire', 'hint', 'secret', 'sleeptalk', 'happiness', 'misfortune', 'life', 'death', 'demise', 'joy', 'fury', 'agony',
        'sadness', 'tears', 'loyalty', 'betrayal', 'hope', 'despair', 'fear', 'losing sanity', 'victory', 'defeat', 'sacrifice', 'light', 'dark',
        'bravery', 'confidence', 'vigor', 'revenge', 'resignation', 'overwhelming', 'regret', 'pointless', 'man', 'woman', 'friendship',
        'love', 'recklessness', 'composure', 'guts', 'comfort', 'silence', 'deep', 'dregs'
    ]

    musings = [
        'good luck', 'fine work', 'I did it!', 'I\'ve failed...', 'here!', 'not here!', 'I can\'t take this...', 'lonely...', 'don\'t you dare!', 'do it!',
        'look carefully', 'listen carefully', 'think carefully', 'this place again?', 'now the real fight begins', 'you don\'t deserve this',
        'keep moving', 'pull back', 'give it up', 'don\'t give up', 'help me...', 'impossible...', 'bloody expensive...', 'let me out of here...',
        'stay calm', 'like a dream...', 'seems familiar...', 'are you ready?', 'it\'ll happen to you too', 'praise the Sun!', 'may the flames guide thee'
    ]
    
    categories = [creatures, objects, techniques, actions, geography, orientation, bodyParts, attribute, concepts, musings]

    def get():
        this = DarkSouls3
        phrase = choose(this.phrases).replace('%', choose(choose(this.categories)))
        if chance(0.9):
            phrase += choose(this.conjunctions) + choose(this.phrases).replace('%', choose(choose(this.categories)))
        return phrase

# Matches: group1%group2%group3
phrasePattern = re.compile(r'([^%]*)(%([^%]*)%([^%]*))?')

phraseDict = {
    'creature': DarkSouls1.characters + DarkSouls2.creatures + DarkSouls3.creatures,
    'object': DarkSouls1.objects + DarkSouls2.objects + DarkSouls3.objects,
    'technique': DarkSouls1.techniques + DarkSouls2.techniques + DarkSouls3.techniques,
    'action': DarkSouls1.actions + DarkSouls2.actions + DarkSouls3.actions,
    'geography': DarkSouls1.geography + DarkSouls2.geography + DarkSouls3.geography,
    'orientation': DarkSouls1.orientation + DarkSouls2.orientation + DarkSouls3.orientation,
    'body part': DarkSouls1.bodyParts + DarkSouls2.bodyParts + DarkSouls3.bodyParts,
    'attribute': DarkSouls1.attribute + DarkSouls2.attribute + DarkSouls3.attribute,
    'concept': DarkSouls1.concepts + DarkSouls2.concepts + DarkSouls3.concepts,
    'musing': DarkSouls2.musings + DarkSouls3.musings,
}

def makePhrase(phrase):
    out = ''
    for a, bc, b, c in re.findall(phrasePattern, phrase):
        out += a
        try:
            out += choose(phraseDict[b.lower()])
        except:
            if bc != '':
                out += '%' + b + '%'
        out += c
    return out