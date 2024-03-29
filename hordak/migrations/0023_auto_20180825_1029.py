# Generated by Django 2.1 on 2018-08-25 10:29

from django.db import migrations, models

import hordak.models.core


class Migration(migrations.Migration):
    dependencies = [("hordak", "0022_auto_20180825_1026")]

    operations = [
        migrations.AlterField(
            model_name="statementimport",
            name="extra",
            field=models.JSONField(
                default=hordak.models.core.json_default,
                help_text="Any extra data relating to the import, probably specific to the data source.",
            ),
        ),
        migrations.AlterField(
            model_name="statementline",
            name="source_data",
            field=models.JSONField(
                default=hordak.models.core.json_default,
                help_text="Original data received from the data source.",
            ),
        ),
    ]
