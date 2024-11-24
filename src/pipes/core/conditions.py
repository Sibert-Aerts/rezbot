'''
A file containing logic for parsing and evaluating logical conditions in a script.
'''

import re
from pyparsing import ParseResults

from pipes.core.state.logger import ErrorLog

from . import grammar
from .state.logger import ErrorLog
from .state.context import Context, ItemScope
from .templated_string.templated_string import TemplatedString

from utils.util import parse_bool


# ======================================= Abstract Condition =======================================

class Condition:
    '''
    Abstract base Condition class.
    Never instantiated, but its from_parsed and from_string constructors instantiate appropriate Condition subclasses.
    '''
    @classmethod
    def from_parsed(cls, parse_result: ParseResults):
        match parse_result._name:
            case 'conjunction':
                return Conjunction([cls.from_parsed(c) for c in parse_result])
            case 'disjunction':
                return Disjunction([cls.from_parsed(c) for c in parse_result])
            case 'negation':
                return Negation.from_parsed(parse_result)
            case 'comparison':
                return Comparison.from_parsed(parse_result)
            case 'agg_predicate':
                return AggregatePredicate.from_parsed(parse_result)
            case 'predicate':
                return Predicate.from_parsed(parse_result)
            case bad_name:
                raise Exception()

    @classmethod
    def from_string(cls, string):
        return cls.from_parsed(grammar.condition.parse_string(string, True)[0])

    # ================ API ================

    def get_pre_errors(self) -> ErrorLog | None:
        raise NotImplementedError()

    async def evaluate(self, context: Context, scope: ItemScope) -> tuple[bool, ErrorLog]:
        raise NotImplementedError()

# ========================================= Root Conditions ========================================

class RootCondition(Condition):
    pre_errors: ErrorLog | None = None
    def get_pre_errors(self) -> ErrorLog | None:
        return self.pre_errors

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

    async def evaluate(self, context: Context, scope: ItemScope) -> tuple[bool, ErrorLog]:
        errors = ErrorLog()
        lhs, lhs_errors = await self.lhs.evaluate(context, scope)
        rhs, rhs_errors = await self.rhs.evaluate(context, scope)
        errors.extend(lhs_errors, 'left-hand side')
        errors.extend(rhs_errors, 'right-hand side')
        if errors.terminal:
            return None, errors

        if self.op is Operation.STR_EQUALS:
            return (lhs == rhs), errors
        if self.op is Operation.STR_NEQUALS:
            return (lhs != rhs), errors
        if self.op is Operation.NUM_LT:
            return (float(lhs) < float(rhs)), errors
        if self.op is Operation.NUM_GT:
            return (float(lhs) > float(rhs)), errors
        if self.op is Operation.NUM_LTE:
            return (float(lhs) <= float(rhs)), errors
        if self.op is Operation.NUM_GTE:
            return (float(lhs) >= float(rhs)), errors
        if self.op is Operation.LIKE:
            return re.search(rhs, lhs), errors
        if self.op is Operation.NLIKE:
            return not re.search(rhs, lhs), errors
        raise Exception()


# ======================== Predicate

def type_check(str, t):
    try:
        t(str)
        return True
    except ValueError:
        return False

