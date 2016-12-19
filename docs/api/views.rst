Views
=====

.. contents::

Hordak provides a number of off-the-shelf views to aid in development. You may
need to implement your own version of (or extend) these views in order
to provide customised functionality.

Accounts
--------

AccountListView
~~~~~~~~~~~~~~~

.. autoclass:: hordak.views.AccountListView
    :members:
    :undoc-members:

AccountCreateView
~~~~~~~~~~~~~~~~~

.. autoclass:: hordak.views.AccountCreateView
    :members:
    :undoc-members:

AccountUpdateView
~~~~~~~~~~~~~~~~~

.. autoclass:: hordak.views.AccountUpdateView
    :members:
    :undoc-members:

Transactions
------------

TransactionCreateView
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: hordak.views.TransactionCreateView
    :members:
    :undoc-members:

TransactionsReconcileView
~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: hordak.views.TransactionsReconcileView
    :members: template_name, model, paginate_by, context_object_name, ordering, success_url
    :undoc-members:
