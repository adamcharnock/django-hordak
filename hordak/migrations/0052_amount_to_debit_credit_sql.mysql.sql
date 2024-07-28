CREATE OR REPLACE PROCEDURE check_leg(IN _leg_id INT, IN _transaction_id INT)
BEGIN
    DECLARE v_debit DECIMAL(10,2);
    DECLARE v_credit DECIMAL(10,2);
    DECLARE v_currency VARCHAR(10);
    DECLARE v_total DECIMAL(10,2);
    DECLARE has_non_zero INT DEFAULT 0;

    -- Fetch the leg details
    SELECT debit, credit INTO v_debit, v_credit FROM hordak_leg WHERE id = _leg_id;

    -- Check conditions
    -- Note: Error 45000 / 1048 becomes an integrity error in the mysqlDB library, and therefore in Django.
    --       That is the apropriate error for this case.
    IF v_debit IS NULL AND v_credit IS NULL THEN
        SIGNAL SQLSTATE '23000' SET MYSQL_ERRNO = 1048, MESSAGE_TEXT = 'Either the debit or credit field must be specified.';
    END IF;

    IF v_debit IS NOT NULL AND v_credit IS NOT NULL THEN
        SIGNAL SQLSTATE '23000' SET MYSQL_ERRNO = 1048, MESSAGE_TEXT = 'Only the debit or credit field must be specified, not both.';
    END IF;

    IF v_debit IS NOT NULL AND v_debit <= 0 THEN
        SIGNAL SQLSTATE '23000' SET MYSQL_ERRNO = 1048, MESSAGE_TEXT = 'The `debit` field must be greater than zero.';
    END IF;

    IF v_credit IS NOT NULL AND v_credit <= 0 THEN
        SIGNAL SQLSTATE '23000' SET MYSQL_ERRNO = 1048, MESSAGE_TEXT = 'The `credit` field must be greater than zero.';
    END IF;

    -- Check all the transaction's leg's sum to zero
    SELECT currency, ABS(SUM(COALESCE(debit, 0) - COALESCE(credit, 0))) INTO v_currency, v_total
    FROM hordak_leg
    WHERE transaction_id = _transaction_id
    GROUP BY currency
    HAVING ABS(SUM(COALESCE(debit, 0) - COALESCE(credit, 0))) != 0
    LIMIT 1;

    IF FOUND_ROWS() > 0 THEN
        set @message_text = CONCAT('Sum of transaction amounts in each currency must be 0. Sum was: ', v_total, ' in ', v_currency);
        SIGNAL SQLSTATE '23000' SET MYSQL_ERRNO = 1048, MESSAGE_TEXT = @message_text;
    END IF;

END;

-- - reverse:
    CREATE OR REPLACE PROCEDURE check_leg(_transaction_id INT)
    BEGIN
    DECLARE transaction_sum DECIMAL(13, 2);
    DECLARE transaction_currency VARCHAR(3);

    SELECT ABS(SUM(amount)) AS total, amount_currency AS currency
        INTO transaction_sum, transaction_currency
        FROM hordak_leg
        WHERE transaction_id = _transaction_id
        GROUP BY amount_currency
        HAVING ABS(SUM(amount)) > 0
        LIMIT 1;

    IF FOUND_ROWS() > 0 THEN
        SET @msg= CONCAT('Sum of transaction amounts must be 0, got ', transaction_sum);
        SIGNAL SQLSTATE '23000' SET
        MYSQL_ERRNO = 1048,
        MESSAGE_TEXT = @msg;
    END IF;

    END;

-- ----

