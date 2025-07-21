'''
A TemplatedString is a sets of dynamic Templated Elements to be interpolated into a static string by evaluating them.
Templated Elements need to be evaluated to yield strings, and may vary depending state, context or nondeterminism.
'''

import asyncio
from pyparsing import ParseBaseException, ParseResults
from itertools import product as iter_product
from enum import Enum

from ..state import ErrorLog, Context, ItemScope, ItemScopeError
from .. import grammar
# NOTE: Additional, circular imports below


# Sentinel objects used by TemplatedString.evaluate()
class FutureSentinel(Enum):
    SOURCE = object()
    COND = object()
    SCRIPT = object()


class TemplatedString:
    '''
    Class representing a string that may contain TemplatedElements, and which can be evaluated to yield strings.

    A primitive data structure of Rezbot Scripts, but also theoretically capable of touching on nearly any kind of scripting feature.

    If there is no need to hold on to the parsed TemplatedString, the static methods `evaluate_string` and `evaluate_origin` can be used instead.
    '''

    pieces: list['str | TemplatedElement']
    pre_errors: ErrorLog
    end_index: int = -1

    is_string = False
    string: str = None

    is_item = False
    item: 'TmplItem' = None

    is_source = False
    source: 'TmplSource' = None

    is_inline_script = False
    inline_script: 'TmplInlineScript' = None

    def __init__(self, pieces: list['str | TemplatedElement'], start_index: int=0, index_items=True, pre_errors=None):
        self.pieces = pieces
        self.pre_errors = ErrorLog() if pre_errors is None else pre_errors
        if index_items:
            self.assign_implicit_item_indices(start_index)
        self._flush()

    @staticmethod
    def from_parsed(result: ParseResults=[], start_index=0):
        pre_errors = ErrorLog()
        pieces: list[str | TemplatedElement] = []

        # Match and parse the different kinds of pieces that make up the TemplatedString
        for result_piece in result:
            if isinstance(result_piece, str):
                pieces.append(result_piece)
                continue

            match result_piece._name:
                case 'te_special':
                    try:
                        symbol = TmplSpecialSymbol.from_parsed(result_piece)
                        pieces.append(symbol)
                    except ValueError as v:
                        pre_errors.log(str(v), terminal=True)

                case 'te_script':
                    inline_script = TmplInlineScript.from_parsed(result_piece)
                    pieces.append(inline_script)
                    pre_errors.extend(inline_script.script.get_static_errors(), 'inline script')

                case 'implicit_item' | 'explicit_item':
                    item = TmplItem.from_parsed(result_piece)
                    pieces.append(item)

                case 'conditional':
                    conditional = TmplConditional.from_parsed(result_piece)
                    pieces.append(conditional)
                    # TODO: Pre-errors

                case 'source':
                    source = TmplSource.from_parsed(result_piece)
                    pieces.append(source)
                    pre_errors.steal(source.pre_errors, source.name)

                case _:
                    raise Exception(f'Unexpected ParseResults._name: {result_piece._name}')

        return TemplatedString(pieces, start_index, pre_errors=pre_errors)

    @staticmethod
    def from_string(string: str):
        parsed = grammar.absolute_templated_string.parse_string(string, parse_all=True)
        return TemplatedString.from_parsed(parsed)

    # ================ Initialization: Implicit item indices

    def assign_implicit_item_indices(self, start_index):
        ''' Runs through all implicitly indexed items and assigns them increasing indices, or recursively adjusts existing ones. '''
        item_index = start_index
        has_explicit, has_implicit = False, False
        # TODO: this currently does not work as intended due to nesting:
        # "{} {roll max={}} {}" == "{0} {roll max={0}} {1}"
        # TODO: Maybe literally just not allow implicit indices outside of top-level templatedstrings
        for piece in self.pieces:
            # TODO: Account for ParsedConditional
            if isinstance(piece, TmplSource):
                item_index = piece.args.adjust_implicit_item_indices(item_index)
            elif isinstance(piece, TmplItem):
                if not piece.is_implicit:
                    has_explicit = True
                else:
                    has_implicit = True
                    piece.index = item_index
                    item_index += 1

        self.end_index = item_index

        if has_explicit and has_implicit:
            self.pre_errors.log('Do not mix empty `{}`\'s with numbered `{}`\'s!', True)

    def adjust_implicit_item_indices(self, new_start_index):
        ''' Recursively adjust all implicit item indices by a flat amount and return the new end index. '''
        for piece in self.pieces:
            # TODO: Account for ParsedConditional
            if isinstance(piece, TmplSource):
                piece.args.adjust_implicit_item_indices(new_start_index)
            elif isinstance(piece, TmplItem) and piece.is_implicit:
                piece.index += new_start_index
        self.end_index += new_start_index
        return self.end_index

    # ================ Representation

    def __repr__(self):
        return 'TStr(%s)' % ', '.join(repr(x) for x in self.pieces)
    def __str__(self):
        return '"' + ''.join(str(x) for x in self.pieces) + '"'
    def __bool__(self):
        # A working TemplatedString is falsey if and only if it represents the static empty string.
        return not (self.is_string and not self.pieces[0])

    # ================ Manipulation

    def _flush(self):
        '''Performs minor optimizations and simplifications either after creation or modification.'''

        ## Join consecutive strings, drop empty strings
        new_pieces = []
        running_str = []
        for piece in self.pieces:
            if isinstance(piece, str):
                running_str.append(piece)
            else:
                if running_str:
                    if joint := ''.join(running_str): new_pieces.append(joint)
                    running_str.clear()
                new_pieces.append(piece)
        if running_str:
            if joint := ''.join(running_str): new_pieces.append(joint)
            running_str.clear()
        self.pieces = new_pieces

        ## Normalise an empty list as a list of a single empty string
        self.pieces = self.pieces or ['']

        ## Determine if we're a very simple kind of TemplatedString
        if len(self.pieces) == 1:
            # TODO: Account for ParsedSpecialSymbols as well
            self.is_string = isinstance(self.pieces[0], str) and not self.pre_errors
            if self.is_string: self.string = self.pieces[0]

            self.is_item = isinstance(self.pieces[0], TmplItem)
            if self.is_item: self.item = self.pieces[0]

            self.is_source = isinstance(self.pieces[0], TmplSource)
            if self.is_source: self.source = self.pieces[0]

            self.is_inline_script = isinstance(self.pieces[0], TmplInlineScript)
            if self.is_inline_script: self.inline_script = self.pieces[0]

        return self

    @staticmethod
    def join(tstrings: list['TemplatedString'], sep=" ") -> 'TemplatedString':
        ''' Joins the TemplatedStrings together as one long TemplatedString, without re-indexing implicit items. '''

        # Gather each TString's pieces in a single list, with separators between them
        pieces = []
        first = True
        for ts in tstrings:
            if not first and sep: pieces.append(sep)
            first = False
            pieces += ts.pieces

        # Gather each TString's pre-errors
        pre_errors = ErrorLog()
        for ts in tstrings:
            pre_errors.extend(ts.pre_errors)

        return TemplatedString(pieces, index_items=False, pre_errors=pre_errors)

    def unquote(self):
        ''' Modifies the TemplatedString in-place to remove wrapping string delimiters, if any. '''
        pieces = self.pieces

        if isinstance(pieces[0], str) and isinstance(pieces[-1], str):
            if pieces[0][:3] == pieces[-1][-3:] == '"""' and not (self.is_string and len(pieces[0]) < 6):
                pieces[0] = pieces[0][3:]
                pieces[-1] = pieces[-1][:-3]
            elif pieces[0][:1] == pieces[-1][-1:] in ('"', "'", '/') and not (self.is_string and len(pieces[0]) < 2):
                pieces[0] = pieces[0][1:]
                pieces[-1] = pieces[-1][:-1]

        return self._flush()

    def strip(self):
        ''' Modifies the TemplatedString in-place to remove leading or trailing spaces in static parts, if any. '''
        pieces = self.pieces
        if isinstance(pieces[0], str):
            pieces[0] = pieces[0].lstrip()
        if isinstance(pieces[-1], str):
            pieces[-1] = pieces[-1].rstrip()
        return self._flush()

    def split_implicit_arg(self, greedy: bool) -> tuple['TemplatedString', 'TemplatedString | None']:
        ''' Splits the TemplatedString into an implicit arg and a "remainder" TemplatedString. '''
        if greedy:
            return self.unquote(), None
        else:
            # This applies the TemplatedString version of .split(' ', 1), probably doesn't need to be more than this.
            implicit = []
            remainder = []
            for i in range(len(self.pieces)):
                piece = self.pieces[i]
                if isinstance(piece, str):
                    if ' ' in piece:
                        piece1, piece2 = piece.split(' ', 1)
                        implicit.append(piece1)
                        remainder = [piece2] + self.pieces[i+1:]
                        break
                    else:
                        implicit.append(piece)
                else:
                    implicit.append(piece)

            return TemplatedString(implicit).unquote(), TemplatedString(remainder)

    # ================ Evaluation

    async def evaluate(self, context: Context, scope: ItemScope=None) -> tuple[str|None, ErrorLog]:
        ''' Evaluate the TemplatedString into a single string. '''
        if self.is_string:
            return self.string, ErrorLog()

        intermediate, errors = await self._intermediate_evaluate(context, scope)
        if errors.terminal:
            return None, errors

        # Flatten the intermediate values down to a single string,
        #   only taking the first string out of any list of choices, or the empty string for an empty choice.
        flattened_str = ''.join(x if isinstance(x, str) else x[0] if x else '' for x in intermediate)
        return flattened_str, errors

    async def multiple_evaluate(self, context: Context, scope: ItemScope=None) -> tuple[list[str]|None, ErrorLog]:
        ''' Evaluate the TemplatedString into a list of strings, one for every combination of the templated element's produced values. '''
        if self.is_string:
            return [self.string], ErrorLog()

        intermediate, errors = await self._intermediate_evaluate(context, scope)
        if errors.terminal:
            return None, errors

        # Convert intermediate values to all be lists of strings (even if single strings)
        choices_list: list[list[str]] = []
        for item in intermediate:
            if isinstance(item, str):
                choices_list.append((item,))
            else:
                choices_list.append(item)

        strings = []
        # Double reversed because we want the combinations to vary left-to-right
        for combo in iter_product(*reversed(choices_list)):
            strings.append(''.join(reversed(combo)))

        return strings, errors

    async def _intermediate_evaluate(self, context: Context, scope: ItemScope=None) -> tuple[list[str|list[str]]|None, ErrorLog]:
        ''' Evaluate the TemplatedString into an intermediate form, either to be flattened or multiplied later. '''
        errors = ErrorLog()
        errors.extend(self.pre_errors)
        NOTHING_BUT_ERRORS = (None, errors)

        if errors.terminal:
            return NOTHING_BUT_ERRORS
        if self.is_string:
            return [self.string], errors

        pieces: list[str|list[str]|FutureSentinel] = []
        futures = []

        ## Go through our pieces and collect either immediately retrievable strings,
        #   lists of strings, or coroutines (i.e. futures).
        for piece in self.pieces:
            if isinstance(piece, str):
                pieces.append(piece)

            elif isinstance(piece, TmplSpecialSymbol):
                pieces.append(piece.symbol)

            elif isinstance(piece, TmplItem):
                try:
                    items = piece.evaluate(scope)
                    pieces.append(items)
                except ItemScopeError as e:
                    msg = f'Error filling in item `{piece}`:\n\tItemScopeError: {e}'
                    errors.log(msg, True)

            elif isinstance(piece, TmplSource) and not errors.terminal:
                pieces.append(FutureSentinel.SOURCE)
                futures.append(piece.evaluate(context, scope))

            elif isinstance(piece, TmplConditional) and not errors.terminal:
                pieces.append(FutureSentinel.COND)
                futures.append(piece.evaluate(context, scope))

            elif isinstance(piece, TmplInlineScript) and not errors.terminal:
                pieces.append(FutureSentinel.SCRIPT)
                futures.append(piece.evaluate(context, scope))

        if errors.terminal:
            return NOTHING_BUT_ERRORS

        ## Await all future results at once
        future_results = await asyncio.gather(*futures)

        ## Correctly interleave the collected results and future results
        results: list[str|list[str]] = []
        future_index = 0
        for piece in pieces:
            if isinstance(piece, (str, list)):
                results.append(piece)

            elif piece in (FutureSentinel.SOURCE, FutureSentinel.SCRIPT):
                items, src_errors = future_results[future_index]
                errors.extend(src_errors)
                if not errors.terminal:
                    results.append(items)
                future_index += 1

            elif piece is FutureSentinel.COND:
                string, cond_errors = future_results[future_index]
                errors.extend(cond_errors)
                if not errors.terminal:
                    results.append(string)
                future_index += 1

            else:
                raise Exception()

        if errors.terminal:
            return NOTHING_BUT_ERRORS

        return results, errors

    # ================ Specific fast-tracked use cases

    @staticmethod
    async def evaluate_string(string: str, context: Context, scope: ItemScope=None, force_single=False) -> tuple[list[str] | None, ErrorLog]:
        '''
        Takes a raw source string, evaluates {sources} and returns the list of values.

        If force_single=False, a pure "{source}" string may generate more (or less!) than 1 value.
        '''
        errors = ErrorLog()
        NOTHING_BUT_ERRORS = (None, errors)
        try:
            template = TemplatedString.from_string(string)
            errors.extend(template.pre_errors)
            if errors.terminal:
                return NOTHING_BUT_ERRORS
        except ParseBaseException as e:
            errors.log_parse_exception(e)
            return NOTHING_BUT_ERRORS

        if not force_single:
            if template.is_item:
                vals = template.item.evaluate(scope)
                return vals, errors
            elif template.is_source:
                vals, errs = await template.source.evaluate(context, scope)
                return vals, errors.extend(errs)
            elif template.is_inline_script:
                vals, errs = await template.inline_script.evaluate(context, scope)
                return vals, errors.extend(errs)

        val, errs = await template.evaluate(context, scope)
        return [val], errors.extend(errs)

    @staticmethod
    async def map_evaluate(tstrings: list['TemplatedString'], context: Context, scope: ItemScope=None) -> tuple[list[str] | None, ErrorLog]:
        '''Evaluates and aggregates each TemplatedString in an iterable sequentially, pure Source TStrings can yield multiple strings.'''
        errors = ErrorLog()

        values = []
        for tstring in tstrings:
            if tstring.is_item:
                try:
                    vals = tstring.item.evaluate(scope)
                except ItemScopeError as e:
                    msg = f'Error filling in item `{tstring.item}`:\n\tItemScopeError: {e}'
                    errors.log(msg, True)
                if not errors.terminal: values.extend(vals)
            elif tstring.is_source:
                vals, errs = await tstring.source.evaluate(context, scope)
                errors.extend(errs)
                if not errors.terminal: values.extend(vals)
            elif tstring.is_inline_script:
                vals, errs = await tstring.inline_script.evaluate(context, scope)
                errors.extend(errs)
                if not errors.terminal: values.extend(vals)
            else:
                val, errs = await tstring.evaluate(context, scope)
                errors.extend(errs)
                if not errors.terminal: values.append(val)

        return (values if not errors.terminal else None, errors)


# Circular imports
from ..pipeline import Pipeline # Load-bearing unused import
from .templated_element import TmplItem, TmplSource, TmplConditional, TmplInlineScript, TmplSpecialSymbol, TemplatedElement
