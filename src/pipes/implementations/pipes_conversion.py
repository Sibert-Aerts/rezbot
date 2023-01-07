from currency_converter import CurrencyConverter, SINGLE_DAY_ECB_URL

from .pipes import pipe_from_class, one_to_one, set_category
from ..signature import Par, Option, with_signature
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

    @with_signature(**{
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
        return str(PipeCurrency._converter.convert(int(text), from_, to))
