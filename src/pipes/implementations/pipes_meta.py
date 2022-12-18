from .pipes import make_pipe, many_to_one, set_category
from ..signature import Par
from ..logger import ErrorLog
from ..templatedstring import TemplatedString
from utils.util import parse_bool


#####################################################
#                   Pipes : META                    #
#####################################################
set_category('META')

@make_pipe({
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


@make_pipe({
    'force_single': Par(parse_bool, False, 'Whether to force each input string to evaluate to one output string.')
})
async def evaluate_sources_pipe(items, force_single: bool):
    '''
    Evaluates sources in the literal strings it receives.
    '''
    errors = ErrorLog()
    output = []
    try:
        for item in items:
            values, errs = await TemplatedString.evaluate_string(item, None, None, forceSingle=force_single)
            if values: output.extend(values)
            errors.extend(errs)
    except:
        raise ValueError('Bad source strings! (Can\'t tell you specific errors right now sorry.)')
    if errors.terminal:
        raise ValueError('Bad source strings! (Can\'t tell you specific errors right now sorry.)')
    # TODO: pipes can produce/access error logs?
    return output


# TODO: "apply" pipe, whose args may be a pipe or even pipeline
