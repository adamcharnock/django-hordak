# Generated by Django 4.2 on 2024-06-27 09:11
from pathlib import Path

from django.db import migrations

from hordak.utilities.migrations import (
    select_database_type,
    migration_operations_from_sql,
)

PATH = Path(__file__).parent


class Migration(migrations.Migration):
    dependencies = [
        ("hordak", "0046_alter_account_uuid_alter_leg_uuid_and_more"),
    ]

    operations = select_database_type(
        postgresql=migration_operations_from_sql(PATH / "0047_get_balance.pg.sql"),
        mysql=migration_operations_from_sql(PATH / "0047_get_balance.mysql.sql"),
    )
