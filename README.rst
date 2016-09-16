django-hordak
=============

**Double entry bookkeeping in Django.**

Django Hordak provides a `simple model layer`_ for a double-entry bookkeeping
system. The intention is not to provide a full-featured app, but rather
to provide a reliable foundation on which to build such apps.

Data consistency is enforced in the model layer and by Postgres triggers.
(It may be possible to use MySQL, MSSQL, Maria et al if one skips the
installation of these triggers).

Ultimately the intention is to integrate this with swiftwind_ to provide
an accounting & billing system for a communal household. This interface
should be intuitive and suitable for non-experts.

.. image:: https://img.shields.io/pypi/v/django-hordak.svg
    :target: https://badge.fury.io/py/django-hordak

.. image:: https://img.shields.io/github/license/waldocollective/django-hordak.svg
    :target: https://pypi.python.org/pypi/django-hordak/

.. image:: https://travis-ci.org/waldocollective/django-hordak.svg?branch=master
    :target: https://travis-ci.org/waldocollective/django-hordak/

.. image:: https://coveralls.io/repos/github/waldocollective/django-hordak/badge.svg?branch=master
    :target: https://coveralls.io/github/waldocollective/django-hordak?branch=master

Installation
------------

Installation using pip::

    pip install django-hordak

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

Explanation: Double Entry for Software Developers
-------------------------------------------------

This explanation may be substantially easier to comprehend for those with a STEM background.

The core of double entry accounting works as follows:

- Each account has a 'type' (asset, liability, income, expense, equity)
- **Debits decrease** the value of an account
- **Credits increase** the value of an account
- The sign of any *asset* or *expense* account balance is **always flipped** upon calculation (i.e. multiply by -1)
- A transaction is comprised of 1 or more credits **and** 1 or more debits
- The value of a transaction's debits and credits must be equal (money into transaction = money out of transaction).

Examples
~~~~~~~~

You live in a shared house. Everyone pays their share into a communal bank account
every month.

Example 1: Saving money to pay a bill (no flipping)
'''''''''''''''''''''''''''''''''''''''''''''''''''

You pay the electricity bill every three months. Therefore every month you take £100
from everyone's contributions and put it into Electricity Payable account (a liability
account) in the knowledge that you will pay the bill from this account when it arrives:

These accounts are income & liability accounts, so neither balance needs to be flipped. Therefore:

* Balances before:

  * *Rent Income*: £500
  * *Electricity Payable* (liability): £0

* **Transaction**:

  * £100 from *Rent Income* to *Electricity Payable*

* Balances after:

  * *Rent Income*: £400
  * *Electricity Payable* (liability): £100

This should also make intuitive sense. Some of the rent income will be used to pay the electricity
bill, therefore the former decreases and the latter increases.

Example 2: Saving money to pay a bill (flipping)
''''''''''''''''''''''''''''''''''''''''''''''''

At the start of every month each housemate pays into the communal bank account. We
should therefore represent this somehow in our double entry system.

We have an account called *Bank*, which is an asset account (because this is money
we actually have). We also have a *Rent Income* account which, as the name implies, is an
income account.

Therefore, **to represent the fact that we have been paid money, we must create a transaction**.
However, money cannot be injected from outside our double entry system, so how do we deal with this?

Let's show how we represent a single housemate's payment:

* Balances before:

  * *Bank* (asset): £0
  * *Rent Income*: £0

* **Transaction:**

  * £500 from *Bank* to *Rent Income*

* Balances after:

  * *Bank* (asset): -£500 * -1 = **£500**
  * *Rent Income*: £500

Because the bank account is an asset account, we flip the sign of its balance.
**The result is that both accounts increase in value.**


django-hordak is packaged using seed_.

.. _seed: https://github.com/adamcharnock/seed/

.. _swiftwind: https://github.com/waldocollective/swiftwind/

.. _simple model layer: https://github.com/waldocollective/django-hordak/blob/master/hordak/models.py
