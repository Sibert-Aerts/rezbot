from .pipe_decorations import *
from utils.texttools import *
from utils.rand import *
import utils.soapstone as soapstone

# Add fields here to make them easily accessible (readable and writable) both inside and outside of this file.
class SourceResources:
    previous_pipe_output = ['Nothing here']
    bot = None

#####################################################
#                      Sources                      #
#####################################################

@make_source({
    'test': Sig(str, 'DEFAULT', 'A test string inserted into the message!'),
    'n': Sig(int, 1, 'amount of times the message is repeated')
}, command=True)
def test_source(test, n):
    '''(A test source)'''
    return ['This is a test! {}!'.format(test) for _ in range(n)]


@make_source({})
def prev_source():
    '''The previous pipe outputs.'''
    return SourceResources.previous_pipe_output


@make_source({}, pass_message=True)
def that_source(message):
    '''The contents of the previous message in the channel.'''
    msg = [m for m in SourceResources.bot.messages if m.channel == message.channel][-2]
    return [msg.content]


@make_source({
    'n': Sig(int, 1, 'The amount of random words')
}, command=True)
def random_source(n):
    '''One or more random words from the dictionary.'''
    return [choose(allWords) for i in range(n)]


@make_source({
    'pattern': Sig(str, None, 'The pattern to look for (regex)'),
    'n'      : Sig(int, 1, 'The number of sampled words.')
}, command=True)
def find_source(pattern, n):
    '''Find random words in the dictionary matching a regex pattern.'''
    pattern = re.compile(pattern)
    items = [w for w in allWords if pattern.search(w) is not None]
    return random.sample(items, min(n, len(items)))


@make_source({
    'game': Sig(str, '?', 'Which Dark Souls game should be used (? for random).', lambda x:x in ['?','1','2','3']),
    'phrase': Sig(str, '%phrase%', 'Overrides game argument: Construct a custom phrase using the following categories:\n{}'.format(', '.join([c for c in soapstone.phraseDict])))
}, command=True)
def soapstone_source(game, phrase):
    '''Generate a randomised Dark Souls soapstone message.'''
    if phrase != '%phrase%':
        return [soapstone.makePhrase(phrase)]
    if game == '?':
        game = choose(['1','2','3'])
    if game == '1':
        return [soapstone.DarkSouls1.get()]
    if game == '2':
        return [soapstone.DarkSouls2.get()]
    if game == '3':
        return [soapstone.DarkSouls3.get()]