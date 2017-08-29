from random import choice

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
        phrase = choice(DarkSouls1.phrases)
        if phrase.find('%') > -1:
            phrase = phrase.replace('%', choice(choice(DarkSouls1.categories)))
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
        phrase = choice(DarkSouls2.phrases)
        while phrase.find('%') > -1:
            phrase = phrase.replace('%', choice(DarkSouls2.subPhrases), 1)
        while phrase.find('$') > -1:
            phrase = phrase.replace('$', choice(choice(DarkSouls2.categories)), 1)
        while phrase.find('£') > -1:
            phrase = phrase.replace('£', choice(choice(DarkSouls2.categories + [DarkSouls2.musings])), 1)
        return phrase