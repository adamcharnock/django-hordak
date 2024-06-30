-- ----
CREATE FUNCTION get_balance(account_id BIGINT, as_of DATE)
RETURNS JSON
BEGIN
    DECLARE account_lft INT;
    DECLARE account_rght INT;
    DECLARE account_tree_id INT;
    DECLARE result_json JSON;

    -- Fetch the account's hierarchical information
    SELECT lft, rght, tree_id INTO account_lft, account_rght, account_tree_id
    FROM hordak_account
    WHERE id = account_id;

    -- Prepare the result set with sums calculated in a derived table (subquery)
    IF as_of IS NOT NULL THEN
        SET result_json = (
            SELECT JSON_ARRAYAGG(
                JSON_OBJECT(
                    'amount', sub.amount,
                    'currency', sub.currency
                )
            )
            FROM (
                SELECT COALESCE(SUM(L.amount), 0.0) AS amount, L.amount_currency AS currency
                FROM hordak_account A2
                JOIN hordak_leg L ON L.account_id = A2.id
                JOIN hordak_transaction T ON L.transaction_id = T.id
                WHERE A2.lft >= account_lft AND A2.rght <= account_rght AND A2.tree_id = account_tree_id AND T.date <= as_of
                GROUP BY L.amount_currency
            ) AS sub
        );
    ELSE
        SET result_json = (
            SELECT JSON_ARRAYAGG(
                JSON_OBJECT(
                    'amount', sub.amount,
                    'currency', sub.currency
                )
            )
            FROM (
                SELECT COALESCE(SUM(L.amount), 0.0) AS amount, L.amount_currency AS currency
                FROM hordak_account A2
                JOIN hordak_leg L ON L.account_id = A2.id
                WHERE A2.lft >= account_lft AND A2.rght <= account_rght AND A2.tree_id = account_tree_id
                GROUP BY L.amount_currency
            ) AS sub
        );
    END IF;

    -- Return the JSON result
    RETURN result_json;
END;
-- - reverse:
DROP FUNCTION get_balance;
