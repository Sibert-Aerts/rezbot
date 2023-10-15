'''
A file containing logic for parsing and evaluating logical conditions in a script.
'''

import re
from pyparsing import ParseResults

from . import grammar
from .logger import ErrorLog, TerminalErrorLogException
from .context import Context, ItemScope
from .templated_string import TemplatedString


class Condition:
    ''' Base Condition class, never instantiated itself, but from_parsed and from_string constructors instantiate appropriately typed Conditions. '''

    @classmethod
    def from_parsed(cls, parse_result):
        if parse_result._name == 'conjunction':
            return Conjunction([cls.from_parsed(c) for c in parse_result])
        if parse_result._name == 'disjunction':
            return Disjunction([cls.from_parsed(c) for c in parse_result])
        if parse_result._name == 'negation':
            return Negation.from_parsed(parse_result)
        if parse_result._name == 'comparison':
            return Comparison.from_parsed(parse_result)
        else:
            raise Exception()

    @classmethod
    def from_string(cls, string):
        return cls.from_parsed(grammar.condition.parse_string(string, True)[0])

    async def evaluate(self, context: Context, scope: ItemScope) -> bool:
        raise NotImplementedError()

# ========================================= Root Conditions ========================================

class RootCondition(Condition):
    pre_errors: ErrorLog | None
    pass

# ======================== Comparison

class Operation:
    STR_EQUALS =    '=='
    STR_NEQUALS =   '!='
    NUM_LT =        '<'
    NUM_GT =        '>'
    NUM_LTE =       '<='
    NUM_GTE =       '>='
    LIKE =          'LIKE'
    NLIKE =         'NOTLIKE'

operation_map = {
    '==':       Operation.STR_EQUALS,
    '!=':       Operation.STR_NEQUALS,
    '<':        Operation.NUM_LT,
    '>':        Operation.NUM_GT,
    '<=':       Operation.NUM_LTE,
    '>=':       Operation.NUM_GTE,
    'LIKE':     Operation.LIKE,
    'NOTLIKE':  Operation.NLIKE,
}

class Comparison(RootCondition):
    def __init__(self, lhs: TemplatedString, op: Operation, rhs: TemplatedString):
        self.lhs = lhs
        self.op = op
        self.rhs = rhs

        if lhs.pre_errors or rhs.pre_errors:
            self.pre_errors = ErrorLog()
            self.pre_errors.extend(lhs.pre_errors, 'left-hand side')
            self.pre_errors.extend(rhs.pre_errors, 'right-hand side')
            if self.pre_errors.terminal:
                raise TerminalErrorLogException(self.pre_errors)
        else:
            self.pre_errors = None

    @classmethod
    def from_parsed(cls, result: ParseResults):
        lhs = TemplatedString.from_parsed(result[0])
        op = operation_map[result[1]]
        rhs = TemplatedString.from_parsed(result[2])
        return Comparison(lhs, op, rhs)

    @classmethod
    def from_string(cls, string: str):
        return cls.from_parsed(grammar.comparison.parse_string(string, True))

    def __repr__(self):
        return 'Comparison(%s %s %s)' % (repr(self.lhs), self.op, repr(self.rhs))
    def __str__(self):
        return '%s%s%s' % (str(self.lhs), self.op, str(self.rhs))

    async def evaluate(self, context: Context, scope: ItemScope):
        lhs, lhs_errors = await self.lhs.evaluate(context, scope)
        rhs, rhs_errors = await self.rhs.evaluate(context, scope)

        if lhs_errors.terminal or rhs_errors.terminal:
            errors = ErrorLog()
            errors.extend(lhs_errors, 'left-hand side')
            errors.extend(rhs_errors, 'right-hand side')
            raise TerminalErrorLogException(errors)
        
        if self.op is Operation.STR_EQUALS:
            return (lhs == rhs)
        if self.op is Operation.STR_NEQUALS:
            return (lhs != rhs)
        if self.op is Operation.NUM_LT:
            return (float(lhs) < float(rhs))
        if self.op is Operation.NUM_GT:
            return (float(lhs) > float(rhs))
        if self.op is Operation.NUM_LTE:
            return (float(lhs) <= float(rhs))
        if self.op is Operation.NUM_GTE:
            return (float(lhs) >= float(rhs))
        if self.op is Operation.LIKE:
            return re.search(rhs, lhs)
        if self.op is Operation.NLIKE:
            return not re.search(rhs, lhs)
        raise Exception()


# ======================================== Joined Conditions =======================================
    
class JoinedCondition:
    children: list[Condition]

    def __init__(self, children: list[Condition]):
        self.children = children

    def __repr__(self):
        return '(' + (' ' + self.joiner + ' ').join(repr(c) for c in self.children) + ')'
    def __str__(self):
        return '(' + (' ' + self.joiner.lower() + ' ').join(str(c) for c in self.children) + ')'

class Conjunction(JoinedCondition):
    joiner = 'AND'

    async def evaluate(self, context: Context, scope: ItemScope):
        for c in self.children:
            if not await c.evaluate(context, scope):
                return False
        return True

class Disjunction(JoinedCondition):
    joiner = 'OR'

    async def evaluate(self, context: Context, scope: ItemScope):
        for c in self.children:
            if await c.evaluate(context, scope):
                return True
        return False


class Negation(Condition):
    def __init__(self, child: Condition):
        self.child = child

    @classmethod
    def from_parsed(cls, result: ParseResults) -> 'Negation':        
        times = len(result) - 1
        negation = Condition.from_parsed(result[-1])
        for _ in range(times):
            negation = Negation(negation)
        return negation

    def __repr__(self):
        return 'NOT(' + repr(self.child) + ')'
    def __str__(self):
        return 'not (' + str(self.child) + ')'

    async def evaluate(self, context: Context, scope: ItemScope):
        return not await self.child.evaluate(context, scope)
