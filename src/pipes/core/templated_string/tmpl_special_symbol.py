import re
from pyparsing import ParseResults


class TmplSpecialSymbol:
    ''' Deterministic templated element representing an otherwise hard to type special symbol. '''
    SPECIAL_SYMBOL_MAP = {
        'n': '\n',
        't': '\t',
    }
    UNICODE_CODE_RE = re.compile(r"^[xuU]([0-9a-fA-F]+)$")

    __slots__ = ('symbol',)
    symbol: str

    def __init__(self, symbol: str):
        self.symbol = symbol

    @staticmethod
    def from_parsed(result: ParseResults):
        name = result.get('name')

        if symbol := TmplSpecialSymbol.SPECIAL_SYMBOL_MAP.get(name):
            return TmplSpecialSymbol(symbol)

        elif match := TmplSpecialSymbol.UNICODE_CODE_RE.match(name):
            symbol_ord = int(match[1], base=16)
            return TmplSpecialSymbol(chr(symbol_ord))

        else:
            raise ValueError(f'Unknown special symbol "\{name}".')


    def __repr__(self):
        return 'SpecialSymbol(%s)' % repr(self.symbol)
    def __str__(self):
        return '{%s}' % repr(self.symbol)[1:-1]
