Hordak Database Triggers
========================

Hordak uses triggers at the database level instead of Django signals. This ensures that if data does not pass
through the Django ORM that integrity is still maintained via Hordak's accounting business rules.

.. note::

    These triggers are automatically added to the database engine through custom Django migration files. When
    the migrate command is run these triggers will be created.

6 Triggers and constraints are added to interact with Hordak models:

- check_leg_
- _`zero_amount_check`
- another

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


.. [#] Deferrable trigger parameters from `CREATE TRIGGER`_.
.. _`CREATE TRIGGER`: https://www.enterprisedb.com/docs/en/10/pg/sql-createtrigger.html