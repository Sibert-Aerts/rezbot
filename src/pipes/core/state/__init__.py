'''
Objects representing and containing various kinds of state as handled by pipes scripts.

Aside from type-checking there are no dependencies from the state submodule on the rest of the pipes.core module.
'''
from .bot_state import BOT_STATE
from .error_log import ErrorLog
from .context import Context, ContextError
from .item_scope import ItemScope, ItemScopeError
from .spout_state import SpoutState