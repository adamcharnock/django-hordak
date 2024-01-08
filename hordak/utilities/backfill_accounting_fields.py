def backfill_accounting_fields(apps, schema_editor):
    from hordak.models.core import Leg

    # Fill Amount
    table_name = Leg._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        sql = f"""
            UPDATE {table_name}
            SET accounting_amount = ABS(amount)
        """
        cursor.execute(sql)

    lhs_accs = ["AS", "EX"]

    #################################
    # Assign types to Left Hand Side

    # Fetch Leg entries with positive amount and related Account type as "AS" or "EX"
    lhs_legs_dr = Leg.objects.filter(amount__gt=0, account__type__in=lhs_accs)
    # Update the accounting_type for those Leg entries
    lhs_legs_dr.update(accounting_type="DR")

    lhs_legs_cr = Leg.objects.filter(amount__lt=0, account__type__in=lhs_accs)
    # Update the accounting_type for those Leg entries
    lhs_legs_cr.update(accounting_type="CR")

    # Assign types to Left Hand Side
    #################################

    #################################
    # Assign types to Right Hand Side

    # Fetch Leg entries with positive amount and related Account type NOT as "AS" or "EX"
    rhs_legs_cr = Leg.objects.filter(amount__lt=0).exclude(account__type__in=lhs_accs)
    # Update the accounting_type for these Leg entries to 'CR'
    rhs_legs_cr.update(accounting_type="CR")

    # Fetch Leg entries with positive amount and related Account type NOT as "AS" or "EX"
    rhs_legs_dr = Leg.objects.filter(amount__gt=0).exclude(account__type__in=lhs_accs)
    # Update the accounting_type for these Leg entries to 'CR'
    rhs_legs_dr.update(accounting_type="DR")

    # Assign types to Right Hand Side
    #################################

    # PostgreSQL SQL
    postgres_sql = f"""
    DO $$
    DECLARE
        mismatched_count INTEGER;
    BEGIN
        WITH TransactionSums AS (
            SELECT
                l.transaction_id,
                SUM(CASE WHEN l.accounting_type = 'DR' THEN l.amount ELSE 0 END) AS dr_sum,
                SUM(CASE WHEN l.accounting_type = 'CR' THEN l.amount ELSE 0 END) AS cr_sum
            FROM
                {table_name} l
            GROUP BY
                l.transaction_id
        )

        SELECT
            COUNT(*)
        INTO mismatched_count
        FROM
            TransactionSums
        WHERE
            dr_sum != cr_sum;

        IF mismatched_count > 0 THEN
            RAISE EXCEPTION 'Mismatched DR and CR sums in Transactions';
        END IF;
    END $$;
    """

    # MySQL SQL
    mysql_sql = f"""
    DROP PROCEDURE IF EXISTS CheckTransactionSums;

    DELIMITER //

    CREATE PROCEDURE CheckTransactionSums()
    BEGIN
        DECLARE v_count INT;

        SELECT
            COUNT(*)
        INTO
            v_count
        FROM (
            SELECT
                l.transaction_id,
                SUM(CASE WHEN l.accounting_type = 'DR' THEN l.amount ELSE 0 END) AS dr_sum,
                SUM(CASE WHEN l.accounting_type = 'CR' THEN l.amount ELSE 0 END) AS cr_sum
            FROM
                {table_name} l
            GROUP BY
                l.transaction_id
            HAVING
                dr_sum != cr_sum
        ) AS MismatchedTransactions;

        IF v_count > 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Mismatched DR and CR sums in Transactions';
        END IF;

    END //

    DELIMITER ;

    CALL CheckTransactionSums();
    """

    with schema_editor.connection.cursor() as cursor:
        if schema_editor.connection.vendor == "postgresql":
            cursor.execute(postgres_sql)
        elif schema_editor.connection.vendor == "mysql":
            cursor.execute(mysql_sql)