class Predicate(RootCondition):
    class Category:
        WHITE = 'WHITE'
        EMPTY = 'EMPTY'
        TRUE =  'TRUE'
        FALSE = 'FALSE'
        BOOL =  'BOOL'
        INT =   'INT'
        FLOAT = 'FLOAT'

    def __init__(self, subject: TemplatedString, negated: bool, category: Category):
        self.subject = subject
        self.negated = negated
        self.category = category

        if subject.pre_errors:
            self.pre_errors = subject.pre_errors

    @classmethod
    def from_parsed(cls, result: ParseResults):
        subject = TemplatedString.from_parsed(result[0])
        negated = bool(result.get('not'))
        category = getattr(Predicate.Category, result['pred_category'])
        return Predicate(subject, negated, category)

    @classmethod
    def from_string(cls, string: str):
        return cls.from_parsed(grammar.predicate.parse_string(string, True))

    def __repr__(self):
        return 'Predicate(%s IS %s%s)' % (repr(self.subject), 'NOT ' if self.negated else '', self.category)
    def __str__(self):
        return '%s IS %s%s' % (str(self.subject), 'NOT ' if self.negated else '', self.category)

    async def evaluate(self, context: Context, scope: ItemScope) -> tuple[bool, ErrorLog]:
        subject, errors = await self.subject.evaluate(context, scope)
        neg = self.negated

        if errors.terminal:
            return None, errors

        if self.category is Predicate.Category.WHITE:
            return neg ^ (subject.isspace() or not subject), errors
        elif self.category is Predicate.Category.EMPTY:
            return neg ^ (not subject), errors
        elif self.category is Predicate.Category.BOOL:
            return neg ^ type_check(subject, parse_bool), errors
        elif self.category is Predicate.Category.FALSE:
            try: return neg ^ (parse_bool(subject) is False), errors
            except: return neg, errors
        elif self.category is Predicate.Category.TRUE:
            try: return neg ^ (parse_bool(subject) is True), errors
            except: return neg, errors
        elif self.category is Predicate.Category.INT:
            return neg ^ type_check(subject, int), errors
        elif self.category is Predicate.Category.FLOAT:
            return neg ^ type_check(subject, float), errors
        raise Exception()


# ======================== Aggregate Predicate

class AggregatePredicate(RootCondition):
    class Type:
        ANYTHING = 'ANYTHING'
        NOTHING = 'NOTHING'

    def __init__(self, negated: bool, type: Type):
        self.negated = negated
        self.type = type

    @classmethod
    def from_parsed(cls, result: ParseResults):
        simple_agg = result['simple_agg_predicate']
        negated = bool(simple_agg.get('not'))
        type = getattr(AggregatePredicate.Type, simple_agg['type'])
        return AggregatePredicate(negated, type)

    @classmethod
    def from_string(cls, string: str):
        return cls.from_parsed(grammar.agg_predicate.parse_string(string, True))

    def __repr__(self):
        return 'AggregatePredicate(%s)' % str(self)
    def __str__(self):
        return '%s%s' % ('NOT ' if self.negated else '', self.type)

    async def evaluate(self, context: Context, scope: ItemScope) -> tuple[bool, ErrorLog]:
        neg = self.negated
        if self.type is AggregatePredicate.Type.ANYTHING:
            return neg ^ bool(scope.items), None
        if self.type is AggregatePredicate.Type.NOTHING:
            return neg ^ (not scope.items), None
        raise Exception()


# ======================================== Joined Conditions =======================================

class JoinedCondition(Condition):
    children: list[Condition]

    def __init__(self, children: list[Condition]):
        self.children = children

    def __repr__(self):
        return '(' + (' ' + self.joiner + ' ').join(repr(c) for c in self.children) + ')'
    def __str__(self):
        return '(' + (' ' + self.joiner.lower() + ' ').join(str(c) for c in self.children) + ')'

    def get_pre_errors(self) -> ErrorLog | None:
        pre_errors = ErrorLog()
        for child in self.children:
            child_pre_errors = child.get_pre_errors()
            if child_pre_errors is not None:
                pre_errors.extend(child_pre_errors)
        return pre_errors

class Conjunction(JoinedCondition):
    joiner = 'AND'

    async def evaluate(self, context: Context, scope: ItemScope) -> tuple[bool, ErrorLog]:
        errors = ErrorLog()
        for child in self.children:
            value, child_errors = await child.evaluate(context, scope)
            if errors.extend(child_errors).terminal:
                return None, errors
            if not value:
                return False, errors
        return True, errors

class Disjunction(JoinedCondition):
    joiner = 'OR'

    async def evaluate(self, context: Context, scope: ItemScope) -> tuple[bool, ErrorLog]:
        errors = ErrorLog()
        for child in self.children:
            value, child_errors = await child.evaluate(context, scope)
            if errors.extend(child_errors).terminal:
                return None, errors
            if value:
                return True, errors
        return False, errors


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

    def get_pre_errors(self) -> ErrorLog | None:
        return self.child.get_pre_errors()

    async def evaluate(self, context: Context, scope: ItemScope) -> tuple[bool, ErrorLog]:
        value, errors = await self.child.evaluate(context, scope)
        return (None if value is None else not value), errors
