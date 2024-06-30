------
-- TODO: Test
create view hordak_transaction_view AS (SELECT
    T.*
    ,JSON_AGG(L_CR.account_id) as credit_account_ids
    ,JSON_AGG(L_DR.account_id) as debit_account_ids
    ,JSON_AGG(L_DR.name) as debit_account_names
    ,JSON_AGG(L_CR.name) as debit_account_names
    ,jsonb_agg(jsonb_build_object('amount', L.amount, 'currency', L.currency)) as balance
FROM
    hordak_transaction T
INNER JOIN LATERAL (
    SELECT SUM(amount) AS amount, amount_currency AS currency
    FROM hordak_leg L
    WHERE L.transaction_id = T.id AND L.amount > 0
    GROUP BY amount_currency
    ) L ON True
INNER JOIN LATERAL (
    SELECT
        account_id,
        name
    FROM hordak_leg
    INNER JOIN hordak_account A on A.id = hordak_leg.account_id
    WHERE transaction_id = T.id AND amount > 0
    GROUP BY account_id, name
    ORDER BY account_id
    ) L_CR ON True
INNER JOIN LATERAL (
    SELECT
        account_id,
        name
    FROM hordak_leg
    INNER JOIN hordak_account A on A.id = hordak_leg.account_id
    WHERE transaction_id = T.id AND amount < 0
    GROUP BY account_id, name
    ORDER BY account_id
    ) L_DR ON True
GROUP BY T.id, T.uuid, T.timestamp, T.date, T.description
ORDER BY T.id DESC);
--- reverse:
drop view hordak_transaction_view;
