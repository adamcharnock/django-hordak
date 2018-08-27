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

 * Django >= 1.10, <= 2.0
 * Python >= 3.4
 * Postgres >= 9.5

Postgres is required, MySQL is unsupported. This is due to the database constraints we apply to
ensure data integrity. MySQL could be certainly supported in future, volunteers welcome.

.. toctree::
    :maxdepth: 2
    :caption: Contents:

    installation
    settings
    customising-templates
    accounting-for-developers
    api/index
    notes
    changelog

Current limitations
-------------------

Django Hordak currently does not guarantee sequential primary keys of database entities.
IDs are created using regular Postgres sequences, and as a result IDs may skip numbers in
certain circumstances. This may conflict with regulatory and audit requirements for
some projects. This is an area for future work
(`1 <https://stackoverflow.com/a/19006312/764723>`_,
`2 <https://www.postgresql.org/message-id/44E376F6.7010802@seaworthysys.com>`_,
`3 <https://wiki.postgresql.org/wiki/FAQ#Why_are_there_gaps_in_the_numbering_of_my_sequence.2FSERIAL_column.3F_Why_aren.27t_my_sequence_numbers_reused_on_transaction_abort.3F>`_,
`4 <https://stackoverflow.com/questions/9984196/postgresql-gapless-sequences/9985219#9985219>`_).

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _swiftwind: https://github.com/adamcharnock/swiftwind
.. _battlecat: https://github.com/adamcharnock/battlecat
.. _tested against: https://travis-ci.org/adamcharnock/django-hordak
