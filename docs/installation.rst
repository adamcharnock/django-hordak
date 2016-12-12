Installation
============

Installation using pip::

    pip install django-hordak

Add to installed apps:

.. code:: python

    INSTALLED_APPS = [
        ...
        'mptt',
        'hordak',
    ]

.. note::

    Hordak uses `django-mptt`_ to provide the account tree structure. It must therefore be listed
    in ``INSTALLED_APPS`` as shown above.

Run the migrations::

    ./manage.py migrate

You should now be able to import from Hordak:

.. code:: python

    from hordak.models import Account, Transaction, ...


.. _django-mptt: https://github.com/django-mptt/django-mptt
