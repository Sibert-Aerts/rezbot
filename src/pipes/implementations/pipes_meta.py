from .pipes import pipe_from_func, many_to_one, set_category
from pipes.core.signature import Par
from pipes.core.state import ErrorLog, Context
from pipes.core.templated_string.templated_string import TemplatedString
from utils.util import parse_bool


#####################################################
#                   Pipes : META                    #
#####################################################
set_category('META')

@pipe_from_func({
    'f': Par(str, None, 'The format string. Items of the form {0}, {1} etc. are replaced with the respective item at that index, twice.')
})
@many_to_one
def format2_pipe(input, f):
    '''
    Formats inputs according to a template which may itself be constructed via template.

    (Should be read as "format²")

    In truth, the regular `format` pipe does nothing but discard all its inputs, only returning its `f` argument instead.
    Rezbot scripting already automatically "formats" the `f` argument, and so it behaves exactly as you want!

    However, if you want the *format itself* to be variable according to input, then this is the pipe for you.

    e.g. `>> ~{0~}+~{1~}|a|b > format2 {}`
    produces `a+b`
    '''
    return [f.format(*input)]


@pipe_from_func({
    'force_single': Par(parse_bool, False, 'Whether to force each input string to evaluate to one output string.')
})
async def evaluate_sources_pipe(items, force_single: bool):
    '''
    Evaluates Sources in the literal strings it receives.

    Evaluation of these Sources is constrained for safety reasons.
    '''
    errors = ErrorLog()
    # NOTE: This carries over NONE of the existing context
    context = Context(
        origin=Context.Origin(
            name='evaluate sources',
            type=Context.Origin.Type.EVALUATE_SOURCES_PIPE,
            activator=None,
        ),
        author=None,
        message=None,
    )
    output = []
    try:
        for item in items:
            values, errs = await TemplatedString.evaluate_string(item, context, force_single=force_single)
            if values: output.extend(values)
            errors.extend(errs)
    except:
        raise ValueError('Bad source strings! (Can\'t tell you specific errors right now sorry.)')
    if errors.terminal:
        raise ValueError('Bad source strings! (Can\'t tell you specific errors right now sorry.)')
    # TODO: pipes can produce/access error logs?
    return output


# TODO: "apply" pipe, whose args may be a pipe or even pipeline
