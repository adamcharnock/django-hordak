# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-12-05 13:05
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("hordak", "0018_auto_20171205_1256")]

    operations = [
        migrations.AddField(
            model_name="statementimport",
            name="source",
            field=models.CharField(
                default="csv",
                help_text='A value uniquely identifying where this data came from. Examples: "csv", "teller.io".',
                max_length=20,
            ),
            preserve_default=False,
        )
    ]