create or replace view hordak_leg_view as (SELECT
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
    COALESCE(L.debit * -1, L.credit) as legacy_amount,
    (CASE WHEN L.debit IS NULL THEN 'CR' ELSE 'DR' END) AS type,
    (
        CASE WHEN A.lft = A.rght - 1
        THEN SUM(COALESCE(credit, 0) - COALESCE(debit, 0)) OVER (PARTITION BY account_id, currency ORDER BY T.date, L.id)
        END
    ) AS account_balance,
    T.description as transaction_description,
    L.description as leg_description
FROM hordak_leg L
INNER JOIN hordak_transaction T on L.transaction_id = T.id
INNER JOIN hordak_account A on A.id = L.account_id
order by T.date desc, id desc);
-- - reverse:
    CREATE OR REPLACE VIEW hordak_leg_view as (SELECT
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


-- ----

CREATE OR REPLACE VIEW hordak_transaction_view AS
SELECT
    T.*,
    (
        SELECT JSON_ARRAYAGG(account_id)
        FROM hordak_leg
        WHERE transaction_id = T.id AND credit IS NOT NULL
    ) AS credit_account_ids,
    (
        SELECT JSON_ARRAYAGG(account_id)
        FROM hordak_leg
        WHERE transaction_id = T.id AND debit IS NOT NULL
    ) AS debit_account_ids,
    (
        SELECT JSON_ARRAYAGG(name)
        FROM hordak_leg JOIN hordak_account A ON A.id = hordak_leg.account_id
        WHERE transaction_id = T.id AND credit IS NOT NULL
    ) AS credit_account_names,
    (
        SELECT JSON_ARRAYAGG(name)
        FROM hordak_leg JOIN hordak_account A ON A.id = hordak_leg.account_id
        WHERE transaction_id = T.id AND debit IS NOT NULL
    ) AS debit_account_names,
    (
        SELECT
            -- TODO: MYSQL LIMITATION: Cannot handle amount calculation for multi-currency transactions
            CASE WHEN COUNT(DISTINCT currency) < 2 THEN CONCAT('[', JSON_OBJECT('amount', SUM(credit), 'currency', currency), ']') END
        FROM hordak_leg
        WHERE transaction_id = T.id AND credit IS NOT NULL
    ) AS amount
FROM
    hordak_transaction T
GROUP BY T.id, T.uuid, T.timestamp, T.date, T.description
ORDER BY T.id DESC;

-- - reverse:

    CREATE OR REPLACE VIEW hordak_transaction_view AS
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

-- ----

CREATE OR REPLACE TRIGGER check_leg_and_account_currency_match_on_insert
AFTER INSERT ON hordak_leg
FOR EACH ROW
BEGIN
    CALL check_leg_and_account_currency_match(NEW.account_id, NEW.currency);
END;

-- - reverse:

    CREATE OR REPLACE TRIGGER check_leg_and_account_currency_match_on_insert
    AFTER INSERT ON hordak_leg
    FOR EACH ROW
    BEGIN
        CALL check_leg_and_account_currency_match(NEW.account_id, NEW.amount_currency);
    END;

-- ----

CREATE OR REPLACE TRIGGER check_leg_and_account_currency_match_on_update
AFTER UPDATE ON hordak_leg
FOR EACH ROW
BEGIN
    CALL check_leg_and_account_currency_match(NEW.account_id, NEW.currency);
END;

-- - reverse:

    CREATE OR REPLACE TRIGGER check_leg_and_account_currency_match_on_update
    AFTER UPDATE ON hordak_leg
    FOR EACH ROW
    BEGIN
        CALL check_leg_and_account_currency_match(NEW.account_id, NEW.amount_currency);
    END;

-- ----

CREATE OR REPLACE FUNCTION get_balance(account_id BIGINT, as_of DATE, as_of_leg_id BIGINT)
RETURNS JSON
BEGIN
    DECLARE account_lft INT;
    DECLARE account_rght INT;
    DECLARE account_tree_id INT;
    DECLARE result_json JSON;
    DECLARE account_type TEXT;
    DECLARE account_sign INT;

    IF as_of IS NULL AND as_of_leg_id IS NOT NULL THEN
        SET @msg= 'get_balance_table(): You must specify the as_of parameter if also specifying the as_of_leg_id parameter';
        SIGNAL SQLSTATE '23000' SET
        MYSQL_ERRNO = 1048,
        MESSAGE_TEXT = @msg;
    end if;

    -- Fetch the account's hierarchical information
    SELECT lft, rght, tree_id, type INTO account_lft, account_rght, account_tree_id, account_type
    FROM hordak_account
    WHERE id = account_id;

    IF account_type = 'EX' OR account_type = 'AS' THEN
        SET account_sign = -1;
    ELSE
        SET account_sign = 1;
    END IF;

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
                SELECT SUM(COALESCE(L.credit, 0) - COALESCE(L.debit, 0)) * account_sign AS amount, L.currency AS currency
                FROM hordak_account A2
                JOIN hordak_leg L ON L.account_id = A2.id
                JOIN hordak_transaction T ON L.transaction_id = T.id
                WHERE
                    A2.lft >= account_lft
                    AND A2.rght <= account_rght
                    AND A2.tree_id = account_tree_id
                    AND (
                        T.date < as_of
                            OR
                        T.date = as_of AND (CASE WHEN as_of_leg_id IS NOT NULL THEN L.id <= as_of_leg_id ELSE TRUE END)
                    )
                GROUP BY L.currency
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
                SELECT SUM(COALESCE(L.credit, 0) - COALESCE(L.debit, 0)) * account_sign AS amount, L.currency AS currency
                FROM hordak_account A2
                JOIN hordak_leg L ON L.account_id = A2.id
                WHERE A2.lft >= account_lft AND A2.rght <= account_rght AND A2.tree_id = account_tree_id
                GROUP BY L.currency
            ) AS sub
        );
    END IF;

    -- Return the JSON result
    RETURN result_json;
END;

-- - reverse:

    CREATE OR REPLACE FUNCTION get_balance(account_id BIGINT, as_of DATE)
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
