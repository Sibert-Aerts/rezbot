import itertools
from typing import Callable, Literal, Type

from discord.ext import commands
from discord import app_commands, Interaction
from discord.app_commands import Choice

from ..pipe import Pipe, Source, Spout, Pipes
from ..implementations.pipes import pipes
from ..implementations.sources import sources
from ..implementations.spouts import spouts
from ..macros import Macros, Macro, MacroSig, pipe_macros, source_macros
from ..events import Event, Events, OnMessage, OnReaction, events
from .macro_commands import check_pipe_macro, check_source_macro
from mycommands import MyCommands
import utils.texttools as texttools
from utils.util import normalize_name

'''
A module providing a collection of slash commands for interacting with scripting/pipes/macros/events.
'''

# ====================================== Scriptoid mappings =======================================

scriptoid_type_map: dict[str, Pipes|Macros|Events]  = {
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

event_type_map: dict[str, Type[OnMessage|OnReaction]] = {
    'OnMessage': OnMessage,
    'OnReaction': OnReaction
}

# ===================================== Autocomplete utility ======================================


def scriptoid_to_choice(scriptoid: Pipe|Macro|Event, channel=None):
    # This could be class methods but it's only used in this one file
    # and it is much nicer to have all the implementations laid out right here.    
    if isinstance(scriptoid, Pipe):
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

def choice_to_scriptoid(value: str, expect_type=None):
    '''Performs the inverse lookup of scriptoid_to_choice, given a Choice's value.'''
    scriptoid_type, name = value.strip().split(':')
    scriptoids = scriptoid_type_map[scriptoid_type]
    name = normalize_name(name)
    scriptoid = scriptoids[name]

    if expect_type and not isinstance(scriptoid, expect_type):
        raise ValueError('Inappropriate scriptoid type.')

    return scriptoid, scriptoids

# ==================================== Autocomplete callbacks =====================================

async def autocomplete_scriptoid(interaction: Interaction, name: str):
    name = name.lower()
    results = []
    scriptoids = itertools.chain(*(p.values() for p in scriptoid_type_map.values()))
    for scriptoid in scriptoids:
        if name in scriptoid.name:
            results.append(scriptoid_to_choice(scriptoid, interaction.channel))
            if len(results) >= 25:
                break
    return results

async def autocomplete_macro(interaction: Interaction, name: str):
    name = name.lower()
    results = []
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


class PipeSlashCommands(MyCommands):

    # =========================================== General scriptoid Lookup ============================================

    @app_commands.command()
    @app_commands.describe(scriptoid_name='The scriptoid to look up')
    @app_commands.autocomplete(scriptoid_name=autocomplete_scriptoid)
    @app_commands.rename(scriptoid_name="scriptoid")
    async def lookup(self, interaction: Interaction, scriptoid_name: str):
        ''' Look up info on a specific Pipe, Source, Spout, Macro or Event. '''        
        reply = interaction.response.send_message
        try:
            scriptoid, _ = choice_to_scriptoid(scriptoid_name)
        except:
            await reply(f'Command failed, likely due to nonexistent scriptoid.', ephemeral=True)
            return

        # Get embed
        embed = scriptoid.embed(interaction)

        # Take credit for native scriptoids
        if isinstance(scriptoid, Pipe):
            embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar)

        await reply(embed=embed)


    # ============================================ Native scriptoid Listing ===========================================

    async def _list_scriptoids(self, interaction: Interaction, scriptoids: Pipes, what: str, category_name: str):
        ## List pipes in a specific category
        reply = interaction.response.send_message
        
        if category_name or not scriptoids.categories:
            if category_name:
                category_name = category_name.upper()
                if category_name not in scriptoids.categories:
                    await reply(f'Unknown category "{category_name}".', ephemeral=True)
                    return
                scriptoids_to_display = scriptoids.categories[category_name]
            else:
                scriptoids_to_display = scriptoids.values()

            infos = []
            if category_name:
                infos.append(f'{what.capitalize()}s in category {category_name}:\n')
            else:
                infos.append(f'{what.capitalize()}s:\n')


            col_width = len(max((p.name for p in scriptoids_to_display), key=len)) + 3
            for pipe in scriptoids_to_display:
                info = pipe.name
                if pipe.doc:
                    info = info.ljust(col_width) + pipe.small_doc
                infos.append(info)

            infos.append('')
            infos.append(f'Use /lookup [{what} name] to see detailed info on a specific {what}.')
            if what != 'spout':
                infos.append(f'Use /{what}_macros for a list of user-defined {what}s.\n')
            await reply(texttools.block_format('\n'.join(infos)))

        ## List all categories
        else:
            infos = []
            infos.append(f'{what.capitalize()} categories:\n')
            
            col_width = len(max(scriptoids.categories, key=len)) + 2
            for category_name in scriptoids.categories:
                info = category_name.ljust(col_width)
                category = scriptoids.categories[category_name]
                MAX_PRINT = 8
                if len(category) > MAX_PRINT:
                    info += ', '.join(p.name for p in category[:MAX_PRINT-1]) + '... (%d more)' % (len(category)-MAX_PRINT+1)
                else:
                    info += ', '.join(p.name for p in category)
                infos.append(info)

            infos.append('')
            infos.append(f'Use /lookup [{what} name] to see more info on a specific {what}.')
            if what != 'spout':
                infos.append(f'Use /{what}_macros for a list of user-defined {what}s.\n')
            await reply(texttools.block_format('\n'.join(infos)))

    @app_commands.command()
    @app_commands.describe(category="The specific category of Pipes to list")
    @app_commands.choices(category=[Choice(name=cat, value=cat) for cat in pipes.categories])
    async def pipes(self, interaction: Interaction, category: str=None):
        ''' Display a list of native Pipes, which can be used in scripts. '''
        await self._list_scriptoids(interaction, pipes, 'pipe', category)

    @app_commands.command()
    @app_commands.describe(category="The specific category of Sources to list")
    @app_commands.choices(category=[Choice(name=cat, value=cat) for cat in sources.categories])
    async def sources(self, interaction: Interaction, category: str=None):
        ''' Display a list of native Sources, which can be used in scripts. '''
        await self._list_scriptoids(interaction, sources, 'source', category)

    @app_commands.command()
    async def spouts(self, interaction: Interaction):
        ''' Display a list of native Spouts, which can be used in scripts. '''
        await self._list_scriptoids(interaction, spouts, 'spout', None)


    # ================================================ Macro Listing ================================================

    async def _list_macros(self, interaction: Interaction, macros: Macros, hidden: bool, mine: bool):
        '''Reply with a list of macros.'''
        what = macros.kind.lower()
        qualified_what = what

        ## Filter based on the given name
        filtered_macros = macros.hidden() if hidden else macros.visible()
        if hidden:
            qualified_what = 'hidden ' + what
        if mine:
            author = interaction.user
            filtered_macros = [m for m in filtered_macros if int(macros[m].authorId) == author.id]
            qualified_what = 'your ' + what

        if not filtered_macros:
            await interaction.response.send_message(f'No {qualified_what} macros found.')
            return

        ## Boilerplate
        infos = []
        infos.append(f'Here\'s a list of all {qualified_what} macros, use /{what}_macro [name] to see more info on a specific one.')
        infos.append(f'Use /{what} for a list of native {qualified_what}s.')

        ## Separate those with and without descriptions
        desced_macros = [m for m in filtered_macros if macros[m].desc]
        undesced_macros = [m for m in filtered_macros if not macros[m].desc]

        ## Format the ones who have a description as a nice two-column block
        if desced_macros:
            infos.append('')
            colW = len(max(desced_macros, key=len)) + 2
            for name in desced_macros:
                macro = macros[name]
                info = name +  ' ' * (colW-len(name))
                desc = macro.desc.split('\n', 1)[0]
                info += desc if len(desc) <= 80 else desc[:75] + '(...)'
                infos.append(info)

        ## Format the other ones as just a list
        if undesced_macros:
            infos.append('\nWithout descriptions:')
            infos += texttools.line_chunk_list(undesced_macros)
        
        first = True
        for block in texttools.block_chunk_lines(infos):
            if first:
                await interaction.response.send_message(block)
                first = False
            else:
                await interaction.channel.send(block)

    @app_commands.command()
    @app_commands.describe(hidden='If true, shows (only) hidden macros', mine='If true, only shows your authored macros')
    async def pipe_macros(self, interaction: Interaction, hidden: bool=False, mine: bool=False):
        ''' Display a list of Pipe Macros. '''
        await self._list_macros(interaction, pipe_macros, hidden, mine)

    @app_commands.command()
    @app_commands.describe(hidden='If true, shows (only) hidden macros', mine='If true, only shows your authored macros')
    async def source_macros(self, interaction: Interaction, hidden: bool=False, mine: bool=False):
        ''' Display a list of Source Macros. '''
        await self._list_macros(interaction, source_macros, hidden, mine)


    # ================================================ Macro Management ===============================================

    macro_group = app_commands.Group(name='macro', description='Define, redefine, describe or delete Macros.')
    ''' The `/macro <action>` command group'''

    @macro_group.command(name='define')
    @app_commands.describe(
        macro_type="The type of Macro",
        name="The name of the Macro",
        code="The code to define the Macro as",
        description="The Macro's description",
        hidden="Whether the Macro should show up in the general Macro list",
        force="Force the Macro to save even if there are errors"
    )
    @app_commands.rename(macro_type="type")
    async def macro_define(self, interaction: Interaction,
        macro_type: Literal['Pipe', 'Source'],
        name: str,
        code: str,
        description: str=None,
        hidden: bool=False,
        force: bool=False
    ):
        ''' Define a new Macro. '''
        reply = interaction.response.send_message
        author = interaction.user
        
        natives = scriptoid_type_map[macro_type]
        macros = scriptoid_type_map[macro_type + '_macro']
        
        name = normalize_name(name)
        if name in natives or name in macros:
            await reply(f'A {macro_type} called `{name}` already exists, try the `/macro edit` command.')
            return

        check = macro_check_map[macros.kind]
        if not force and not await check(code, reply):
            await interaction.channel.send('Run the command again with `force: True` to save it anyway.')
            return

        macro = Macro(macros.kind, name, code, author.name, author.id, desc=description, visible=not hidden)
        macros[name] = macro
        await reply(f'Successfully defined a new {macro_type} macro.', embed=macro.embed(interaction))

    @macro_group.command(name='edit')
    @app_commands.describe(
        macro_choice="The Macro to edit",
        code="If given, the Macro's new code",
        description="If given, the Macro's new description",
        hidden="If given, the Macro's new visibility",
        force="Force the Macro to save even if there are errors"
    )
    @app_commands.autocomplete(macro_choice=autocomplete_macro)
    @app_commands.rename(macro_choice='macro')
    async def macro_edit(self, interaction: Interaction,
        macro_choice: str,
        code: str=None,
        description: str=None,
        hidden: bool=None,
        force: bool=None
    ):
        ''' Redefine one or more fields on an existing Macro. '''
        reply = interaction.response.send_message
        author = interaction.user

        try:
            macro, macros = choice_to_scriptoid(macro_choice, Macro)
        except:
            await reply(f'Command failed, likely due to nonexistent Macro.', ephemeral=True)
            return

        if not macro.authorised(author):
            await reply('You are not authorised to modify that Macro. Try defining a new one instead.')
            return

        check = macro_check_map[macros.kind]
        if not force and code and not await check(code, reply):
            await interaction.channel.send('Run the command again with `force: True` to save it anyway.')
            return

        if code is not None:
            macro.code = code
        if description is not None:
            macro.desc = description
        if hidden is not None:
            macro.visible = not hidden

        macros.write()
        await reply(f'Successfully edited the {macro.kind} Macro.', embed=macro.embed(interaction))

    @macro_group.command(name='delete')
    @app_commands.describe(macro_choice="The Macro to delete")
    @app_commands.autocomplete(macro_choice=autocomplete_macro)
    @app_commands.rename(macro_choice='macro')
    async def macro_delete(self, interaction: Interaction, macro_choice: str):
        ''' Delete a Macro. '''
        reply = interaction.response.send_message
        author = interaction.user
    
        try:
            macro, macros = choice_to_scriptoid(macro_choice, Macro)
        except:
            await reply(f'Command failed, likely due to nonexistent Macro.', ephemeral=True)
            return

        if not macro.authorised(author):
            await reply('You are not authorised to modify that Macro.')
            return

        del macros[macro.name]
        await reply(f'Successfully deleted {macros.kind} Macro `{macro.name}`.')

    @macro_group.command(name='set_param')
    @app_commands.describe(
        macro_choice="The Macro",
        param="The name of the parameter to assign",
        description="The parameter's description to assign",
        default="The parameter's default value to assign",
        delete="If True, will delete this parameter instead",
    )
    @app_commands.autocomplete(macro_choice=autocomplete_macro)
    @app_commands.rename(macro_choice='macro')
    async def macro_set_param(self, interaction: Interaction,
        macro_choice: str,
        param: str,
        description: str=None,
        default: str=None,
        delete: bool=False,
    ):
        ''' Add, overwrite or delete a parameter on a Macro. '''
        reply = interaction.response.send_message
        author = interaction.user
        
        param = normalize_name(param)
        try:
            macro, macros = choice_to_scriptoid(macro_choice, Macro)
        except:
            return await reply(f'Command failed, likely due to nonexistent Macro.', ephemeral=True)

        if not macro.authorised(author):
            return await reply(f'You are not authorised to modify {macro.kind} Macro {macro.name}.', ephemeral=True)

        existed = (param in macro.signature)
        if not delete:
            par = MacroSig(param, default, description)
            macro.signature[param] = par
        elif existed:
            del macro.signature[param]
        else:
            return await reply(f'Parameter `{param}` does not exist on {macro.kind} Macro {macro.name}.', ephemeral=True)

        macros.write()
        verbed = 'deleted' if delete else 'overwrote' if existed else 'added'
        await reply(f'Successfully {verbed} parameter `{param}` on {macro.kind} Macro {macro.name}.', embed=macro.embed(interaction))


    # ================================================= Event Listing =================================================

    @app_commands.command()
    @app_commands.describe(enabled='If given, only list Events enabled (disabled) in this channel')
    async def events(self, interaction: Interaction, enabled: bool=None):
        ''' Display a list of Events. '''
        def reply(*a, **kw):
            if not interaction.response.is_done():
                return interaction.response.send_message(*a, **kw)
            return interaction.channel.send(*a, **kw)

        if not events:
            await reply('No events registered.')
            return

        enabled_events, disabled_events = [], []
        for event in events.values():
            if interaction.channel.id in event.channels: enabled_events.append(event)
            else: disabled_events.append(event)

        if enabled_events and enabled is not False:
            infos = ['**__Enabled:__**'] + ['• ' + str(e) for e in enabled_events]
            await reply('\n'.join(infos))

        if disabled_events and enabled is not True:
            infos = ['**__Disabled:__**'] + [', '.join(e.name for e in disabled_events)]
            await reply('\n'.join(infos))


    # ================================================ Event Management ===============================================

    event_group = app_commands.Group(name='event', description='Define, redefine, describe or delete Events')
    ''' The `/event <action>` command group'''

    @event_group.command(name='define')
    @app_commands.describe(
        name='The name of the new Event',
        event_type='The type of Event',
        trigger='The type-dependent trigger',
        code='The code which is triggered'
    )
    @app_commands.rename(event_type='type')
    async def event_define(self, interaction: Interaction,
        name: str,
        event_type: Literal['OnMessage', 'OnReaction'],
        trigger: str,
        code: str,
    ):
        ''' Define a new Event and enable it in this channel. '''
        reply = interaction.response.send_message
        EventType = event_type_map[event_type]

        name = normalize_name(name)
        if name in events:
            await reply(f'An Event called `{name}` already exists, try the `/event edit` command.')
            return
            
        # TODO: Check event script code before saving

        event = EventType(name, interaction.channel, code, trigger)
        events[name] = event
        await reply(f'Successfully defined a new Event.', embed=event.embed(interaction))

    @event_group.command(name='edit')
    @app_commands.describe(
        event_choice='The Event to edit',
        event_type='If given, the Event\'s new type',
        trigger='If given, the Event\'s new type-dependent trigger',
        code='If given, the Event\'s new code',
    )
    @app_commands.rename(event_choice='event')
    @app_commands.autocomplete(event_choice=autocomplete_event())
    async def event_edit(self, interaction: Interaction,
        event_choice: str,
        event_type: Literal['OnMessage', 'OnReaction']=None,
        trigger: str=None,
        code: str=None,
    ):
        ''' Redefine one or more fields on an existing Event. '''
        reply = interaction.response.send_message

        try:
            event, _ = choice_to_scriptoid(event_choice, Event)
        except:
            await reply(f'Command failed, likely due to nonexistent Event.', ephemeral=True)
            return

        # TODO: Check event code for errors

        if event_type is not None:
            EventType = event_type_map[event_type]
            if trigger is None:
                await reply(f'When changing Event Type, the trigger must be given as well.')
                return
            new_event = EventType(event.name, interaction.channel, event.script, trigger)
            new_event.channels = event.channels
            event = new_event
            events[event.name] = event
        elif trigger is not None:
            event.set_trigger(trigger)
        if code is not None:
            event.script = code

        events.write()
        await reply(f'Successfully edited the Event.', embed=event.embed(interaction))

    @event_group.command(name='delete')
    @app_commands.describe(event_choice='The Event to delete')
    @app_commands.rename(event_choice='event')
    @app_commands.autocomplete(event_choice=autocomplete_event())
    async def event_delete(self, interaction: Interaction, event_choice: str):
        ''' Delete an Event. '''
        reply = interaction.response.send_message

        try:
            event, _ = choice_to_scriptoid(event_choice, Event)
        except:
            await reply(f'Command failed, likely due to nonexistent Event.', ephemeral=True)
            return

        del events[event.name]
        await reply(f'Successfully deleted Event `{event.name}`.')
        
    async def _event_set_enabled(self, interaction: Interaction, event_choice: str, enable: bool):
        reply = interaction.response.send_message

        try:
            event, _ = choice_to_scriptoid(event_choice, Event)
        except:
            await reply(f'Command failed, likely due to nonexistent Event.', ephemeral=True)
            return

        if enable:
            if interaction.channel.id in event.channels:
                await reply(f'Event {event.name} is already enabled in {interaction.channel.mention}.')
            else:                
                event.channels.append(interaction.channel.id)
                await reply(f'Event {event.name} has been enabled in {interaction.channel.mention}.')
        else:
            if interaction.channel.id not in event.channels:
                await reply(f'Event {event.name} is already disabled in {interaction.channel.mention}.')
            else:                
                event.channels.remove(interaction.channel.id)
                await reply(f'Event {event.name} has been disabled in {interaction.channel.mention}.')

    @event_group.command(name='enable')
    @app_commands.describe(event_choice='The Event to enable')
    @app_commands.rename(event_choice='event')
    @app_commands.autocomplete(event_choice=autocomplete_event(enabled=False))
    async def event_enable(self, interaction: Interaction, event_choice: str):
        ''' Enable an Event in this channel. '''
        await self._event_set_enabled(interaction, event_choice, enable=True)

    @event_group.command(name='disable')
    @app_commands.describe(event_choice='The Event to disable')
    @app_commands.rename(event_choice='event')
    @app_commands.autocomplete(event_choice=autocomplete_event(enabled=True))
    async def event_disable(self, interaction: Interaction, event_choice: str):
        ''' Disable an Event in this channel. '''
        await self._event_set_enabled(interaction, event_choice, enable=False)



# Load the bot cog
async def setup(bot: commands.Bot):
    await bot.add_cog(PipeSlashCommands(bot))