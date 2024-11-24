from pyparsing import ParseResults

from ..state import ErrorLog, Context, ItemScope
from ..executable_script import ExecutableScript


class TmplInlineScript:
    ''' Class representing an inline script inside a TemplatedString. '''

    def __init__(self, script: 'ExecutableScript'):
        self.script = script

    @staticmethod
    def from_parsed(parsed: ParseResults):
        return TmplInlineScript(ExecutableScript.from_parsed_simple_script(parsed['inline_script']))

    def __repr__(self):
        return 'InlScript(%s)' % repr(self.script)
    def __str__(self):
        return '{>> %s}' % str(self.script)

    # ================ Evaluation

    async def evaluate(self, context: Context, scope: ItemScope) -> tuple[ list[str] | None, ErrorLog ]:
        values, errors, spout_state = await self.script.execute_without_side_effects(context, scope)
        return values, errors
