from pathlib import Path
from typing import TypeVar

from django.db import migrations


def migration_operations_from_sql(file_path: Path):
    operations = []
    sql: str = file_path.read_text(encoding="utf8").strip().strip("-")
    # Mysql needs to have spaces after a '--' comment
    sql = sql.replace("-- ----", "------").replace("-- -", "---")
    if not sql:
        return []

    sql_statements = sql.split("\n------\n")
    for sql_statement in sql_statements:
        if "--- reverse:" in sql_statement:
            forward, reverse = sql_statement.split("--- reverse:")
        else:
            forward, reverse = sql_statement, None

        if _is_empty_sql_statement(forward):
            raise Exception("Forward SQL statement cannot be empty")

        if reverse is not None and _is_empty_sql_statement(reverse):
            # Reverse is specified, but is empty. So assume no reverse
            # action is required
            reverse = ""

        operations.append(migrations.RunSQL(sql=forward, reverse_sql=reverse))

    return operations


T = TypeVar("T", bound=migrations.RunSQL)


def select_database_type(postgresql: T, mysql: T) -> T:
    from django.db import connections

    from hordak.models import Account

    database_name = Account.objects.get_queryset().db
    db_vendor = connections[database_name].vendor
    if db_vendor == "mysql":
        return mysql
    else:
        return postgresql


def _is_empty_sql_statement(sql: str) -> bool:
    """Remove comments and strip whitespace"""
    lines = sql.split("\n")
    lines = [
        line.strip()
        for line in lines
        if not line.strip().startswith("--") and line.strip()
    ]
    return not bool(lines)
