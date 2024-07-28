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
--- reverse:
-- can be implicitly dropped by migration 0050
drop view if exists hordak_transaction_view;
