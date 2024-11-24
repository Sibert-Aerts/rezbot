'''
File used for quickly testing bot scripting functionality without loading an actual Discord bot.
Change or add coroutine definitions depending on what you're testing.
Actual rezbot scripting test suite: Someday, maybe, surely.
'''

import timeit
import asyncio
import itertools
from pprint import pprint

import pipes.core.grammar as grammar
from pipes.core.state import Context, ItemScope, ErrorLog, SpoutState
import pipes.core.groupmodes as groupmodes
from pipes.core.templated_string.templated_string import TemplatedString
from pipes.core.conditions import Condition
from pipes.core.executable_script import ExecutableScript

from pipes.core.macros import Macro, MACRO_SOURCES, MACRO_PIPES
from pipes.core.events import Event, ALL_EVENTS


#### Stub values and methods

context = Context(
    origin=Context.Origin(
        Context.Origin.Type.COMMAND,
        name='Test context',
        activator=None,
    ),
    arguments={'1': 'one', '2': 'two', 'small': 'small ', 'page': 'dog'},
)
scope = ItemScope(items=['ix', 'nox', 'flux'])

def fmt_list(l, base_indent=0):
    if not l: return '[]'
    indent = base_indent + 4
    items = ['['] + [repr(x) for x in l]
    return ('\n' + ' '*indent).join(items) + '\n' + ' ' * base_indent + ']'

async def print_side_effects(ctx, spout_state: SpoutState, end_values):
    print('\nSIDE EFFECTS:')
    print('    CALLBACKS:', fmt_list(spout_state.callbacks, base_indent=4))
    print('    AGGREGATED:', dict(spout_state.aggregated))
    print('    END VALUES:', fmt_list(end_values, base_indent=4))
    return ErrorLog()

async def print_error_log(ctx, errors: ErrorLog):
    if not errors: return
    print('\nERROR LOG:\n' + str(errors))


#### Test functions

async def test_switch():
    remainder, mode = groupmodes.legacy_parse('''SWITCH(( {arg small}=="" ))[
  /1!(4)( join , > embed image={} )
  | ((1)! embed image={})
]''')

    print('MODE:', mode)
    if remainder:
        print('REMAINDER:', remainder)
    print()

    _pipes = ['true', 'false']

    async def run_condition(items):
        result = await mode.apply(items, _pipes, context, scope)
        for items, pipe in result:
            print(items, '->', pipe)

    await run_condition(['10', '10', '10', '10', '10', '20'])
    await run_condition(['0', '5', '7'])


async def test_conditional():

    ts = TemplatedString.from_string('{?A if 0==0 and not (0==1 or 0==0) else "B B"}')
    s, _ = await ts.evaluate(context, scope)

    print(repr(ts))
    print(s)


async def test_condition():

    cond = Condition.from_string('foo IS NOT TRUE')
    value, errors = await cond.evaluate(context, scope)

    print(cond)
    print(value)
    print(errors)


async def test_groupmode():
    split_strs = [
        '(1)',
        '/2!',
        '%3',
        '#1',
        '#2:3',
        '#:-4!',
        '#5:!!',
        '#:',
    ]
    for s in split_strs:
        split = groupmodes.SplitMode.from_string(s)
        print(s, '\t→', split)

    print()
    assign_strs = [
        '',
        '*',
        '?',
        '* ?',
        'SWITCH( {foo}==foo )',
        '* SWITCH( 1>2 | {get bar} IS INT or 20 LIKE /30/ and 1==1 )!!',
    ]
    for s in assign_strs:
        assign = groupmodes.AssignMode.from_string(s)
        print(s, '\t→', assign)

    print()
    if_strs = [
        'IF( True IS TRUE )',
        'IF( {foo}==foo and bar>bar )!',
    ]
    for s in if_strs:
        res = groupmodes.IfMode.from_string(s)
        print(s, '\t→', res)
    print()
    groupby_strs = [
        'GROUP BY 1',
        'COLLECT BY 2,3',
        'EXTRACT BY 2,  5, 10',
        'COLLECT BY ( 2,3 )',
    ]
    for s in groupby_strs:
        res = groupmodes.GroupBy.from_string(s)
        print(s, '\t→', res)
    print()
    sortby_strs = [
        'SORT BY 1',
        'SORT BY +2, +3, +4',
        'SORT BY (1, 1, 1, 1, 1)',
    ]
    for s in sortby_strs:
        res = groupmodes.SortBy.from_string(s)
        print(s, '\t→', res)

    print('\n')
    groupmode_strs = [
        '(1) IF ({0} LIKE /10/)!? gaga',
        '#10:(2)(03) SORT BY +1,+2 GROUP BY 3,4 *SWITCH(boo==foo|bar>far) gaga',
        '(1)/2! %3 \\5 #1 #2:3 #:-4 #5:\n IF( {10}=={20}{30} )!! SORT BY 1 GROUP BY 1,2,3 SWITCH( {foo}bar==1 )! pipe_name\nblabla',
    ]
    for s in groupmode_strs:
        res, rem = groupmodes.GroupMode.from_string_with_remainder(s)
        print(s, '\t→', res)
        print('\t\t Remainder:', repr(rem))


