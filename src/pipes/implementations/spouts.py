from typing import TypeVar

# NOTE: Unused imports here are so our submodules can import them
from pipes.core.signature import Par, Signature, get_signature, with_signature
from pipes.core.pipe import Spout, Spouts
from pipes.core.state.context import Context

#######################################################
#                     Decorations                     #
#######################################################

NATIVE_SPOUTS = Spouts()
'The canonical object storing/indexing all `Spout` instances.'

_SPOUT_CATEGORY = 'NONE'

def set_category(category: str):
    global _SPOUT_CATEGORY
    _SPOUT_CATEGORY = category

def spout_from_func(signature: dict[str, Par]=None, /, *, command=False, **kwargs):
    '''Makes a Spout out of a function.'''
    func = None
    if callable(signature):
        (func, signature) = (signature, None)

    def _spout_from_func(func):
        global NATIVE_SPOUTS, _SPOUT_CATEGORY
        # Name is the function name with the _spout bit cropped off
        name = func.__name__.rsplit('_', 1)[0].lower()
        doc = func.__doc__
        # Signature may be set using @with_signature, given directly, or not given at all
        sig = get_signature(func, Signature(signature or {}))
        spout = Spout(sig, func, name=name, doc=doc, category=_SPOUT_CATEGORY, **kwargs)
        NATIVE_SPOUTS.add(spout, command)
        return func

    if func: return _spout_from_func(func)
    return _spout_from_func

T = TypeVar('T')

def spout_from_class(cls: type[T]) -> type[T]:
    '''
    Makes a Spout out of a class by reading its definition, and either the class' or the method's docstring.
    ```py
    # Fields:
    name: str
    aliases: list[str]=None
    command: bool=False
    mode: Spout.Mode=Spout.Mode.functional

    # Methods:
    @with_signature(...)
    @staticmethod
    def spout_function(bot, ctx: Context, items: list[str], **kwargs) -> list[str]: ...

    @staticmethod
    def may_use(user: discord.User) -> bool: ...
    ```
    '''
    def get(key, default=None):
        return getattr(cls, key, default)

    spout = Spout(
        get_signature(cls.spout_function),
        cls.spout_function,
        mode=get('mode'),
        name=cls.name,
        doc=cls.__doc__ or cls.spout_function.__doc__,
        category=_SPOUT_CATEGORY,
        aliases=get('aliases'),
        may_use=get('may_use'),
    )
    NATIVE_SPOUTS.add(spout, get('command', False))
    return cls


#######################################################
#                        Spouts                       #
#######################################################

from . import spouts_print
from . import spouts_message
from . import spouts_embed
from . import spouts_interact
from . import spouts_state
from . import spouts_meta