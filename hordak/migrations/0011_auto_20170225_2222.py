# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2017-02-25 22:22
from __future__ import unicode_literals

from uuid import uuid4

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("hordak", "0010_auto_20161216_1202")]

    operations = [
        migrations.CreateModel(
            name="TransactionImport",
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
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid4,
                        editable=False,
                        unique=True,
                    ),
                ),
                (
                    "timestamp",
                    models.DateTimeField(
                        default=django.utils.timezone.now, editable=False
                    ),
                ),
                (
                    "has_headings",
                    models.BooleanField(
                        default=True,
                        verbose_name="First line of file contains headings",
                    ),
                ),
                (
                    "file",
                    models.FileField(
                        upload_to="transaction_imports",
                        verbose_name="CSV file to import",
                    ),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("uploaded", "Uploaded, ready to import"),
                            ("done", "Import complete"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "date_format",
                    models.CharField(
                        choices=[
                            ("%d-%m-%Y", "dd-mm-yyyy"),
                            ("%d/%m/%Y", "dd/mm/yyyy"),
                            ("%d.%m.%Y", "dd.mm.yyyy"),
                            ("%d-%Y-%m", "dd-yyyy-mm"),
                            ("%d/%Y/%m", "dd/yyyy/mm"),
                            ("%d.%Y.%m", "dd.yyyy.mm"),
                            ("%m-%d-%Y", "mm-dd-yyyy"),
                            ("%m/%d/%Y", "mm/dd/yyyy"),
                            ("%m.%d.%Y", "mm.dd.yyyy"),
                            ("%m-%Y-%d", "mm-yyyy-dd"),
                            ("%m/%Y/%d", "mm/yyyy/dd"),
                            ("%m.%Y.%d", "mm.yyyy.dd"),
                            ("%Y-%d-%m", "yyyy-dd-mm"),
                            ("%Y/%d/%m", "yyyy/dd/mm"),
                            ("%Y.%d.%m", "yyyy.dd.mm"),
                            ("%Y-%m-%d", "yyyy-mm-dd"),
                            ("%Y/%m/%d", "yyyy/mm/dd"),
                            ("%Y.%m.%d", "yyyy.mm.dd"),
                            ("%d-%m-%y", "dd-mm-yy"),
                            ("%d/%m/%y", "dd/mm/yy"),
                            ("%d.%m.%y", "dd.mm.yy"),
                            ("%d-%y-%m", "dd-yy-mm"),
                            ("%d/%y/%m", "dd/yy/mm"),
                            ("%d.%y.%m", "dd.yy.mm"),
                            ("%m-%d-%y", "mm-dd-yy"),
                            ("%m/%d/%y", "mm/dd/yy"),
                            ("%m.%d.%y", "mm.dd.yy"),
                            ("%m-%y-%d", "mm-yy-dd"),
                            ("%m/%y/%d", "mm/yy/dd"),
                            ("%m.%y.%d", "mm.yy.dd"),
                            ("%y-%d-%m", "yy-dd-mm"),
                            ("%y/%d/%m", "yy/dd/mm"),
                            ("%y.%d.%m", "yy.dd.mm"),
                            ("%y-%m-%d", "yy-mm-dd"),
                            ("%y/%m/%d", "yy/mm/dd"),
                            ("%y.%m.%d", "yy.mm.dd"),
                        ],
                        default="%d-%m-%Y",
                        max_length=50,
                    ),
                ),
                (
                    "hordak_import",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="hordak.StatementImport",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="TransactionImportColumn",
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
                ("column_number", models.PositiveSmallIntegerField()),
                (
                    "column_heading",
                    models.CharField(
                        blank=True, default="", max_length=100, verbose_name="Column"
                    ),
                ),
                (
                    "to_field",
                    models.CharField(
                        blank=True,
                        choices=[
                            (None, "-- Do not import --"),
                            ("date", "Date"),
                            ("amount", "Amount"),
                            ("amount_out", "Amount (money in only)"),
                            ("amount_in", "Amount (money out only)"),
                            ("description", "Description / Notes"),
                        ],
                        default=None,
                        max_length=20,
                        null=True,
                        verbose_name="Is",
                    ),
                ),
                ("example", models.CharField(blank=True, default="", max_length=200)),
                (
                    "transaction_import",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="columns",
                        to="hordak.TransactionImport",
                    ),
                ),
            ],
            options={"ordering": ["transaction_import", "column_number"]},
        ),
        migrations.AlterUniqueTogether(
            name="transactionimportcolumn",
            unique_together=set(
                [
                    ("transaction_import", "column_number"),
                    ("transaction_import", "to_field"),
                ]
            ),
        ),
    ]