async def time_groupmode_parse():
    groupmode_strs = [
        '(1) IF ({0} LIKE /10/)!? gaga',
        '#10:(2)(03) SORT BY +1,+2 GROUP BY 3,4 *SWITCH(boo==foo|bar>far) gaga',
        '(1)/2! %3 \\5 #1 #2:3 #:-4 #5:\n SORT BY 1 GROUP BY 1,2,3 SWITCH( {foo}bar==1 )! pipe_name\nblabla',
    ]
    def new_parse():
        for s in groupmode_strs:
            res, rem = groupmodes.GroupMode.from_string_with_remainder(s)
    def old_parse():
        for s in groupmode_strs:
            res, rem = groupmodes.legacy_parse(s)
    new_parse()
    old_parse()
    print('OLD TIME:', timeit.timeit('parse()', globals={'parse': old_parse}, number=1))
    print('NEW TIME:', timeit.timeit('parse()', globals={'parse': new_parse}, number=1))


async def test_multiple_evaluate():

    # NOTE: Multiple-evaluates to 200k strings
    ts = TemplatedString.from_string('----{20 words}/{20 words}/{10 words}/{50 words}-----')

    s, _ = await ts.evaluate(context, scope)
    print("SINGLE EVALUATE")
    pprint(s)

    start = timeit.default_timer()
    strings, _ = await ts.multiple_evaluate(context, scope)
    end = timeit.default_timer()
    print('TIME:', end-start, 'COUNT:', len(strings))


async def statically_analyse_all_macros_and_events():

    bad_macros: list[tuple[Macro, ErrorLog]] = list()
    for macro in itertools.chain(MACRO_PIPES.values(), MACRO_SOURCES.values()):
        errors = macro.get_static_errors()
        if errors:
            bad_macros.append((macro, errors))

    bad_events: list[tuple[Event, ErrorLog]] = list()
    for event in ALL_EVENTS.values():
        errors = event.get_static_errors()
        if errors:
            bad_events.append((event, errors))

    for macro, errors in bad_macros:
        print()
        print('Bad Macro:', macro.name)
        print(errors)
        print()

    for event, errors in bad_events:
        print()
        print('Bad Event:', event.name)
        print(errors)
        print()


async def test_script(pl_str):
    pl = ExecutableScript.from_string(pl_str)

    print('REPR:')
    print(repr(pl), '\n')
    print('STRING:')
    print(str(pl), '\n')

    if static_errors := pl.get_static_errors():
        print('\nSTATIC ERRORS:\n' + str(static_errors))

    pl.perform_side_effects = print_side_effects
    pl.send_error_log = print_error_log

    await pl.execute(context)

async def test_script_cli():
    '''
    Interactive script execution CLI.
    '''
    try:
        while True:
            pl = input('Please input your script:\n>>')
            await test_script(pl)
            print()
    except EOFError:
        print()
        print('Ending session.')
        return


if __name__ == '__main__':
    try:
        pass
        # asyncio.run(test_switch())
        # asyncio.run(test_conditional())
        # asyncio.run(test_condition())
        # asyncio.run(test_groupmode())
        # asyncio.run(time_groupmode_parse())

        # asyncio.run(test_multiple_evaluate())

        # asyncio.run(statically_analyse_all_macros_and_events())

        asyncio.run(test_script_cli())

    except KeyboardInterrupt:
        pass
