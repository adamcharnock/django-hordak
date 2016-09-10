django-hordak
===========================================================

**Double entry book keeping in Django.**

The initial priority is to ensure the model layer works reliably.
Ultimately the intention is to integrate this with swiftwind_ to provide
an accounting & billing system for a communal household. This interface
should be intuitive and suitable for non-experts.

.. image:: https://img.shields.io/pypi/v/django-hordak.svg
    :target: https://badge.fury.io/py/django-hordak

.. image:: https://img.shields.io/pypi/dm/django-hordak.svg
    :target: https://pypi.python.org/pypi/django-hordak

.. image:: https://img.shields.io/github/license/waldocollective/django-hordak.svg
    :target: https://pypi.python.org/pypi/django-hordak/

.. image:: https://travis-ci.org/waldocollective/django-hordak.svg?branch=master
    :target: https://travis-ci.org/waldocollective/django-hordak/

.. image:: https://coveralls.io/repos/github/waldocollective/django-hordak/badge.svg?branch=master
    :target: https://coveralls.io/github/waldocollective/django-hordak?branch=master

Installation
------------

Installation using pip::

    pip install django-hordak  # Release coming soon

Tested against:

- Django >= 1.8, <= 1.10
- Python 2.7, 3.4, 3.5, nightly
- Postgres 9

Hordak *may* work with Postgres 8, but this is not tested for.

It may also be possible to run Hordak on a
non-Postgres RDBMS if one skips the ``*_check_*`` migrations, as these are Postgres-specific.
However, this is not recommended as it could lead to database inconsistency.

Usage
-----

TBA

django-hordak is packaged using seed_.

.. _seed: https://github.com/adamcharnock/seed/

.. _swiftwind: https://github.com/adamcharnock/swiftwind/
