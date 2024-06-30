------
create view hordak_transaction_view AS (SELECT
    T.*
    ,JSON_AGG(L_CR.credit_account_id) as credit_account_ids
    ,JSON_AGG(L_DR.debit_account_id) as debit_account_ids
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
        account_id AS credit_account_id
    FROM hordak_leg
    WHERE transaction_id = T.id AND amount > 0
    GROUP BY account_id
    ) L_CR ON True
INNER JOIN LATERAL (
    SELECT
        account_id AS debit_account_id
    FROM hordak_leg
    WHERE transaction_id = T.id AND amount < 0
    GROUP BY account_id
    ) L_DR ON True
GROUP BY T.id, T.uuid, T.timestamp, T.date, T.description
ORDER BY T.id DESC);
--- reverse:
drop view hordak_transaction_view;
