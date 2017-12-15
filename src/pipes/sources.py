from .pipe_decorations import *
from utils.texttools import *
from utils.rand import *

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
})
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
})
def random_source(n):
    '''One or more random words from the dictionary.'''
    return [choose(allWords) for i in range(n)]