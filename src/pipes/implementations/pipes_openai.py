from configparser import ConfigParser

from .pipes import make_pipe, one_to_many, set_category
from ..signature import Par
from utils.util import parse_bool
import permissions


#####################################################
#                   Pipes : OPENAI                  #
#####################################################
set_category('OPENAI')

_is_openai_usable = False
def openai_setup():
    global openai, _is_openai_usable
    try: import openai
    except: return print('Could not import Python module `openai`, OpenAI-related features will not be available.')

    config = ConfigParser()
    config.read('config.ini')
    openai_api_key = config['OPENAI']['api_key']
    if not openai_api_key or openai_api_key == 'PutYourKeyHere':
        return print('OpenAI API key not set in config.ini, OpenAI-related features will not be available.')
    openai.api_key = openai_api_key
    _is_openai_usable = True

openai_setup()

@make_pipe({
    'n':                Par(int, 1, 'The amount of completions to generate.'),
    'max_tokens':       Par(int, 50, 'The limit of tokens to generate per completion, includes prompt.'),
    'temperature':      Par(float, .7, 'Value between 0 and 1 determining how creative/unhinged the generation is.'),
    'model':            Par(str, 'ada', 'The GPT model to use, generally: ada/babbage/curie/davinci.'),
    'presence_penalty': Par(float, 0, 'Value between -2 and 2, positive values discourage reusing already present words.'),
    'frequency_penalty':Par(float, 0, 'Value between -2 and 2, positive values discourage reusing frequently used words.'),
    'stop':             Par(str, None, 'String that, if generated, marks the immediate end of the completion.', required=False),
    'prepend_prompt':   Par(parse_bool, True, 'Whether to automatically prepend the input prompt to each completion.'),
    },
    may_use=lambda user: permissions.has(user.id, permissions.trusted),
    command=True,
)
@one_to_many
def gpt_complete_pipe(text, prepend_prompt, **kwargs):
    '''
    Generate a completion to the individual given inputs.
    Uses OpenAI GPT models.
    '''
    if not _is_openai_usable: return [text]

    response = openai.Completion.create(prompt=text, **kwargs)
    completions = [choice.text for choice in response.choices]
    if prepend_prompt:
        completions = [text + completion for completion in completions]
    return completions

@make_pipe({
    'instruction':  Par(str, None, 'The instruction that tells the model how to edit the prompt.'),
    'n':            Par(int, 1, 'The amount of completions to generate.'),
    'temperature':  Par(float, .7, 'Value between 0 and 1 determining how creative/unhinged the generation is.'),
    'model':        Par(str, 'text-davinci-edit-001', 'The GPT model to use, either text-davinci-edit-001 or code-davinci-edit-001.'),
    },
    may_use=lambda user: permissions.has(user.id, permissions.trusted)
)
@one_to_many
def gpt_edit_pipe(text, **kwargs):
    '''
    Edit the given input according to an instruction.    
    Uses OpenAI GPT models.
    '''
    if not _is_openai_usable: return [text]

    response = openai.Edit.create(input=text, **kwargs)
    return [choice.text for choice in response.choices]
