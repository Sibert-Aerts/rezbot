# Adapted from https://github.com/jh69/biogenerator
# Credit to Jon Hendren (@fart)

from .rand import choose, chance
from .texttools import camel_case

thing = ['Coffee','Doctor Who','Football','Sports','Baseball','Cigar',
'Tabletop Gaming', 'Settlers of Catan','Video Games','Video Poker',
'Blackjack','Gambling','True Detective','Breaking Bad',
'Mens Rights','Pizza','Caffeine','Craft Beer','Eczema','Anti-Vaccine',
'Conservative','Constitution','Bible','Christ','Gun Rights','Pro-Life',
'Bodybuilding','Oxycodone','Xanax','Wine','Whiskey','Liquor','Anime',
'Miyazaki','Bukowski','Hitler','Hunting','White Nationalist','Bugchaser',
'Weird Twitter','Marijuana','Dog','Cat','JRPG','Arson','Libertarian','Dawkins',
'Poly','Steampunk','Veteran','Egalitarian','Politics','SJW','Gamergate',
'Star Wars','Bernie Sanders','Hillary Clinton','Donald Trump','Craft Whiskey',
'Brunch','NASCAR','America','Ferret','Rat','Open Source','Ruby','Netflix',
'Gout','Chagas','Horse','Comedy','Favstar','420','2A','Open Carry','Marketing',
'Social Media','LinkedIn','Networking','Travel']

modifier = ['Fan','CEO','Guy','Dad','Liker','Enjoyer','Appreciator','Fanatic','Lover',
'Guru','Fetishist','Obsessive','Blogger','Writer','Parent','Man','Dude',
'Junkie','Addict','Snob','Aficionado','Nerd','Geek','Freak','Enthusiast','Admirer','Fiend','Hound','Expert','Critic','Nut','Maven','Savant','Zealot',
'Follower','Influencer','Evangelist']

disclaimers = ['I am very random','RTs are not endorsements',
'Opinions are my own','Opinions do not reflect those of my employer',
'Just here to talk %', 'Business inquiries? DM me.']

def get():
	string = ''
	for _ in range(20):
		if chance(0.3):
			string += choose(thing) + ' ' + choose(modifier) + '. '
		else:
			string += choose(thing) + '. '
		
		if len(string) > 70:
			if chance(0.2):
				string += choose(disclaimers).replace('%', choose(thing)) + '. '
		if len(string) > 100:
			string += '#' + camel_case(choose(thing))
			return string