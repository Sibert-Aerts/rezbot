import re
import itertools
from typing import Callable, Type

from discord import Interaction
from discord.app_commands import Choice

from pipes.core.pipe import Pipeoid, Pipe, Source, Spout, Pipes, Sources, Spouts
from pipes.implementations.pipes import pipes
from pipes.implementations.sources import sources
from pipes.implementations.spouts import spouts
from pipes.core.macros import Macros, Macro, pipe_macros, source_macros
from pipes.core.events import Event, Events, OnMessage, OnReaction, OnInvoke, events
from .macro_commands import check_pipe_macro, check_source_macro
from utils.util import normalize_name


# ====================================== Scriptoid mappings =======================================

scriptoid_type_map: dict[str, Pipes|Sources|Spouts|Macros|Events]  = {
    'Pipe': pipes,
    'Source': sources,
    'Spout': spouts,
    'Pipe_macro': pipe_macros,
    'Source_macro': source_macros,
    'Event': events,
}

macro_check_map: dict[str, Callable] = {
    'Pipe': check_pipe_macro,
    'Source': check_source_macro,
}

event_type_map: dict[str, Type[OnMessage|OnReaction|OnInvoke]] = {
    'OnMessage': OnMessage,
    'OnReaction': OnReaction,
    'OnInvoke': OnInvoke,
}


# ===================================== Autocomplete utility ======================================

def scriptoid_to_choice(scriptoid: Pipeoid|Macro|Event, channel=None):
    # This could be class methods but it's only used in this one file
    # and it is much nicer to have all the implementations laid out right here.
    if isinstance(scriptoid, Pipeoid):
        # name  = 'pipe_name (PipeType)'
        # value = 'PipeType:pipe_name'
        type_name = type(scriptoid).__name__
        name = f'{scriptoid.name} ({type_name})'
        value = f'{type_name}:{scriptoid.name}'
        return Choice(name=name, value=value)

    if isinstance(scriptoid, Macro):
        # name  = 'macro_name (Kind Macro)'
        # value = 'Kind_macro:macro_name'
        name = f'{scriptoid.name} ({scriptoid.kind} Macro)'
        value = f'{scriptoid.kind}_macro:{scriptoid.name}'
        return Choice(name=name, value=value)

    if isinstance(scriptoid, Event):
        # name  = 'event_name (EventType Event, xabled)'
        # value = 'Event:macro_name'
        type_name = type(scriptoid).__name__
        xabled = 'enabled' if scriptoid.is_enabled(channel) else 'disabled'
        name = f'{scriptoid.name} ({type_name} Event, {xabled})'
        value = 'Event:' + scriptoid.name
        return Choice(name=name, value=value)

    raise NotImplementedError(repr(scriptoid), repr(type(scriptoid)))

class TrulyBadScriptoidChoice(ValueError):
    pass

def strict_choice_to_scriptoid(value: str, expect_type=None):
    '''Performs the inverse lookup of scriptoid_to_choice, given a Choice's value.'''
    scriptoid_type, name = value.strip().split(':')
    scriptoids = scriptoid_type_map[scriptoid_type]
    name = normalize_name(name)
    scriptoid = scriptoids[name]

    if expect_type and not isinstance(scriptoid, expect_type):
        raise TrulyBadScriptoidChoice('Inappropriate scriptoid type.')
    return scriptoid, scriptoids

def choice_to_scriptoid(value: str, expected_type=None):
    try:
        return strict_choice_to_scriptoid(value, expect_type=expected_type)
    except TrulyBadScriptoidChoice:
        raise
    except Exception:
        pass

    def expected(t):
        return expected_type is None or expected_type is t

    # Try to strip the name down to the barest
    name = normalize_name(value)
    name = re.sub('\(.*', '', name).strip()

    # Try to find any kind of match
    if expected(Pipe) and name in pipes:
        return pipes[name], pipes
    if expected(Source) and name in sources:
        return sources[name], sources
    if expected(Spout) and name in spouts:
        return spouts[name], spouts
    if expected(Macro):
        if name in pipe_macros:
            return pipe_macros[name], pipe_macros
        if name in source_macros:
            return source_macros[name], source_macros
    if expected(Event):
        if name in events:
            return events[name], events
    raise ValueError(f'Could not find a relevant scriptoid by name `{name}`.')


# ==================================== Autocomplete callbacks =====================================

async def autocomplete_scriptoid(interaction: Interaction, name: str):
    name = name.lower()
    results: list[Choice] = []
    scriptoids = itertools.chain(*(p.values() for p in scriptoid_type_map.values()))
    for scriptoid in scriptoids:
        if name in scriptoid.name:
            results.append(scriptoid_to_choice(scriptoid, interaction.channel))
            if len(results) >= 25:
                break
    return results

async def autocomplete_macro(interaction: Interaction, name: str):
    name = name.lower()
    results: list[Choice] = []
    for macro in itertools.chain(pipe_macros.values(), source_macros.values()):
        if name in macro.name:
            results.append(scriptoid_to_choice(macro))
            if len(results) >= 25:
                break
    return results

def autocomplete_event(*, enabled=None):
    async def _autocomplete_event(interaction: Interaction, name: str):
        name = name.lower()
        results = []
        for event in events.values():
            if enabled is not None and event.is_enabled(interaction.channel) != enabled:
                continue
            if name in event.name:
                results.append(scriptoid_to_choice(event, interaction.channel))
                if len(results) >= 25:
                    break
        return results
    return _autocomplete_event

async def autocomplete_invoke_command(interaction: Interaction, name: str):
    name = name.lower()

    commands = set()
    for event in events.on_invoke_events:
        if event.is_enabled(interaction.channel) and name in event.command:
            commands.add(event.command)

    # Sort commands alphabetically and cut off at 25
    return [Choice(name=command, value=command) for command in sorted(commands)[:25]]