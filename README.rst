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

Design
------

The core models consist of:

- ``Account`` - Such as 'Accounts Receivable', a bank account, etc. Accounts can be arranged as a tree structure,
  where the balance of the parent account is the summation of the balances of all its children.
- ``Transaction`` - Represents a movement between accounts. Each transaction must have two or more legs.
- ``Leg`` - Represents a flow of money into (debit) or out of (credit) a transaction. Debits are represented by
  negative amounts, and credits by positive amounts. The sum of all a transaction's legs must equal zero. This is
  enforced with a database constraint.

Additionally, there are models which related to the import of external bank statement data:

- ``StatementImport`` - Represents a simple import of zero or more statement lines relating to a specific ``Account``.
- ``StatementLine`` - Represents a statement line. ``StatementLine.create_transaction()`` may be called to
  create a transaction for the statement line.

Loading Fixtures
----------------

Fixture data can be loaded as normal::

    ./manage.py loaddata top-level-accounts

Creating Fixtures
-----------------

Create fixtures as follows::

    ./manage.py dumpdata hordak --indent=2 --natural-primary --natural-foreign > fixtures/my-fixture.json

Usage
-----

TBA

django-hordak is packaged using seed_.

.. _seed: https://github.com/adamcharnock/seed/

.. _swiftwind: https://github.com/adamcharnock/swiftwind/
