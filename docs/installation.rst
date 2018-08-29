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

If you need different than default values of the ``HORDAK_DECIMAL_PLACES`` and ``HORDAK_MAX_DIGITS`` variables
in :ref:`settings <settings>` it is right time to do it before running migrations.
If you would want to change these values in future, you will have
to deal with creating and maintaining your own ``hordak`` migration for that.

Run the migrations::

    ./manage.py migrate

Using the interface
-------------------

Hordak comes with a basic interface. The intention is that you will either build on it, or use a
:ref:`another interface <interfaces>`. To get started with the example interface you can add the
following to your ``urls.py``:

.. code:: python

    urlpatterns = [
        ...
        url(r'^', include('hordak.urls', namespace='hordak'))
    ]

You should then be able to create a user and start the development server
(assuming you ran the migrations as detailed above):

.. code::

    # Create a user to login as
    ./manage.py createsuperuser
    # Start the development server
    ./manage.py runserver

And now navigate to http://127.0.0.1:8000/.


Using the models
----------------

Hordak's primary purpose is to provide a set of robust models with which you can model the core of a
double entry accounting system. Having completed the above setup you should be able to import these
models and put them to use.

.. code:: python

    from hordak.models import Account, Transaction, ...

You can find further details in the :ref:`API documentation <api>`.
You may also find the :ref:`accounting for developers <accounting_for_developers>` section useful.

.. _django-mptt: https://github.com/django-mptt/django-mptt
