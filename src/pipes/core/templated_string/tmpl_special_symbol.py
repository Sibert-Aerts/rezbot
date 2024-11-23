from pyparsing import ParseResults


class TmplSpecialSymbol:
    ''' Templated element representing some otherwise hard to type special symbol. '''
    SPECIAL_SYMBOL_MAP = {
        'n': '\n',
        't': '\t',
    }

    __slots__ = ('symbol')
    symbol: str

    def __init__(self, symbol: str):
        self.symbol = symbol

    @staticmethod
    def from_parsed(result: ParseResults):
        name = result.get('name')
        symbol = TmplSpecialSymbol.SPECIAL_SYMBOL_MAP.get(name)
        if symbol is None:
            raise ValueError(f'Unknown special symbol "\{name}".')
        return TmplSpecialSymbol(symbol)

    def __repr__(self):
        return 'SpecialSymbol(%s)' % repr(self.symbol)
    def __str__(self):
        return '{%s}' % repr(self.symbol)[1:-1]
