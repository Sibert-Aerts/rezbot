from .rand import choose

Bene  = [   'Bene','Bendy','Badger','Bumble','Blowhole','Brando','Band-Aid','Bunga',
            'Bonga','Bongo','Blackbeard','Blackboard','Blackman','Bender','Barter','Bullet',
            'Bismol','Balder','Borno','Belgium','Belland','Boobie','Butthole','Bazing','Blubber',
            'Billy','Barney','Belly','Bello','Bulldog','Barnhouse','Bathhouse','Bulboid','Bully',
            'Banker','Butter','Bluffer','Bulger','Burglar','Blimper','Binder','Boulder',
            'Buttfuck','Burnward','Blueballs','Bunny','Blaze-it-','Blazing','Blowing','Blowjob',
            'Boobjob','Breaststroke','Bangle','Bauble','Bubble','Brittle','British','Britain',
            'Briton','Breadbox','Brazil','Baghdad','Bangkok','Beijing','Berry','Benchpress',
            'Beirut','Belgrade','Berlin','Brussels','Better','Bedroom','Bury','Bedlam',
            'Beckham','Bedsore','Bedpiece','Bedlamp','Bedrock','Becker','Bedtime','Blaze-a-',
            'Bend-it-','Bend-a-'
        ]
Dict =  [   'dict','get','fuck','dick','pick','nick','quick','cake','lock','hack','frog', 'loch',
            'gook','narc','stark','bark','jerk','lurk','neck','flick','rick','hick','nig','brick',
            'bit','chit','nit','kit','mick','quit','lit','lid','bid','skid','fritte','lick',
            'snack','lack','frick','chick','lich','leech','croc','luck','chuck','rock','block',
            'black','slack','whack','kid','click','crick','kick','spick','thick','tic','trick','wick',
            'sick','schtick','snick','britt','fit','grit','hit','knit','mitt','pit','split','wit',
            'spit','slit','pritt','kids','hits','wits','picked','nicked','flicked','tricked','licked',
            'kicked'
        ]
Cumber =[   'Cumber','Cucumber','Christmas','Cartwheel','Cancelled','Corkscrew','Cancan','Carseat',
            'Catman','Crimson','Combat','Crowbar','Cosine','Crabhat','Kringle','Kettle','Crabcake',
            'Scatman','Quitter','Cutie','Cutter','Cutman','Cattail','Catpaw','Cumher','Kremlin',
            'Kremling','Croco','Cocoa','Contract','Catscan','Carpark','Cantine','Cardgame',
            'Caroll','Kelly','Kelvin','Kenny','Kevin','Carrey','Cutmy','Killmy','Kujo','Kinder',
            'Congo','Cuba','Quarter','Corner','Cardboard','Crowman','Country','Commute',
            'Collage','Colour','Combine','Covered','Cuban','Cuberoot','Cubic','Cueball',
            'Cupid','Cupric','Curate','Cubric','Cannon','Canon','Cardio','Callus','Candle',
            'Candy','College'
        ]
Batch = [   'batch','itch','bitch','butch','britch','fletch','brunch','blunt','bear','ball','bic',
            'snatch','catch','match','latch','fraîche','bridge','fridge','nudge','björk','patch',
            'crotch','botch','notch','bap','slatch','banks','balls','bill','mitch','midge',
            'bob','bert','bart','watch','stache','thatch','scratch','hat','hats','bib','bids',
            'bet','boat','bee','bulge','back','bad','band','bat','bag','bath','badge','bang',
            'bass','bash','babs','bangs','ban','baps','boob','boobs','breast','breasts','blam',
            'blem'
        ]

def generate():
    return choose(Bene) + choose(Dict) + ' ' + choose(Cumber) + choose(Batch)