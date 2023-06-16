from configparser import ConfigParser
import discord

from .pipes import pipe_from_class, one_to_many, set_category
from ..signature import Par, with_signature
from utils.util import parse_bool
import permissions


#####################################################
#                   Pipes : OPENAI                  #
#####################################################
set_category('OPENAI')

_is_openai_usable = False

def openai_setup():
    global openai, _is_openai_usable

    # Attempt import
    try: import openai
    except: return print('Could not import Python module `openai`, OpenAI-related features will not be available.')

    # Attempt read API key from config
    config = ConfigParser()
    config.read('config.ini')
    openai_api_key = config['OPENAI']['api_key']
    if not openai_api_key or openai_api_key == 'PutYourKeyHere':
        return print('OpenAI API key not set in config.ini, OpenAI-related features will not be available.')

    openai.api_key = openai_api_key
    _is_openai_usable = True

openai_setup()

@pipe_from_class
class PipeGPTComplete:
    name = 'gpt_complete'
    aliases = ['gpt_extend']
    command = True

    def may_use(user: discord.User):
        return permissions.has(user.id, permissions.trusted)

    @with_signature(
        n                 = Par(int, 1, 'The number of completions to generate.', check=lambda n: n <= 10),
        max_tokens        = Par(int, 50, 'The limit of tokens to generate per completion, does not include prompt.'),
        temperature       = Par(float, .7, 'Value between 0 and 2 determining how creative/unhinged the generation is.'),
        model             = Par(str, 'ada', 'The GPT model to use, generally: ada/babbage/curie/davinci.'),
        presence_penalty  = Par(float, 0, 'Value between -2 and 2, positive values discourage reusing already present words.'),
        frequency_penalty = Par(float, 0, 'Value between -2 and 2, positive values discourage reusing frequently used words.'),
        stop              = Par(str, None, 'String that, if generated, marks the immediate end of the completion.', required=False),
        prepend_prompt    = Par(parse_bool, True, 'Whether to automatically prepend the input prompt to each completion.'),
    )
    @one_to_many
    @staticmethod
    def pipe_function(text, prepend_prompt, **kwargs):
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


@pipe_from_class
class PipeGPTEdit:
    name = 'gpt_edit'

    @staticmethod
    def may_use(user: discord.User):
        return permissions.has(user.id, permissions.trusted)

    @with_signature(
        instruction = Par(str, None, 'The instruction that tells the model how to edit the prompt.'),
        n           = Par(int, 1, 'The amount of completions to generate.'),
        temperature = Par(float, .7, 'Value between 0 and 1 determining how creative/unhinged the generation is.'),
        model       = Par(str, 'text-davinci-edit-001', 'The GPT model to use, either text-davinci-edit-001 or code-davinci-edit-001.'),
    )
    @one_to_many
    @staticmethod
    def pipe_function(text, **kwargs):
        '''
        Edit the given input according to an instruction.    
        Uses OpenAI GPT models.
        '''
        if not _is_openai_usable: return [text]

        response = openai.Edit.create(input=text, **kwargs)
        return [choice.text for choice in response.choices]
