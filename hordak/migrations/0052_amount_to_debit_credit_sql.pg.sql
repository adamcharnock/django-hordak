CREATE OR REPLACE FUNCTION check_leg()
    RETURNS TRIGGER AS
$$
DECLARE
    tx_id INT;
    non_zero RECORD;
BEGIN
    IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
        -- TODO: Test
        IF NEW.debit IS NULL AND NEW.credit IS NULL THEN
            RAISE EXCEPTION 'Either the debit or credit field must be specified. Record ID: %', NEW.id USING ERRCODE = 23514;
        END IF;

        -- TODO: Test
        IF NEW.debit IS NOT NULL AND NEW.credit IS NOT NULL THEN
            RAISE EXCEPTION 'Only the debit or credit field must be specified, not both. Record ID: %', NEW.id USING ERRCODE = 23514;
        END IF;

        -- TODO: Test
        IF NEW.debit IS NOT NULL AND NOT (NEW.debit > 0) THEN
            RAISE EXCEPTION 'The `debit` field must be greater than zero. Was: %. Record ID %', NEW.debit, NEW.id USING ERRCODE = 23514;
        END IF;

        -- TODO: Test
        IF NEW.credit IS NOT NULL AND NOT (NEW.credit > 0) THEN
            RAISE EXCEPTION 'The `credit` field must be greater than zero. Was: %. Record ID %', NEW.credit, NEW.id USING ERRCODE = 23514;
        END IF;
    END IF;

    -- Get the transaction for this leg
    IF (TG_OP = 'DELETE') THEN
        tx_id := OLD.transaction_id;
    ELSE
        tx_id := NEW.transaction_id;
    END IF;

    -- Check all the transaction's leg's sum to zero
    SELECT ABS(SUM(COALESCE(debit, 0) - COALESCE(credit, 0))) AS total, currency
        INTO non_zero
        FROM hordak_leg
        WHERE transaction_id = tx_id
        GROUP BY currency
        HAVING ABS(SUM(COALESCE(debit, 0) - COALESCE(credit, 0))) != 0
        LIMIT 1;

    IF FOUND THEN
        -- TODO: Include transaction id in exception message below (see #93)
        RAISE EXCEPTION 'Sum of transaction amounts in each currency must be 0. Currency % has non-zero total %', non_zero.currency, non_zero.total USING ERRCODE = 23514;
    END IF;

    RETURN NEW;
END;
$$
LANGUAGE plpgsql;
--- reverse:
    CREATE OR REPLACE FUNCTION check_leg()
        RETURNS trigger AS
    $$
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
            -- TODO: Include transaction id in exception message below (see #93)
            RAISE EXCEPTION 'Sum of transaction amounts in each currency must be 0. Currency % has non-zero total %',
                non_zero.currency, non_zero.total USING ERRCODE = 23514;
        END IF;

        RETURN NEW;
    END;
    $$
    LANGUAGE plpgsql;
------
drop view hordak_leg_view;
--- reverse:
    create view hordak_leg_view as (SELECT
        L.id,
        L.uuid,
        transaction_id,
        account_id,
        A.full_code as account_full_code,
        A.name as account_name,
        A.type as account_type,
        T.date as date,
        ABS(amount) as amount,
        amount_currency,
        (CASE WHEN amount > 0 THEN 'CR' ELSE 'DR' END) AS type,
        (CASE WHEN amount > 0 THEN ABS(amount) END) AS credit,
        (CASE WHEN amount < 0 THEN ABS(amount) END) AS debit,
        (
            CASE WHEN A.lft = A.rght - 1
            THEN SUM(amount) OVER (PARTITION BY account_id, amount_currency ORDER BY T.date, L.id)
            END
        ) AS account_balance,
        T.description as transaction_description,
        L.description as leg_description
    FROM hordak_leg L
    INNER JOIN hordak_transaction T on L.transaction_id = T.id
    INNER JOIN hordak_account A on A.id = L.account_id
    order by T.date desc, id desc);

------

create view hordak_leg_view as (SELECT
    L.id,
    L.uuid,
    transaction_id,
    account_id,
    A.full_code as account_full_code,
    A.name as account_name,
    A.type as account_type,
    T.date as date,
    L.credit,
    L.debit,
    COALESCE(L.debit, L.credit) as amount,
    L.currency,
    COALESCE(L.debit * -1, L.credit) as legacy_amount,
    (CASE WHEN L.debit IS NULL THEN 'CR' ELSE 'DR' END) AS type,
    (
        CASE WHEN A.lft = A.rght - 1
        THEN SUM(COALESCE(credit, 0)::DECIMAL - COALESCE(debit, 0)::DECIMAL) OVER (PARTITION BY account_id, currency ORDER BY T.date, L.id)
        END
    ) AS account_balance,
    T.description as transaction_description,
    L.description as leg_description
FROM hordak_leg L
INNER JOIN hordak_transaction T on L.transaction_id = T.id
INNER JOIN hordak_account A on A.id = L.account_id
order by T.date desc, id desc);
--- reverse:
drop view hordak_leg_view;

------

create or replace view hordak_transaction_view AS (SELECT
    T.*,
    -- Get ID and names of credited accounts
    -- Note that this gets unique IDs and names. If there is a
    -- way to implement this without DISTINCT then I would like that
    -- as then we can be guaranteed to get back the same number
    -- of account names and account IDs.
    (
        SELECT JSONB_AGG(L_CR.account_id)
        FROM hordak_leg L_CR
        INNER JOIN hordak_account A ON A.id = L_CR.account_id
        WHERE L_CR.transaction_id = T.id AND L_CR.credit IS NOT NULL
    ) AS credit_account_ids,
    (
        SELECT JSONB_AGG(L_DR.account_id)
        FROM hordak_leg L_DR
        INNER JOIN hordak_account A ON A.id = L_DR.account_id
        WHERE L_DR.transaction_id = T.id AND L_DR.debit IS NOT NULL
    ) AS debit_account_ids,
    (
        SELECT JSONB_AGG(A.name)
        FROM hordak_leg L_CR
        INNER JOIN hordak_account A ON A.id = L_CR.account_id
        WHERE L_CR.transaction_id = T.id AND L_CR.credit IS NOT NULL
    ) AS credit_account_names,
    (
        SELECT JSONB_AGG(A.name)
        FROM hordak_leg L_DR
        INNER JOIN hordak_account A ON A.id = L_DR.account_id
        WHERE L_DR.transaction_id = T.id AND L_DR.debit IS NOT NULL
    ) AS debit_account_names,
    JSONB_AGG(jsonb_build_object('amount', L.credit, 'currency', L.currency)) as amount
FROM
    hordak_transaction T
-- Get LEG amounts for each currency in the transaction
INNER JOIN LATERAL (
    SELECT SUM(credit) AS credit, currency
    FROM hordak_leg L
    WHERE L.transaction_id = T.id AND L.credit IS NOT NULL
    GROUP BY currency
    ) L ON True
GROUP BY T.id, T.uuid, T.timestamp, T.date, T.description
ORDER BY T.id DESC);
--- reverse:
    create or replace view hordak_transaction_view AS (SELECT
        T.*,
        -- Get ID and names of credited accounts
        -- Note that this gets unique IDs and names. If there is a
        -- way to implement this without DISTINCT then I would like that
        -- as then we can be guaranteed to get back the same number
        -- of account names and account IDs.
        (
            SELECT JSONB_AGG(L_CR.account_id)
            FROM hordak_leg L_CR
            INNER JOIN hordak_account A ON A.id = L_CR.account_id
            WHERE L_CR.transaction_id = T.id AND L_CR.amount > 0
        ) AS credit_account_ids,
        (
            SELECT JSONB_AGG(L_DR.account_id)
            FROM hordak_leg L_DR
            INNER JOIN hordak_account A ON A.id = L_DR.account_id
            WHERE L_DR.transaction_id = T.id AND L_DR.amount < 0
        ) AS debit_account_ids,
        (
            SELECT JSONB_AGG(A.name)
            FROM hordak_leg L_CR
            INNER JOIN hordak_account A ON A.id = L_CR.account_id
            WHERE L_CR.transaction_id = T.id AND L_CR.amount > 0
        ) AS credit_account_names,
        (
            SELECT JSONB_AGG(A.name)
            FROM hordak_leg L_DR
            INNER JOIN hordak_account A ON A.id = L_DR.account_id
            WHERE L_DR.transaction_id = T.id AND L_DR.amount < 0
        ) AS debit_account_names,
        JSONB_AGG(jsonb_build_object('amount', L.amount, 'currency', L.currency)) as amount
    FROM
        hordak_transaction T
    -- Get LEG amounts for each currency in the transaction
    INNER JOIN LATERAL (
        SELECT SUM(amount) AS amount, currency
        FROM hordak_leg L
        WHERE L.transaction_id = T.id AND L.amount > 0
        GROUP BY currency
        ) L ON True
    GROUP BY T.id, T.uuid, T.timestamp, T.date, T.description
    ORDER BY T.id DESC);

------

CREATE OR REPLACE FUNCTION check_leg_and_account_currency_match()
    RETURNS trigger AS
$$
DECLARE
    account RECORD;
BEGIN

    IF (TG_OP = 'DELETE') THEN
        RETURN OLD;
    END IF;

    PERFORM * FROM hordak_account WHERE id = NEW.account_id AND currencies::jsonb @> to_jsonb(ARRAY[NEW.currency]::text[]);

    IF NOT FOUND THEN
        SELECT * INTO account FROM hordak_account WHERE id = NEW.account_id;

        RAISE EXCEPTION 'Destination Account#% does not support currency %. Account currencies: %', account.id, NEW.currency, account.currencies USING ERRCODE = 23514;
    END IF;

    RETURN NEW;
END;
$$
LANGUAGE plpgsql;

--- reverse:

    CREATE OR REPLACE FUNCTION check_leg_and_account_currency_match()
        RETURNS trigger AS
    $$
    DECLARE
        account RECORD;
    BEGIN

        IF (TG_OP = 'DELETE') THEN
            RETURN OLD;
        END IF;

        PERFORM * FROM hordak_account WHERE id = NEW.account_id AND currencies::jsonb @> to_jsonb(ARRAY[NEW.amount_currency]::text[]);

        IF NOT FOUND THEN
            SELECT * INTO account FROM hordak_account WHERE id = NEW.account_id;

            RAISE EXCEPTION 'Destination Account#% does not support currency %. Account currencies: %', account.id, NEW.amount_currency, account.currencies USING ERRCODE = 23514;
        END IF;

        RETURN NEW;
    END;
    $$
    LANGUAGE plpgsql;

------

ALTER TABLE hordak_leg DROP CONSTRAINT zero_amount_check;
--- reverse:
ALTER TABLE hordak_leg ADD CONSTRAINT zero_amount_check CHECK (amount != 0);

------

ALTER TABLE hordak_leg ADD CONSTRAINT zero_amount_check_credit CHECK (credit != 0);
--- reverse:
ALTER TABLE hordak_leg DROP CONSTRAINT zero_amount_check_credit;

------

ALTER TABLE hordak_leg ADD CONSTRAINT zero_amount_check_debit CHECK (debit != 0);
--- reverse:
ALTER TABLE hordak_leg DROP CONSTRAINT zero_amount_check_debit;


------
CREATE OR REPLACE FUNCTION get_balance_table(account_id BIGINT, as_of DATE = NULL, as_of_leg_id BIGINT = NULL)
    RETURNS TABLE (amount DECIMAL, currency VARCHAR) AS
$$
DECLARE
    account_lft int;
    account_rght int;
    account_tree_id int;
    account_type TEXT;
    account_sign INT;
BEGIN
    -- Get the account's information
    SELECT
        lft,
        rght,
        tree_id,
        type
    INTO
        account_lft,
        account_rght,
        account_tree_id,
        account_type
    FROM hordak_account
    WHERE id = account_id;
    -- TODO: OPTIMISATION: Crate get_balance_table_simple() for use when this is a leaf account,
    --       and defer to it when lft + 1 = rght

    IF account_type = 'EX' OR account_type = 'AS' THEN
        account_sign := -1;
    ELSE
        account_sign := 1;
    END IF;

    IF as_of IS NULL AND as_of_leg_id IS NOT NULL THEN
        RAISE EXCEPTION 'get_balance_table(): You must specify the as_of parameter if also specifying the as_of_leg_id parameter';
    end if;

    IF as_of IS NOT NULL THEN
        -- If `as_of` is specified then we need an extra join onto the
        -- transactions table to get the transaction date
        RETURN QUERY
            SELECT
                SUM(COALESCE(L.credit, 0) - COALESCE(L.debit, 0)) * account_sign as amount,
                L.currency as currency
            FROM hordak_account A2
            INNER JOIN hordak_leg L on L.account_id = A2.id
            INNER JOIN hordak_transaction T on L.transaction_id = T.id
            WHERE
                -- We want to include this account and all of its children
                A2.lft >= account_lft AND
                A2.rght <= account_rght AND
                A2.tree_id = account_tree_id AND
                -- Also respect the as_of parameter
                (
                    T.date < as_of
                        OR
                    T.date = as_of AND (CASE WHEN as_of_leg_id IS NOT NULL THEN L.id <= as_of_leg_id ELSE TRUE END)
                )
            GROUP BY L.currency;
    ELSE
        RETURN QUERY
            SELECT
                SUM(COALESCE(L.credit, 0) - COALESCE(L.debit, 0)) * account_sign as amount,
                L.currency as currency
            FROM hordak_account A2
            INNER JOIN hordak_leg L on L.account_id = A2.id
            WHERE
                -- We want to include this account and all of its children
                A2.lft >= account_lft AND
                A2.rght <= account_rght AND
                A2.tree_id = account_tree_id
            GROUP BY L.currency;
    END IF;
END;
$$
LANGUAGE plpgsql;
--- reverse:
    CREATE OR REPLACE FUNCTION get_balance_table(account_id BIGINT, as_of DATE = NULL)
        RETURNS TABLE (amount DECIMAL, currency VARCHAR) AS
    $$
    DECLARE
        account_lft int;
        account_rght int;
        account_tree_id int;
    BEGIN
        -- Get the account's information
        SELECT
            lft,
            rght,
            tree_id
        INTO
            account_lft,
            account_rght,
            account_tree_id
        FROM hordak_account
        WHERE id = account_id;
        -- TODO: OPTIMISATION: Crate get_balance_table_simple() for use when this is a leaf account,
        --       and defer to it when lft + 1 = rght

        IF as_of IS NOT NULL THEN
            -- If `as_of` is specified then we need an extra join onto the
            -- transactions table to get the transaction date
            RETURN QUERY
                SELECT
                    COALESCE(SUM(L.amount), 0.0) as amount,
                    L.amount_currency as currency
                FROM hordak_account A2
                INNER JOIN hordak_leg L on L.account_id = A2.id
                INNER JOIN hordak_transaction T on L.transaction_id = T.id
                WHERE
                    -- We want to include this account and all of its children
                    A2.lft >= account_lft AND
                    A2.rght <= account_rght AND
                    A2.tree_id = account_tree_id AND
                    -- Also respect the as_of parameter
                    T.date <= as_of
                GROUP BY L.amount_currency;
        ELSE
            RETURN QUERY
                SELECT
                    COALESCE(SUM(L.amount), 0.0) as amount,
                    L.amount_currency as currency
                FROM hordak_account A2
                INNER JOIN hordak_leg L on L.account_id = A2.id
                WHERE
                    -- We want to include this account and all of its children
                    A2.lft >= account_lft AND
                    A2.rght <= account_rght AND
                    A2.tree_id = account_tree_id
                GROUP BY L.amount_currency;
        END IF;
    END;
    $$
    LANGUAGE plpgsql;

------
DROP FUNCTION get_balance;
--- reverse:

    CREATE FUNCTION get_balance(account_id BIGINT, as_of DATE = NULL)
        RETURNS JSONB AS
    $$
    BEGIN
        -- Convert our balance table into JSONB in the form:
        --     [{"amount": 100.00, "currency": "EUR"}]
        RETURN
            (SELECT jsonb_agg(jsonb_build_object('amount', amount, 'currency', currency)))
            FROM get_balance_table(account_id, as_of);
    END;
    $$
    LANGUAGE plpgsql;

------

CREATE OR REPLACE FUNCTION get_balance(account_id BIGINT, as_of DATE = NULL, as_of_leg_id BIGINT = NULL)
    RETURNS JSONB AS
$$
BEGIN
    -- Convert our balance table into JSONB in the form:
    --     [{"amount": 100.00, "currency": "EUR"}]
    RETURN
        (SELECT jsonb_agg(jsonb_build_object('amount', amount, 'currency', currency)))
        FROM get_balance_table(account_id, as_of, as_of_leg_id);
END;
$$
LANGUAGE plpgsql;

--- reverse:
    DROP FUNCTION get_balance;
