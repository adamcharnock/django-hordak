Currency
========

.. contents::

.. automodule:: hordak.utilities.currency

Currency Exchange
-----------------

The ``currency_exchange()`` helper function is provided to assist in creating
currency conversion Transactions.

.. autofunction:: hordak.utilities.currency.currency_exchange

Balance
-------

.. autoclass:: hordak.utilities.currency.Balance
    :members:

Exchange Rate Backends
----------------------

.. autoclass:: hordak.utilities.currency.BaseBackend
    :members:
    :private-members:

.. autoclass:: hordak.utilities.currency.FixerBackend
    :members:
