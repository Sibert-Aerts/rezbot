'''
A TemplatedString is a sequence of static strings and Templated Elements, meant to be evaluated to a single string.
Templated Elements need to be evaluated to yield strings, and may vary depending state, context or randomization.
'''


import asyncio
from pyparsing import ParseBaseException, ParseResults

from utils.choicetree import ChoiceTree
from .logger import ErrorLog
from .context import Context, ItemScope, ItemScopeError
from . import grammar
from .templated_element import ParsedItem, ParsedSource, ParsedConditional, ParsedInlineScript, ParsedSpecialSymbol, ParsedTemplatedElement


class TemplatedString:
    '''
    Class representing a string that may contain TemplatedElements, and which can be evaluated to yield strings.

    A primitive data structure of Rezbot Scripts, but also theoretically capable of touching on nearly any kind of scripting feature.

    If there is no need to hold on to the parsed TemplatedString, the static methods `evaluate_string` and `evaluate_origin` can be used instead.
    '''

    pieces: list[str | ParsedTemplatedElement]
    pre_errors: ErrorLog
    end_index: int = -1

    is_string = False
    string: str = None
    is_source = False
    source: 'ParsedSource' = None
    is_inline_script = False
    inline_script: 'ParsedInlineScript' = None

    def __init__(self, pieces: list[str | ParsedTemplatedElement], start_index: int=0, index_items=True, pre_errors=None):
        self.pieces = pieces
        self.pre_errors = ErrorLog() if pre_errors is None else pre_errors
        if index_items:
            self.assign_implicit_item_indices(start_index)
        self._flush()

    @staticmethod
    def from_parsed(result: ParseResults=[], start_index=0):
        pre_errors = ErrorLog()
        pieces: list[str | ParsedTemplatedElement] = []

        def append_string(s):
            if not pieces or not isinstance(pieces[-1], str):
                pieces.append(s)
            else:
                pieces[-1] += s

        # Match and parse the different kinds of pieces that make up the TemplatedString
        for result_piece in result:
            if isinstance(result_piece, str):
                append_string(result_piece)
                continue

            match result_piece._name:
                case 'te_special':
                    try:
                        item = ParsedSpecialSymbol.from_parsed(result_piece)
                        append_string(item)
                    except ValueError as v:
                        pre_errors.log(str(v), terminal=True)

                case 'te_script':
                    item = ParsedInlineScript.from_parsed(result_piece)
                    pieces.append(item)

                case 'item':
                    item = ParsedItem.from_parsed(result_piece)
                    pieces.append(item)

                case 'conditional':
                    conditional = ParsedConditional.from_parsed(result_piece)
                    pieces.append(conditional)
                    # TODO: Pre-errors

                case 'source':
                    source = ParsedSource.from_parsed(result_piece)
                    pieces.append(source)
                    pre_errors.steal(source.pre_errors, source.name)

                case _:
                    raise Exception()

        return TemplatedString(pieces, start_index, pre_errors=pre_errors)

    @staticmethod
    def from_string(string: str):
        parsed = grammar.absolute_templated_string.parse_string(string, parse_all=True)
        return TemplatedString.from_parsed(parsed)

    # ================ Initialization

    def assign_implicit_item_indices(self, start_index):
        ''' Runs through all implicitly indexed items and assigns them increasing indices, or recursively adjusts existing ones. '''
        item_index = start_index
        explicit_item, implicit_item = False, False
        # TODO: this currently does not work as intended due to nesting:
        # "{} {roll max={}} {}" == "{0} {roll max={0}} {1}"
        for piece in self.pieces:
            # TODO: Account for ParsedConditional
            if isinstance(piece, ParsedSource):
                item_index = piece.args.adjust_implicit_item_indices(item_index)
            elif isinstance(piece, ParsedItem):
                if piece.explicitly_indexed:
                    explicit_item = True
                else:
                    implicit_item = True
                    piece.index = item_index
                    item_index += 1

        self.end_index = item_index

        if explicit_item and implicit_item:
            self.pre_errors.log('Do not mix empty `{}`\'s with numbered `{}`\'s!', True)

    def adjust_implicit_item_indices(self, new_start_index):
        ''' Recursively adjust all implicit item indices by a flat amount and return the new end index. '''
        for piece in self.pieces:
            # TODO: Account for ParsedConditional
            if isinstance(piece, ParsedSource):
                piece.args.adjust_implicit_item_indices(new_start_index)
            elif isinstance(piece, ParsedItem) and not piece.explicitly_indexed:
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
        '''Performs minor optimizations and simplifications either after creation or after modification.'''

        ## For simplicity, an empty list is normalised to an empty string
        self.pieces = self.pieces or ['']

        ## Join consecutive strings
        new_pieces = []
        running_str = []
        for piece in self.pieces:
            if isinstance(piece, str):
                running_str.append(piece)
            else:
                if running_str:
                    new_pieces.append("".join(running_str))
                    running_str.clear()
                new_pieces.append(piece)
        if running_str:
            new_pieces.append("".join(running_str))
            running_str.clear()
        self.pieces = new_pieces

        ## Determine if we're a very simple kind of TemplatedString
        if len(self.pieces) == 1:
            self.is_string = isinstance(self.pieces[0], str) and not self.pre_errors
            if self.is_string: self.string = self.pieces[0]

            self.is_source = isinstance(self.pieces[0], ParsedSource)
            if self.is_source: self.source = self.pieces[0]

            self.is_inline_script = isinstance(self.pieces[0], ParsedInlineScript)
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
        errors = ErrorLog()
        errors.extend(self.pre_errors)
        NOTHING_BUT_ERRORS = (None, errors)

        if errors.terminal:
            return NOTHING_BUT_ERRORS
        if self.is_string:
            return self.string, errors

        SOURCE_FUTURE = object()
        COND_FUTURE = object()
        SCRIPT_FUTURE = object()
        results = []
        futures = []

        ## Go through our pieces and collect either immediately retrievable strings,
        #   or string-determining coroutines (i.e. futures).
        for piece in self.pieces:
            if isinstance(piece, str):
                results.append(piece)

            elif isinstance(piece, ParsedItem):
                try:
                    results.append(piece.evaluate(scope))
                except ItemScopeError as e:
                    msg = f'Error filling in item `{piece}`:\n\tItemScopeError: {e}'
                    errors.log(msg, True)

            elif isinstance(piece, ParsedInlineScript) and not errors.terminal:
                results.append(SCRIPT_FUTURE)
                futures.append(piece.evaluate(context, scope))

            elif isinstance(piece, ParsedConditional) and not errors.terminal:
                results.append(COND_FUTURE)
                futures.append(piece.evaluate(context, scope))

            elif isinstance(piece, ParsedSource) and not errors.terminal:
                results.append(SOURCE_FUTURE)
                futures.append(piece.evaluate(context, scope))

        if errors.terminal:
            return NOTHING_BUT_ERRORS

        ## Await all future results at once
        future_results = await asyncio.gather(*futures)

        ## Join the collected results and future results
        strings = []
        future_index = 0
        for result in results:
            if result in (SOURCE_FUTURE, SCRIPT_FUTURE):
                items, src_errors = future_results[future_index]
                errors.extend(src_errors)
                if not errors.terminal:
                    strings.append(items[0] if items else '')
                future_index += 1
            elif result is COND_FUTURE:
                string, cond_errors = future_results[future_index]
                errors.extend(cond_errors)
                if not errors.terminal:
                    strings.append(string)
                future_index += 1
            else:
                strings.append(result)

        if errors.terminal:
            return NOTHING_BUT_ERRORS

        return ''.join(strings), errors

    # ================ Specific fast-tracked use cases

    @staticmethod
    async def evaluate_string(string: str, context: Context, scope: ItemScope, force_single=False) -> tuple[list[str] | None, ErrorLog]:
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

        if not force_single and template.is_source:
            vals, errs = await template.source.evaluate(context, scope)
            return vals, errs
        elif not force_single and template.is_inline_script:
            vals, errs = await template.inline_script.evaluate(context, scope)
            return vals, errs
        else:
            val, errs = await template.evaluate(context, scope)
            return [val], errs

    @staticmethod
    def parse_origin(origin_str: str) -> tuple[list['TemplatedString'] | None, ErrorLog]:
        '''Takes a raw source string, expands it if necessary, and already parses each one as a TemplatedString.'''
        origins = []
        expand = True
        errors = ErrorLog()

        ## Get rid of wrapping quotes or triple quotes
        if len(origin_str) >= 6 and origin_str[:3] == origin_str[-3:] == '"""':
            origin_str = origin_str[3:-3]
            expand = False
        elif len(origin_str) >= 2 and origin_str[0] == origin_str[-1] in ('"', "'", '/'):
            origin_str = origin_str[1:-1]

        ## ChoiceTree expand
        if expand:
            try:
                expanded = ChoiceTree(origin_str, parse_flags=True)
            except ParseBaseException as e:
                errors.log_parse_exception(e)
                return origins, errors
        else:
            expanded = [origin_str]

        ## Parse each string as a TemplatedString, collecting errors along the way
        for origin_str in expanded:
            try:
                origin = TemplatedString.from_string(origin_str)
                origins.append(origin)
                errors.extend(origin.pre_errors)
            except ParseBaseException as e:
                errors.log_parse_exception(e)

        return origins, errors

    @staticmethod
    async def evaluate_origin(origin_str: str, context: Context, scope: ItemScope=None) -> tuple[list[str] | None, ErrorLog]:
        '''Takes a raw source string, expands it, evaluates {sources} in each one and returns the combined values.'''
        origins, errors = TemplatedString.parse_origin(origin_str)
        if errors.terminal:
            return (None, errors)
        values, map_errors = await TemplatedString.map_evaluate(origins, context, scope)
        errors.extend(map_errors)
        return values, errors

    @staticmethod
    async def map_evaluate(tstrings: list['TemplatedString'], context: Context, scope: ItemScope=None) -> tuple[list[str] | None, ErrorLog]:
        '''Evaluates and aggregates each TemplatedString in an iterable sequentially, pure Source TStrings can yield multiple strings.'''
        errors = ErrorLog()

        values = []
        for tstring in tstrings:
            if tstring.is_source:
                vals, errs = await tstring.source.evaluate(context, scope)
                errors.extend(errs)
                if not errors.terminal: values.extend(vals)
            if tstring.is_inline_script:
                vals, errs = await tstring.inline_script.evaluate(context, scope)
                errors.extend(errs)
                if not errors.terminal: values.extend(vals)
            else:
                val, errs = await tstring.evaluate(context, scope)
                errors.extend(errs)
                if not errors.terminal: values.append(val)

        return (values if not errors.terminal else None, errors)
