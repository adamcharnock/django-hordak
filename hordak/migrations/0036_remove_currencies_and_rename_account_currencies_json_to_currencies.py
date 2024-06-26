# Generated by Django 4.2 on 2023-05-16 01:36

from django.db import migrations, models

import hordak
from hordak.defaults import DEFAULT_CURRENCY


class Migration(migrations.Migration):
    dependencies = [
        ("hordak", "0035_account_currencies_json"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="account",
            name="currencies",
        ),
        migrations.RenameField(
            model_name="account",
            old_name="currencies_json",
            new_name="currencies",
        ),
        migrations.AlterField(
            model_name="account",
            name="currencies",
            field=models.JSONField(
                db_index=True,
                default=(DEFAULT_CURRENCY,),
                verbose_name="currencies",
            ),
        ),
    ]
