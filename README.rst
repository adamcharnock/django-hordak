django-hordak
=============

**Double entry bookkeeping in Django.**

Django Hordak provides a `simple model layer`_ for a double-entry accounting
system. The intention is not to provide a full-featured app, but rather
to provide a reliable foundation on which to build such apps.

.. image:: https://img.shields.io/pypi/v/django-hordak.svg
    :target: https://badge.fury.io/py/django-hordak

.. image:: https://img.shields.io/github/license/adamcharnock/django-hordak.svg
    :target: https://pypi.python.org/pypi/django-hordak/

.. image:: https://travis-ci.org/adamcharnock/django-hordak.svg?branch=master
    :target: https://travis-ci.org/adamcharnock/django-hordak/

.. image:: https://coveralls.io/repos/github/adamcharnock/django-hordak/badge.svg?branch=master
    :target: https://coveralls.io/github/adamcharnock/django-hordak?branch=master

Documentation
-------------

Documentation can be found at: http://django-hordak.readthedocs.io/

Related Projects
----------------

Django Hordak is the core functionality of a double entry accounting system.
It provides thoroughly tested core models with relational integrity constrains
to ensure consistency.

Interfaces which build on Hordak include:

 * `battlecat`_ – General purpose accounting interface (work in progress)
 * `swiftwind`_ – Accounting for communal households (work in progress)


django-hordak is packaged using seed_.

.. _seed: https://github.com/adamcharnock/seed/
.. _swiftwind: https://github.com/adamcharnock/swiftwind/
.. _simple model layer: https://github.com/adamcharnock/django-hordak/blob/master/hordak/models.py
.. _battlecat: https://github.com/adamcharnock/battlecat
