Hordak Database Triggers
========================

Hordak uses triggers at the database level instead of Django signals. This ensures that if data does not pass
through the Django ORM that integrity is still maintained via Hordak's accounting business rules.

.. note::

    These triggers are automatically added to the database engine through custom Django migration files. When
    the migrate command is run these triggers will be created.

6 Triggers and constraints are added to interact with Hordak models:

- check_leg_
- zero_amount_check_
- check_leg_and_account_currency_match_
- bank_accounts_are_asset_accounts_
- update_full_account_codes_
- check_account_type_

.. _check_leg:

The :code:`check_leg` trigger
-----------------------------

A trigger is added that executes a SQL procedure when each row in the :class:`hordak.models.Leg` database table is
**inserted**, **updated**, or **deleted**.

This constraint is set with execution timing of :code:`DEFERRABLE INITIALLY DEFERRED`, which means it is executed when a
transaction is finished.

.. note::

    If a constraint is deferrable, this clause specifies the default time to check the constraint. If the constraint
    is :code:`INITIALLY IMMEDIATE`, it is checked after each statement. If the constraint is
    :code:`INITIALLY DEFERRED`, it is checked only at the end of the transaction. [#]_

**This trigger ensures that the total amount for the legs of a transaction is equal to 0. Or else it raises a database
level exception.**

Procedure Code
^^^^^^^^^^^^^^

.. highlight:: sql

::

    DECLARE
        tx_id INT;
        non_zero RECORD;
    BEGIN
        IF (TG_OP = 'DELETE') THEN
            tx_id := OLD.transaction_id;
        ELSE
            tx_id := NEW.transaction_id;
        END IF;
        SELECT ABS(SUM(amount)) AS total, amount_currency AS currency
            INTO non_zero
            FROM hordak_leg
            WHERE transaction_id = tx_id
            GROUP BY amount_currency
            HAVING ABS(SUM(amount)) > 0
            LIMIT 1;
        IF FOUND THEN
            RAISE EXCEPTION 'Sum of transaction amounts in each currency must be 0. Currency % has non-zero total %',
                non_zero.currency, non_zero.total;
        END IF;
        RETURN NEW;
    END;

.. _zero_amount_check:

The :code:`zero_amount_check` constraint
----------------------------------------

A constraint is added that checks the value of the :code:`amount` field of :class:`hordak.models.Leg`.

**This constraint ensures that amount value for a single leg transaction does not equal 0. Or else it raises a database
level exception.**

Procedure Code
^^^^^^^^^^^^^^

.. highlight:: sql

::

    ALTER TABLE hordak_leg ADD CONSTRAINT zero_amount_check CHECK (amount != 0)

.. _check_leg_and_account_currency_match:

The :code:`check_leg_and_account_currency_match` constraint
-----------------------------------------------------------

A trigger is added that executes a SQL procedure when each row in the :class:`hordak.models.Leg` database table is
**inserted**, **updated**, or **deleted**. This constraint is set with execution timing of
:code:`DEFERRABLE INITIALLY DEFERRED`

**This procedure ensures that destination account for a leg transaction has the same currency as the origin account.**

Procedure Code
^^^^^^^^^^^^^^

.. highlight:: sql

::

    DECLARE
    BEGIN
        IF (TG_OP = 'DELETE') THEN
            RETURN OLD;
        END IF;
        PERFORM * FROM hordak_account WHERE id = NEW.account_id AND NEW.amount_currency = ANY(currencies);
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Destination account does not support currency %', NEW.amount_currency;
        END IF;
        RETURN NEW;
    END;

.. _bank_accounts_are_asset_accounts:

The :code:`bank_accounts_are_asset_accounts` constraint
-------------------------------------------------------

A constraint is added that interacts with the :class:`hordak.models.Account` database table.

**This constraint ensures that Account objects that have the is_bank_account flag set must be an asset account type.**

Procedure Code
^^^^^^^^^^^^^^

.. highlight:: sql

::

    ADD CONSTRAINT bank_accounts_are_asset_accounts
    CHECK (is_bank_account = FALSE OR _type = 'AS')

.. _update_full_account_codes:

The :code:`update_full_account_codes` trigger
---------------------------------------------

A trigger is added that executes a SQL procedure when each row in the :class:`hordak.models.Account` database table is
**inserted**, **updated**, or **deleted** and where it is also a root Account. This trigger is set with default execution timing of
:code:`DEFERRABLE INITIALLY IMMEDIATE`

**This procedure performs multiple activities:**

- It sets any empty string :class:`hordak.models.Account` :code:`account.code` to :code:`NULL` database value.
- It sets the :code:`account.full_code` of children accounts to a combination of its parents :code:`account.code`.
- If a parent :code:`account.code` is :code:`NULL` it sets the children's subsequent :code:`account.full_code` to :code:`NULL` also.

Procedure Code
^^^^^^^^^^^^^^

.. highlight:: sql

::

    BEGIN
        -- Set empty string codes to be NULL
        UPDATE hordak_account SET code = NULL where code = '';

        -- Set full code to the combination of the parent account's codes
        UPDATE
            hordak_account AS a
        SET
            full_code = (
                SELECT string_agg(code, '' order by lft)
                FROM hordak_account AS a2
                WHERE a2.lft <= a.lft AND a2.rght >= a.rght AND a.tree_id = a2.tree_id
            );

        -- Set full codes to NULL where a parent account includes a NULL code
        UPDATE
            hordak_account AS a
        SET
            full_code = NULL
        WHERE
            (
                SELECT COUNT(*)
                FROM hordak_account AS a2
                WHERE a2.lft <= a.lft AND a2.rght >= a.rght AND a.tree_id = a2.tree_id AND a2.code IS NULL
            ) > 0;
        RETURN NULL;
    END;

.. _check_account_type:

The :code:`check_account_type` trigger
---------------------------------------------

A trigger is added that executes a SQL procedure when each row in the :class:`hordak.models.Account` database table is
**inserted** or **updated** and where it is also a root Account. This trigger is set with default execution timing of
:code:`DEFERRABLE INITIALLY IMMEDIATE`

**This procedure sets children accounts to the same type as the parent account.**

Procedure Code
^^^^^^^^^^^^^^

.. highlight:: sql

::

    BEGIN
        IF NEW.parent_id::BOOL THEN
            NEW.type = (SELECT type FROM hordak_account WHERE id = NEW.parent_id);
        END IF;
        RETURN NEW;
    END;

.. [#] Deferrable trigger parameters from `CREATE TRIGGER`_.
.. _`CREATE TRIGGER`: https://www.enterprisedb.com/docs/en/10/pg/sql-createtrigger.html