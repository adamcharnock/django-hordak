-- ----
CREATE VIEW hordak_transaction_view AS
SELECT
    T.*,
    (
        SELECT CONCAT('[', GROUP_CONCAT(JSON_OBJECT('amount', SUM(L.amount), 'currency', L.amount_currency) SEPARATOR ','), ']')
        FROM hordak_leg L
        WHERE L.transaction_id = T.id AND L.amount > 0
        GROUP BY L.amount_currency
    ) AS balance
FROM
    hordak_transaction T
GROUP BY T.id, T.uuid, T.timestamp, T.date, T.description;
-- - reverse:
drop view hordak_transaction_view;
