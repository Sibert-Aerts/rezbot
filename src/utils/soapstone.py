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


class Bloodborne:
    phrases = [
        '%', 'fear %', 'remember %', 'time for %', 'it\'s the scourge of %', 'reeks of %', '% is effective', 'beware of %', 'treat % with care',
        'it is all thanks to %', 'despicable %', 'woeful %', 'wondrous %', 'nothing but % here', '% waits ahead', 'you must accept %',
        'have mercy, %', 'no mercy for %', 'have audience with %', 'reminiscent of %', 'oh, %!'
    ]

    stock_phrases = [
        'you\'ve come to the right place', 'bless us with blood', 'may the good blood guide your way', 'fear your blindness',
        'the sky and the cosmos are one', 'let us cleanse these foul streets', 'you\'re in the know, right?', 'oh, I can\'t wait... hee hee...',
        'take a step forward', 'turn back', 'those with faith will be spared', 'don\'t be fooled', 'pitiful, really', 'behind you',
        'don\'t you dare look at me!', 'sincerest thanks', 'a hunter is never alone', 'please, carry on in my stead', 'run!', 'don\'t give up!'
    ]

    conjunctions = [' and ', ' but ', ' or ', ' therefore ', ' eventually ', ', ']

    creatures = [
        'beast', 'man-beast', 'giant beast', 'abhorrent beast', 'infected one', 'foe', 'strong foe', 'giant foe', 'terrible foe',
        'hound', 'bird', 'snake', 'animal', 'insect', 'watcher', 'shaman', 'dead', 'foul spirit', 'the lost', 'malformed thing',
        'monster', 'unknown thing', 'slimy thing', 'blobby thing', 'kin of the cosmos', 'evil eye', 'false god', 'superior being', 'messenger', 'doll',
    ]

    humans = [
        'man', 'woman', 'elderly', 'ailing one', 'madman', 'keeper', 'mob', 'wheelchair', 'small gent', 'small lady', 'titan',
        'amazon', 'fatty', 'dullard', 'liar', 'scoundrel', 'child', 'friend', 'darling', 'master', 'infant', 'queen', 'yourself',
        'hunter', 'cooperator', 'adversary', 'executioner', 'vileblood', 'hunter of hunters', 'blood-addled hunter'
    ]

    tactics_a = [
        'physical attack', 'blunt attack', 'thrust attack', 'blood attack', 'arcane', 'fire', 'bolt', 'quick weapon', 'long weapon',
        'poison', 'frenzy', 'exploiting species', 'beast transformation', 'firearm', 'blunderbuss', 'torch', 'shield', 'rally',
        'charge attack', 'visceral attack', 'rolling', 'quickstep', 'blood vial', 'quicksilver bullet', 'medicine', 'special medicine',
        'projectile', 'oil', 'coarse paper', 'special item'
    ]

    tactics_b = [
        'ambush', 'pincer attack', 'sneak attack', 'patrol', 'reinforcements caller', '"focus on attacks"', '"focus on evasion"',
        '"focus on healing"', '"close-range fight"', '"long-range fight"', '"hit-and-run"', 'sniping', 'counter', '"attack from behind"',
        '"open when attacking"', '"strike and be struck"', '"kill in order"', '"kill first"', 'charging forth', 'lure', 'stealth', 'ignoring',
        'retreat', 'use of terrain', 'tight spot', 'high spot', 'fall', 'alertness', 'unbreakable will', 'leaden constitution'
    ]

    things = [
        'blood echoes', 'insight', 'bloodstone', 'blood gem', 'rune', 'ritual material', 'key', 'item', 'special item', 'paleblood',
        'message', 'rating', 'dead body', 'treasure', 'lever', 'statue', 'light', 'bonfire', 'footing', 'trap', 'yharnam', 'clinic',
        'grand cathedral', 'church', 'safe place', 'old labyrinth', 'workshop', 'healing church', 'hidden path', 'unseen village'
    ]

    concepts = [
        'hunting', 'night', 'dawn', 'blood', 'warm blood', 'scourge', 'life', 'nightmare', 'moon', 'cosmos', 'eye', 'oedon',
        'communion', 'donation', 'ritual', 'contact', 'encounter', 'evolution', 'oath', 'corruption', 'execution', 'cleansing',
        'prayer', 'curse', 'defilement', 'sinister', 'courage', 'respect', 'inquisitiveness', 'pity', 'grief', 'joy', 'wrath',
        'sanity', 'madness', 'fervor', 'seduction', 'feasting', 'tastiness', 'tonsil', 'metamorphosis', 'common sense', 'darkness',
        'secret', 'singing', 'sobbing', 'howling', '"all\'s well"', 'the unseen', 'all'
    ]
    
    categories = [creatures, humans, tactics_a, tactics_b, things, concepts]

    def get_phrase():
        if chance(0.8):
            return choose(Bloodborne.phrases).replace('%', choose(choose(Bloodborne.categories)))
        return choose(Bloodborne.stock_phrases)

    def get():
        this = Bloodborne
        phrase = this.get_phrase()
        if chance(0.8):
            phrase += choose(this.conjunctions) + this.get_phrase()
        return phrase

