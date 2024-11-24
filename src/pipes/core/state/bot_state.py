from collections import defaultdict
from resource.variables import VariableStore


class BotState():
    previous_pipeline_output: defaultdict[list]
    variables: VariableStore
    earmarked_messages: dict


BOT_STATE = BotState()
'''Magic global cross-script state object.'''

BOT_STATE.previous_pipeline_output = defaultdict(list)
BOT_STATE.variables = VariableStore('variables.json')
BOT_STATE.earmarked_messages = dict()
