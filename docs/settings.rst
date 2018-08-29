.. _settings:

Settings
========

You can set the following your project's ``settings.py`` file:

DEFAULT_CURRENCY
----------------

Default: ``"EUR"``

The default currency to use when creating new accounts

CURRENCIES
----------

Default: ``[]``

Any currencies (additional to ``DEFAULT_CURRENCY``) that you will wish to create accounts in.
For example, you may have ``"EUR"`` for your ``DEFAULT_CURRENCY``, and ``["USD", "GBP"]`` for your
additional ``CURRENCIES``.


HORDAK_DECIMAL_PLACES
---------------------

Default: ``2``

Number of decimal places that is used for storing monetary values in ``Decimal`` data type.


HORDAK_MAX_DIGITS
-----------------

Default: ``13``

Number of maximal numer of digits allowed in monetary values (which are stored in ``Decimal`` data type). Decimal places both right and left of decimal point are counted.
