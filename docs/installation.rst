Installation
============

Installation using pip::

    pip install django-hordak

Add to installed apps:

.. code:: python

    INSTALLED_APPS = [
        ...
        'hordak',
    ]

Run the migrations::

    ./manage.py migrate

You should now be able to import from Hordak:

.. code:: python

    from hordak.models import Account, Transaction, ...
