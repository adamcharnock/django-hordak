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

Any currencies (additional to ``DEFAULT_CURRENCY``) for which you wish to create accounts.
For example, you may have ``"EUR"`` for your ``DEFAULT_CURRENCY``, and ``["USD", "GBP"]`` for your
additional ``CURRENCIES``.


HORDAK_DECIMAL_PLACES
---------------------

Default: ``2``

Number of decimal places available within monetary values.


HORDAK_MAX_DIGITS
-----------------

Default: ``13``

Maximum number of digits allowed in monetary values.
Decimal places both right and left of decimal point are included in this count.
Therefore a maximum value of 9,999,999.999 would require ``HORDAK_MAX_DIGITS=10``
and ``HORDAK_DECIMAL_PLACES=3``.
