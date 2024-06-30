------
CREATE FUNCTION get_balance_table(account_id BIGINT, as_of DATE = NULL)
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
--- reverse:
DROP FUNCTION get_balance_table(BIGINT, DATE);


------
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
--- reverse:
DROP FUNCTION get_balance(BIGINT, DATE);
