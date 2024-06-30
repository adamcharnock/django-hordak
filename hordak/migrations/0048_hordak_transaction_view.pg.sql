------
create view hordak_transaction_view AS (SELECT
    T.*
    ,JSON_AGG(LA.credit_account_id) as credit_account_ids
    ,JSON_AGG(LA.debit_account_id) as debit_account_ids
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
        (CASE WHEN L.amount > 0 THEN account_id END) AS credit_account_id,
        (CASE WHEN NOT (L.amount > 0) THEN account_id END) AS debit_account_id
    FROM hordak_leg L
    WHERE L.transaction_id = T.id
    GROUP BY account_id, L.amount > 0
    ) LA ON True
GROUP BY T.id, T.uuid, T.timestamp, T.date, T.description
ORDER BY T.id DESC);
--- reverse:
drop view hordak_transaction_view;
