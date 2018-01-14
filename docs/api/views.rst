.. _api_views:

Views
=====

.. contents::

Hordak provides a number of off-the-shelf views to aid in development. You may
need to implement your own version of (or extend) these views in order
to provide customised functionality.

Extending views
---------------

To extend a view you will need to ensure Django loads it by updating your ``urls.py`` file.
To do this, alter you current urls.py:

.. code:: python

    # Replace this
    urlpatterns = [
        ...
        url(r'^', include('hordak.urls', namespace='hordak'))
    ]

And changes it as follows, copying in the patterns from hordak's root ``urls.py``:

.. code:: python

    # With this
    from hordak import views as hordak_views

    hordak_urls = [
        ... patterns from Hordak's root urls.py ...
    ]

    urlpatterns = [
        url(r'^admin/', admin.site.urls),

        url(r'^', include(hordak_urls, namespace='hordak', app_name='hordak')),
        ...
    ]


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

AccountTransactionView
~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: hordak.views.AccountTransactionsView
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