class Sekiro:
    phrases = [
        '%', '%...', 'might be %', 'hm. so it\'s a %', 'which means...%', '% you say...', '%...!', 'ought to be %...', 'surely not %...',
        'what is a %...?', '%...?', 'it\'s not a %', '%... I\'ll think about it', '%? I see...', 'in case of %...', 'perform %',
        'should try %', 'confront %', 'while %', 'avoid %', 'no need for %', 'the pinnacle of %', 'offer to %', 'for the sake of %',
        '% is recious...', 'surely, not %', 'code of %'
    ]
    conjunctions = [
        ' and ', ' because ', ' all the more ', ' therefore ', ' but ', ' is ', ' in short ', ' that is to say ', ' or ',
        ' also ', ' however ', ' if ', ' then ', ' by the way ', ' as it were ', ', '
    ]

    people = [
        'divine child', 'divine heir', 'Kuro', 'Lord Kuro', 'sculptor', 'physician', 'memorial mob', 'peddler', 'Wolf',
        'Sekiro', 'I', 'me', 'you', 'equal', 'superior', 'comrade', 'pious one', 'villain', 'forlorn', 'misfit', 'graceful one',
        'swift', 'straggler', 'brute', 'mule', 'horror', 'moneybags', 'vagabond', 'deserter', 'cheat', 'fiend', 'youth', 'man',
        'woman', 'elder', 'geezer', 'hag', 'master', 'friend', 'ally', 'lord', 'parent', 'foster father', 'child'
    ]

    enemies = [
        'enemy', 'foe', 'worthy opponent', 'extraordinary foe', 'shinobi', 'bandit', 'villager', 'Ashina clan', 'sniper',
        'fencer', 'warrior', 'seeker', 'beast', 'hound', 'monkey', 'serpent', 'insect', 'parasite', 'gamefowl', 'monster',
        'spirit', 'apparition', 'infested', 'undying', 'demon', 'shura'
    ]

    objects = [
        'sculptor\'s idol', 'offering box', 'treasure', 'chest', 'mechanism', 'tatami mat', 'under the floor', 'door', 'key',
        'trap', 'sen', 'katana', 'shinobi prosthetic', 'prosthetic tool', 'item', 'valuable item', 'material', 'gourd', 'sugar',
        'balloon', 'spirit emblem', 'document', 'blood', 'rice', 'sake', 'prayer bead', 'prayer necklace', 'memory', 'remnant'
    ]

    tactics = [
        'swordplay', 'projectile', 'mid-air battle', 'stealth', 'reconnaisance', 'taking them one by one', 'luring out',
        'ambushing', 'pincer attack', 'taking them all at once', 'fleeing', 'charging', 'jumping off', 'sprinting through',
        'flanking', 'leaving to fate', 'caution', 'distracting', 'controlling', 'stripping away', 'feigning death'
    ]

    techniques = [
        'movement', 'sprinting', 'grappling hook', 'jumping', 'crouching', 'jump kick', 'attacking', 'sweep attack',
        'grab attack', 'thrust attack', 'counter-slash attack', 'shinobi deathblow', 'backstab deathblow', 'plunging deathblow',
        'guard', 'deflecting', 'consecutive deflects', 'mikiri counter', 'evasion', 'ledge hang', 'wall hug', 'peeking', 'swimming', 'eavesdropping'
    ]

    locations = [
        'castle keep', 'outskirts', 'village', 'rooftop', 'hallway', 'stairs', 'temple', 'valley', 'cliff', 'abyss', 'mountain path', 'forest',
        'treetop', 'swamp', 'cave', 'tall grass', 'underwater', 'water surface', 'mid-air', 'shortcut', 'detour', 'hidden path', 'escape route',
        'dead end', 'bright place', 'dark place', 'open place', 'cramped place', 'safe area', 'dangerous area', 'ladder', 'stunning view',
        'oversight', 'misfortune', 'carelessness', 'encounter', 'enemy group', 'lone enemy', 'enemy patrol', 'training'
    ]

    orientations = ['front', 'back', 'left', 'right', 'up', 'down', 'below', 'above', 'behind', 'ahead']

    attributes = [
        'poison', 'burn', 'terror', 'shock', 'enfeeblement', 'forbidden', 'sinister burden', 'slash attacks',
        'blunt attacks', 'thrust attacks', 'ranged attacks', 'flame', 'apparition', 'posture'
    ]

    concepts = [
        'fighting chance', 'escape', 'perilous pass', 'certain death', 'secret', 'gibberish', 'bliss', 'misery',
        'life', 'death', 'wrath', 'pain', 'sadness', 'loyalty', 'betrayal', 'cowardice', 'hope', 'fear', 'victory',
        'defeat', 'sacrifice', 'risk one\'s life', 'relief', 'vigor', 'resignation', 'critical moment', 'regret',
        'futility', 'friendship', 'love', 'abandon', 'composure', 'persistence', 'solace', 'quiet', 'depth', 'stagnation',
        'strength', 'speed', 'toughness', 'skill', 'hatred', 'revenge', 'repayment', 'auspicious', 'foreboding', 'panic',
        'hesitation', 'comfort', 'blink', 'short', 'long', 'beautiful', 'hideous'
    ]

    musings = [
        'well done', 'I\'ve done it', 'regretful...', 'here...', 'not here...', 'no turning back...', 'enough', 'look carefully',
        'listen carefully', 'think carefully', 'this place again...', 'this is it', 'is this a trick...?', 'go', 'go back', 'give up',
        'stay strong', 'impossible...', 'so high up...', 'so deep...', 'keep calm...', 'an illusion...', 'nostalgic...',
        'prepare yourself...', 'you\'ll know it when you see it', 'as you command', 'face me', 'I don\'t mind', 'yes', 'no',
        'what...?', 'alright', 'I cannot', 'I cannot say', 'forgive me', 'I don\'t think', 'you have my gratitude',
        'farewell', 'do what must be done', 'I will lose', '........'
    ]
    
    words = [people, enemies, objects, tactics, techniques, locations, orientations, attributes, concepts, musings]

    def get():
        this = Sekiro
        phrase = choose(this.phrases).replace('%', choose(choose(this.words)))
        if chance(0.9):
            phrase += choose(this.conjunctions) + choose(this.phrases).replace('%', choose(choose(this.words)))
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