.. _settings:

Settings
========

You can set the following your project's ``settings.py`` file:

DEFAULT_CURRENCY
----------------

Default: ``"EUR"`` (str)

The default currency to use when creating new accounts

CURRENCIES
----------

Default: ``[]`` (list)

Any currencies (additional to ``DEFAULT_CURRENCY``) for which you wish to create accounts.
For example, you may have ``"EUR"`` for your ``DEFAULT_CURRENCY``, and ``["USD", "GBP"]`` for your
additional ``CURRENCIES``.
To set different value, than for `dj-money`,
you can use `HORDAK_CURRENCIES` setting value will be used preferentially.


HORDAK_DECIMAL_PLACES
---------------------

Default: ``2`` (int)

Number of decimal places available within monetary values.


HORDAK_MAX_DIGITS
-----------------

Default: ``13`` (int)

Maximum number of digits allowed in monetary values.
Decimal places both right and left of decimal point are included in this count.
Therefore a maximum value of 9,999,999.999 would require ``HORDAK_MAX_DIGITS=10``
and ``HORDAK_DECIMAL_PLACES=3``.

HORDAK_UUID_DEFAULT
-------------------

Default: ``uuid.uuid4`` (callable)

A callable to be used to generate UUID values for database entities.


HORDAK_CHECKPOINT_THRESHOLD
---------------------------

Default: ``0`` (int)

Enables running total checkpoints (PostgreSQL only). When set to a positive
number, an account's balance checkpoint is advanced automatically once that
many legs have been created since the last checkpoint, making
``Account.get_simple_balance()`` O(legs since last checkpoint) instead of
O(all legs) on busy accounts.

Left at ``0`` (the default), no checkpoints are built automatically and leg
creation performs no extra queries. Checkpoints can still be built manually
with the ``recalculate_running_totals`` management command, which also
supports ``--check`` (verify checkpoints against full sums, optionally
``--mail-admins``) and ``--keep-history``.

Checkpoints require PostgreSQL: choosing a cutoff that cannot race in-flight
inserts relies on lock visibility (``pg_locks``) that other backends do not
expose. On other databases the checkpoint-building entry points raise
``NotImplementedError``; balance reads are unaffected. Checkpoint building
also skips any round during which another transaction is inserting legs, and
catches up at the next quiet moment -- on a ledger with continuous writes,
checkpoints advance in the gaps.
