import re

from .rand import *

def removeBrackets(str):
    return re.sub('[()]', '', str)

def removeBracketed(str):
    return re.sub('\([^)]*\)', '', str)

def sentenceCase(str):
    return str[0].upper() + str[1:]

class Meal:

    adjectives = ['warme', 'koude', 'sappige', 'BBQ', 'frisse', 'gefrituurde', 'gebakken', 'gegrilde',
                  'gewokte', 'gebraden', 'vegetarische', 'veganistische', 'gepaneerde', 'bevroren', 'rauwe',
                  'opgewarmde', 'gevulde', 'gestoofde', 'gestoomde', 'krokante', 'malse', 'knapperige',
                  ]

    weirdAdjectives = ['gesmolten', 'vloeibare', 'verbrande', 'gevallen', 'vergeten', 'eetbare', 'platte',
                       'verloren', 'zelfgemaakte', 'pescetarische', 'vierkantige', 'ronde',
                       ]

    origins = ['Belgische', 'Duitse', 'Franse', 'Spaanse', 'Florentijnse', 'Italiaanse', 'Koreaanse', 'Japanse', 'Amerikaanse',
               'Europeese', 'Waalse', 'Vlaamse', 'Brusselse', 'Zweedse', 'Finse', 'Russische', 'Deense', 'Nederlandse', 'Thaïse',
               'provençaalse'
               ]

    ingredients = ['spaghetti', 'pasta', 'water', 'vlees', 'ham', 'kebab', 'brood', 'baguette', 'risotto', 'rijst',
                   'tagliatelli', 'spinazie', 'aardappel', 'lam(s)', 'varken(s)', 'broccoli', 'appel', 'peer(en)',
                   'zuurkool', 'koffie', 'kip(pen)', 'groente(n)', 'ajuin', 'courgette(n)', 'quinoa', 'bolognaise', 'wok', 'scampi',
                   'tomaten', 'komkommer', 'augurk(en)', 'bloemkool', 'geit(en)', 'aubergine', 'tofu', 'zalm', 'ei(er)', 'kabeljauw',
                   'kaas', 'ricotta', 'parmezaan', 'vermicelli', 'cannelloni', 'gevogelte', 'dragon', 'kruiden',
                   ]

    weirdIngredients = ['vogel', 'blad(er)', 'gras', 'soepgroentjes', 'plant(en)', 'deeg', 'restjes', 'hot-dog', 'frikandel',
                        'kipknots(en)', 'nasi', 'bami', 'boullion', 'mayonnaise', 'ketchup', 'mosterd', 'boter',
                        ]

    types = ['schotel', 'burger', 'soep', 'verrassing', 'mengsel', 'puree', 'saus', 'balletjes', 'roll', 'broodje', 'wrap',
             'soufflé', 'pastij', 'quiche', 'gebraad', 'saté', 'schijfjes', 'blokjes', 'toefjes', 'wedges', 'frietjes', 'steak',
             'koteletten', 'worst', 'worstjes', 'pasta', 'festijn', 'slatje', 'brochette', 'nootjes',
             ]

    weirdTypes = ['mislukking', 'vergissing', 'mysterie', 'misdaad', 'ziekte', 'voedsel', 'maaltijd', 'ding',
                  'vlees', 'chips', 'vervanger', 'sap', 'taart', 'knots', 'vingers', 'nuggets', 'koek',
                  ]

    def generate(weird=False):
        str = ''
        something = False

        weird = weird or chance(0.1)

        origins = Meal.origins
        adjectives = Meal.adjectives + (Meal.weirdAdjectives if weird else [])
        ingredients = Meal.ingredients + \
            (Meal.weirdIngredients if weird else [])
        types = Meal.types + (Meal.weirdTypes if weird else [])

        if chance(0.2) or (weird and chance(0.1)):
            str += choose(origins) + ' '
            something = True

        if chance(0.3) or (weird and chance(0.2)):
            str += choose(adjectives) + ' '
            something = True

        str += choose(ingredients)

        if chance(0.5) or (not something and chance(0.5)) or (weird and chance(0.3)):
            str = removeBrackets(str)
            str += choose(types)
        else:
            str = removeBracketed(str)

        if chance(0.2) or (weird and chance(0.2)):
            str += ' met '
            str += choose(ingredients)
            if chance(0.5):
                str = removeBrackets(str)
                str += choose(types)
            else:
                str = removeBracketed(str)

        if chance(0.1) or (weird and chance(0.1)):
            str += ' op ' + choose(origins) + ' wijze'

        return sentenceCase(str)

    def generateMenu(type):
        s = '**Lunch Today:**\n'

        listItems = [':tea:', ':tomato:', ':poultry_leg:', ':meat_on_bone:', ':spaghetti:']
        for item in listItems:
            s += item + ' ' + Meal.generate(type == 'weird') + '\n'

        return s