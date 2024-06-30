------
create view hordak_transaction_view AS (SELECT
    T.*
    ,jsonb_agg(jsonb_build_object('amount', L.amount, 'currency', L.currency)) as balance
FROM
    hordak_transaction T
INNER JOIN LATERAL (
    SELECT SUM(amount) AS amount, amount_currency AS currency
    FROM hordak_leg L
    WHERE L.transaction_id = T.id AND L.amount > 0
    GROUP BY amount_currency
    ) L ON True
GROUP BY T.id, T.uuid, T.timestamp, T.date, T.description
ORDER BY T.id DESC);
--- reverse:
drop view hordak_transaction_view;
