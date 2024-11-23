'''
There are five types of Templated Elements:

    * Item: e.g. {}, {0}, {^1}, {2!}, {^^3!}
        These are (implicit) indexes pointing out items to use from the provided ItemScope.

    * Source: e.g. {word}, {word query=foo}, {txt bible sequential=false}
        These are evaluated as calls to their respective Source.

    * Conditional: e.g. {?foo if {0}=='bar' else baz}, {?{word} if {arg 1} LIKE /^foo/ and {get baz} != zip else {arg 2}}
        These represent an (if_case: TemplatedString, condition: Condition, else_case: TemplatedString) tuple,
            the Condition is evaluated based on both ItemScope and Context, and then depending on its value,
            either `if_case` or `else_case` is evaluated.

    * InlineScript: e.g. {>> {word} > find_all . > join +}
        The script (whose syntax is limited) is evaluated.

    * Special: e.g. {\n}, {\t}
        These are simply replaced by respective '\n' and '\t' special characters at parse time.
'''

from typing import TypeAlias

from .tmpl_item import TmplItem
from .tmpl_source import TmplSource
from .tmpl_conditional import TmplConditional
from .tmpl_special_symbol import TmplSpecialSymbol
from .tmpl_inline_script import TmplInlineScript


TemplatedElement: TypeAlias = TmplItem | TmplSource | TmplConditional | TmplSpecialSymbol | TmplInlineScript
