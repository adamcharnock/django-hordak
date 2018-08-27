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
