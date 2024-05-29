# Generated by Django 4.2 on 2023-05-02 14:36

import django.db.models.deletion
import djmoney.models.fields
from django.db import migrations, models
from hordak.defaults import DECIMAL_PLACES, MAX_DIGITS
import hordak.models.core


class Migration(migrations.Migration):
    dependencies = [
        ("hordak", "0034_alter_account_currencies_alter_leg_amount_currency"),
    ]

    operations = [
        migrations.CreateModel(
            name="RunningTotal",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("currency", models.CharField(max_length=15)),
                (
                    "balance_currency",
                    djmoney.models.fields.CurrencyField(
                        choices=hordak.models.core.get_currency_choices(),
                        default=hordak.models.core.get_internal_currency,
                        editable=False,
                        max_length=3,
                        null=True,
                    ),
                ),
                (
                    "balance",
                    djmoney.models.fields.MoneyField(
                        blank=True,
                        decimal_places=DECIMAL_PLACES,
                        default_currency=hordak.models.core.get_internal_currency,
                        max_digits=MAX_DIGITS,
                        null=True,
                    ),
                ),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="running_totals",
                        to="hordak.account",
                    ),
                ),
            ],
            options={
                "verbose_name": "Running Total",
                "verbose_name_plural": "Running Totals",
            },
        ),
    ]
