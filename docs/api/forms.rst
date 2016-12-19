Forms
=====

.. contents::

As with views, Hordak provides a number of off-the-shelf forms. You may
need to implement your own version of (or extend) these forms in order
to provide customised functionality.

SimpleTransactionForm
---------------------

.. autoclass:: hordak.forms.SimpleTransactionForm

TransactionForm
---------------

.. autoclass:: hordak.forms.TransactionForm

LegForm
-------

.. autoclass:: hordak.forms.LegForm

LegFormSet
----------

A formset which can be used to display multiple :class:`Leg forms <hordak.forms.LegForm>`.
Useful when creating transactions.
