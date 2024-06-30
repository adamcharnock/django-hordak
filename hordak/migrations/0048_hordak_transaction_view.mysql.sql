-- ----
CREATE VIEW hordak_transaction_view AS
SELECT
    T.*,
    (
        SELECT JSON_ARRAYAGG(account_id)
        FROM hordak_leg
        WHERE transaction_id = T.id AND amount > 0
    ) AS credit_account_ids,
    (
        SELECT JSON_ARRAYAGG(account_id)
        FROM hordak_leg
        WHERE transaction_id = T.id AND amount < 0
    ) AS debit_account_ids,
    (
        SELECT JSON_ARRAYAGG(name)
        FROM hordak_leg JOIN hordak_account A ON A.id = hordak_leg.account_id
        WHERE transaction_id = T.id AND amount > 0
    ) AS credit_account_names,
    (
        SELECT JSON_ARRAYAGG(name)
        FROM hordak_leg JOIN hordak_account A ON A.id = hordak_leg.account_id
        WHERE transaction_id = T.id AND amount < 0
    ) AS debit_account_names,
    (
        SELECT
            -- TODO: MYSQL LIMITATION: Cannot handle amount calculation for multi-currency transactions
            CASE WHEN COUNT(DISTINCT amount_currency) < 2 THEN CONCAT('[', JSON_OBJECT('amount', SUM(amount), 'currency', amount_currency), ']') END
        FROM hordak_leg
        WHERE transaction_id = T.id AND amount > 0
    ) AS amount
FROM
    hordak_transaction T
GROUP BY T.id, T.uuid, T.timestamp, T.date, T.description
ORDER BY T.id DESC;
-- - reverse:
drop view hordak_transaction_view;
