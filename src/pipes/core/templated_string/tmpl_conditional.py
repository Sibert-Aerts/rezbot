from pyparsing import ParseResults

from ..logger import ErrorLog
from ..context import Context, ItemScope


class TmplConditional:
    ''' Class representing an inline IF/ELSE conditional expression inside a TemplatedString. '''

    def __init__(self, case_if: 'templated_string.TemplatedString', condition: 'Condition', case_else: 'templated_string.TemplatedString'):
        self.case_if = case_if
        self.condition = condition
        self.case_else = case_else

    @staticmethod
    def from_parsed(parsed: ParseResults):
        case_if = templated_string.TemplatedString.from_parsed(parsed['case_if'][0])
        condition = Condition.from_parsed(parsed['condition'])
        case_else = templated_string.TemplatedString.from_parsed(parsed['case_else'][0])
        return TmplConditional(case_if, condition, case_else)

    def __repr__(self):
        return 'Conditional(%s, %s, %s)' % (repr(self.case_if), repr(self.condition), repr(self.case_else))
    def __str__(self):
        return '{? %s if %s else %s}' % (str(self.case_if), str(self.condition), str(self.case_else))

    # ================ Evaluation

    async def evaluate(self, context: Context, scope: ItemScope) -> tuple[ list[str] | None, ErrorLog ]:
        errors = ErrorLog()
        cond_value, cond_errors = await self.condition.evaluate(context, scope)
        if errors.extend(cond_errors, 'condition').terminal:
            return None, errors
        if cond_value:
            return await self.case_if.evaluate(context, scope)
        else:
            return await self.case_else.evaluate(context, scope)


# þeſe lynes art doƿn here due to dependencys circulaire
from . import templated_string
from ..conditions import Condition