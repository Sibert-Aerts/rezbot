from pyparsing import ParseResults

from ..state import ErrorLog, Context, ItemScope
from ..pipeline import Pipeline


class TmplInlineScript:
    ''' Class representing an inline script inside a TemplatedString. '''

    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline

    @staticmethod
    def from_parsed(parsed: ParseResults):
        return TmplInlineScript(Pipeline.from_parsed_simple_script_or_pipeline(parsed['inline_script']))

    def __repr__(self):
        return 'InlScript(%s)' % repr(self.pipeline)
    def __str__(self):
        return '{>> %s}' % str(self.pipeline)

    # ================ Evaluation

    async def evaluate(self, context: Context, scope: ItemScope=None) -> tuple[ list[str] | None, ErrorLog ]:
        items = scope.items if scope is not None else ()
        values, errors, spout_state = await self.pipeline.apply(items, context, scope)
        return values, errors
