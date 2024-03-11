from currency_converter import CurrencyConverter, SINGLE_DAY_ECB_URL
from pint import UnitRegistry

from .pipes import pipe_from_class, one_to_one, set_category
from pipes.core.signature import Par, Option, with_signature, parse_bool
from utils.util import format_doc


#####################################################
#                Pipes : CONVERSION                 #
#####################################################
set_category('CONVERSION')

CURRENCIES = [
    'EUR', 'USD', 'JPY', 'BGN', 'CYP', 'CZK', 'DKK', 'EEK', 'GBP', 'HUF', 'LTL', 'LVL', 'MTL', 'PLN',
    'ROL', 'RON', 'SEK', 'SIT', 'SKK', 'CHF', 'ISK', 'NOK', 'HRK', 'RUB', 'TRL', 'TRY', 'AUD', 'BRL',
    'CAD', 'CNY', 'HKD', 'IDR', 'ILS', 'INR', 'KRW', 'MXN', 'MYR', 'NZD', 'PHP', 'SGD', 'THB', 'ZAR',
]
Currency = Option(*CURRENCIES, name='Currency', prefer_upper=True, stringy=True)

@pipe_from_class
class PipeCurrency:
    name = 'currency'
    command = True

    _converter = None

    @with_signature({
        'from': Par(Currency, None, 'Currency to convert from'),
        'to':   Par(Currency, None, 'Currency to convert to'),
    })
    @one_to_one
    @format_doc(currencies=', '.join(CURRENCIES))
    def pipe_function(text, *, to, **kwargs):
        '''
        Convert between currencies by present day exchange rates.

        Valid currencies: {currencies}
        '''
        if PipeCurrency._converter is None:
            # Fetch today's exchange rates
            PipeCurrency._converter = CurrencyConverter(SINGLE_DAY_ECB_URL)

        from_ = kwargs['from']
        return format(PipeCurrency._converter.convert(float(text), from_, to), '.2f')


UNIT = UnitRegistry(autoconvert_offset_to_baseunit=True)
UNIT_FORMAT = Option('none', 'wide', 'compact', 'pretty', name='Unit format')

@pipe_from_class
class PipeUnit:
    name = 'unit'
    command = True

    @with_signature({
        'from':   Par(str, None, 'Unit to convert from'),
        'to':     Par(str, None, 'Unit to convert to', required=False),
        'format': Par(UNIT_FORMAT, 'none', 'How the unit output should be formatted: none/wide/compact/pretty).'),
        'short':  Par(parse_bool, True, 'Whether to use abbreviations for unit output.'),
        'digits': Par(int, None, 'Force a specific number of digits to show.', required=False, check=lambda n: n >=0),
    })
    def pipe_function(items, *, to, format, short, digits, **kwargs):
        '''
        Convert between units of measurement, treating input items as quantities.
        
        Blank inputs are treated as a quantity of 1.
        When no input items are given at all, simply converts the given two units once.

        Uses python package `pint` for parsing and converting units.
        '''
        # Special case where the quantity is presumably in the from argument
        if len(items) == 0:
            items = ['']

        unit_from = UNIT(kwargs['from'])
        unit_to = UNIT(to) if to else False
        
        # Build the format flag
        if format == UNIT_FORMAT.none:
            format_flag = ''
            if digits is not None:
                format_flag = '.' + str(digits) + 'f' + format_flag
            format_format = '{:' + format_flag + '}'
        else:
            format_flag = 'P' if format == UNIT_FORMAT.pretty else 'C' if format == UNIT_FORMAT.compact else 'D'
            if short:
                format_flag += '~'
            if digits is not None:
                format_flag = '.' + str(digits) + 'f' + format_flag
            format_format = '{:' + format_flag + '}'

        res = []
        for item in items:
            magnitude = float(item) if item.strip() else 1
            quantity_from = magnitude * unit_from
            quantity_result = quantity_from.to(unit_to) if unit_to is not False else quantity_from

            if format == UNIT_FORMAT.none:
                res.append(format_format.format(quantity_result.magnitude))
            else:
                res.append(format_format.format(quantity_result))

        return res
