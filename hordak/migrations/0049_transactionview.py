# Generated by Django 4.2 on 2024-06-30 11:57

from django.db import migrations, models
import django.db.models.deletion
import hordak.utilities.db


class Migration(migrations.Migration):
    dependencies = [
        ("hordak", "0048_hordak_transaction_view"),
    ]

    operations = [
        migrations.CreateModel(
            name="TransactionView",
            fields=[
                (
                    "parent",
                    models.OneToOneField(
                        db_column="id",
                        editable=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        primary_key=True,
                        related_name="view",
                        serialize=False,
                        to="hordak.transaction",
                    ),
                ),
                ("uuid", models.UUIDField(editable=False, verbose_name="uuid")),
                (
                    "timestamp",
                    models.DateTimeField(
                        editable=False,
                        help_text="The creation date of this transaction object",
                        verbose_name="timestamp",
                    ),
                ),
                (
                    "date",
                    models.DateField(
                        editable=False,
                        help_text="The date on which this transaction occurred",
                        verbose_name="date",
                    ),
                ),
                (
                    "description",
                    models.TextField(editable=False, verbose_name="description"),
                ),
                (
                    "amount",
                    hordak.utilities.db.BalanceField(
                        editable=False,
                        help_text="The total amount transferred in this transaction",
                    ),
                ),
                (
                    "credit_account_ids",
                    models.JSONField(
                        editable=False,
                        help_text="List of account ids for the credit legs of this transaction",
                    ),
                ),
                (
                    "debit_account_ids",
                    models.JSONField(
                        editable=False,
                        help_text="List of account ids for the debit legs of this transaction",
                    ),
                ),
                (
                    "credit_account_names",
                    models.JSONField(
                        editable=False,
                        help_text="List of account names for the credit legs of this transaction",
                    ),
                ),
                (
                    "debit_account_names",
                    models.JSONField(
                        editable=False,
                        help_text="List of account names for the debit legs of this transaction",
                    ),
                ),
            ],
            options={
                "db_table": "hordak_transaction_view",
                "managed": False,
            },
        ),
    ]
