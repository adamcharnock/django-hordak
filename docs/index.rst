Django Hordak
=============

Django Hordak is the core functionality of a double entry accounting system.
It provides thoroughly tested core models with relational integrity constrains
to ensure consistency.

Hordak also includes a basic accounting interface. This should allow you to get
up-and-running quickly. However, the expectation is that you will either heavily
build on this example or use one of the interfaces detailed below.

Interfaces which build on Hordak include:

.. _interfaces:

 * `battlecat`_ – General purpose accounting interface (work in progress)
 * `swiftwind`_ – Accounting for communal households (work in progress)

Requirements
------------

Hordak is `tested against`_:

 * Django >= 1.8, <= 1.10
 * Python 2.7, 3.4, 3.5, nightly
 * Postgres 9

Postgres is required, MySQL is unsupported. This is due to the database constraints we apply to
ensure data integrity. MySQL could be certainly supported in future, volunteers welcome.

.. toctree::
    :maxdepth: 2
    :caption: Contents:

    installation
    getting-started
    customising-templates
    accounting-for-developers
    api/index
    notes
    changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _swiftwind: https://github.com/adamcharnock/swiftwind
.. _battlecat: https://github.com/adamcharnock/battlecat
.. _tested against: https://travis-ci.org/adamcharnock/django-hordak
