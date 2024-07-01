-- TODO: Trigger to ensure that only credit or debit is set
-- TODO: Trigger to ensure that credit/debit is > 0

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
        HAVING (SUM(debit) - SUM(credit)) != 0
        LIMIT 1;

    IF FOUND THEN
        -- TODO: Include transaction id in exception message below (see #93)
        RAISE EXCEPTION 'Sum of transaction amounts in each currency must be 0. Currency %% has non-zero total %%',
            non_zero.currency, non_zero.total;
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
            RAISE EXCEPTION 'Sum of transaction amounts in each currency must be 0. Currency %% has non-zero total %%',
                non_zero.currency, non_zero.total;
        END IF;

        RETURN NEW;
    END;
    $$
    LANGUAGE plpgsql;
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
    (CASE WHEN L.debit IS NULL THEN 'CR' ELSE 'DR' END) AS type,
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
-- - reverse:
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
create view hordak_transaction_view AS (SELECT
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
    create view hordak_transaction_view AS (SELECT
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
        SELECT SUM(amount) AS amount, amount_currency AS currency
        FROM hordak_leg L
        WHERE L.transaction_id = T.id AND L.amount > 0
        GROUP BY amount_currency
        ) L ON True
    GROUP BY T.id, T.uuid, T.timestamp, T.date, T.description
    ORDER BY T.id DESC);
