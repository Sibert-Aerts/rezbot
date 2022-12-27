import utils.util as util
import math
import re

from simpleeval import SimpleEval

from .pipes import pipe_from_func, many_to_one, set_category
from ..signature import Par


#####################################################
#                   Pipes : MATHS                   #
#####################################################
set_category('MATHS')

def smart_format(x: float):
    x = str(x)
    return re.sub('\.?0+$', '', x) if '.' in x else x

MATH_FUNCTIONS = {
    # Trigonometry
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'asin': math.asin,
    'acos': math.acos,
    'atan': math.atan,
    'atan2': math.atan2,
    # Exponentiation
    'exp': math.exp,
    'log': math.log,
    'log10': math.log10,
    'log2': math.log2,
    # This asshole
    'factorial': math.factorial,
    # Squares and roots
    'sqrt': math.sqrt,
    'hypot': math.hypot,
    # Reduction
    'floor': math.floor,
    'ceil': math.ceil,
    'round': round,
    'abs': abs,
    'sign': lambda x : -1 if x < 0 else 1 if x > 0 else 0,
    # Number theory
    'gcd': math.gcd,
    # Statistics
    'min': min,
    'max': max,
    'sum': sum,
    'avg': lambda *x : sum(x)/len(x)
}

SIMPLE_EVAL = SimpleEval(functions=MATH_FUNCTIONS, names={'e': math.e, 'pi': math.pi, 'inf': math.inf, 'True': True, 'False': False})

@pipe_from_func({
    'expr': Par(str, None, 'The mathematical expression to evaluate. Use {} notation to insert items into the expression.')
}, command=True)
@many_to_one
@util.format_doc(funcs=', '.join(c for c in MATH_FUNCTIONS))
def math_pipe(values, expr):
    '''
    Evaluates the mathematical expression given by the argument string.
    
    Available functions: {funcs}
    Available constants: True, False, e, pi and inf
    
    Note: For finding the min, max, sum or avg of an arbitrary number of arguments, use the respective min, max, sum and avg pipes.
    '''
    return [ smart_format(SIMPLE_EVAL.eval(expr)) ]


@pipe_from_func
@many_to_one
def max_pipe(values):
    ''' Produces the maximum value of the inputs evaluated as numbers. '''
    return [smart_format(max(float(x) for x in values))]


@pipe_from_func
@many_to_one
def min_pipe(values):
    ''' Produces the minimum value of the inputs evaluated as numbers. '''
    return [smart_format(min(float(x) for x in values))]


@pipe_from_func
@many_to_one
def sum_pipe(values):
    ''' Produces the sum of the inputs evaluated as numbers. '''
    return [smart_format(sum(float(x) for x in values))]


@pipe_from_func
@many_to_one
def avg_pipe(values):
    ''' Produces the mean average of the inputs evaluated as numbers. '''
    return [smart_format(sum(float(x) for x in values)/len(values))]