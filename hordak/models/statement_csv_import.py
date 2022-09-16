import csv
from io import StringIO

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_smalluuid.models import SmallUUIDField, uuid_default
from model_utils import Choices
from tablib import Dataset

from hordak.utilities.statement_import import DATE_FORMATS


class TransactionCsvImport(models.Model):
    STATES = Choices(
        ("pending", "Pending"),
        ("uploaded", "Uploaded, ready to import"),
        ("done", "Import complete"),
    )

    uuid = SmallUUIDField(
        default=uuid_default(), editable=False, verbose_name=_("uuid")
    )
    timestamp = models.DateTimeField(
        default=timezone.now, editable=False, verbose_name=_("timestamp")
    )
    has_headings = models.BooleanField(
        default=True, verbose_name=_("First line of file contains headings")
    )
    file = models.FileField(
        upload_to="transaction_imports", verbose_name=_("CSV file to import")
    )
    state = models.CharField(
        max_length=20, choices=STATES, default="pending", verbose_name=_("state")
    )
    date_format = models.CharField(
        choices=DATE_FORMATS,
        max_length=50,
        default="%d-%m-%Y",
        null=False,
        verbose_name=_("date format"),
    )
    hordak_import = models.ForeignKey(
        "hordak.StatementImport",
        on_delete=models.CASCADE,
        verbose_name=_("hordak import"),
    )

    def _get_csv_reader(self):
        # TODO: Refactor to support multiple readers (xls, quickbooks, etc)
        csv_buffer = StringIO(self.file.read().decode())
        return csv.reader(csv_buffer)

    def create_columns(self):
        """For each column in file create a TransactionCsvImportColumn"""
        reader = self._get_csv_reader()
        headings = next(reader)
        try:
            examples = next(reader)
        except StopIteration:
            examples = []

        found_fields = set()
        for i, value in enumerate(headings):
            if i >= 20:
                break

            infer_field = self.has_headings and value not in found_fields

            to_field = (
                {
                    "date": "date",
                    "amount": "amount",
                    "description": "description",
                    "memo": "description",
                    "notes": "description",
                }.get(value.lower(), "")
                if infer_field
                else ""
            )

            if to_field:
                found_fields.add(to_field)

            TransactionCsvImportColumn.objects.update_or_create(
                transaction_import=self,
                column_number=i + 1,
                column_heading=value if self.has_headings else "",
                to_field=to_field,
                example=examples[i].strip() if examples else "",
            )

    def get_dataset(self):
        reader = self._get_csv_reader()
        if self.has_headings:
            next(reader)

        data = list(reader)
        headers = [
            column.to_field or "col_%s" % column.column_number
            for column in self.columns.all()
        ]
        return Dataset(*data, headers=headers)


class TransactionCsvImportColumn(models.Model):
    """Represents a column in an imported CSV file

    Stores information regarding how we map to the data in the column
    to our hordak.StatementLine models.
    """

    TO_FIELDS = Choices(
        (None, "-- Do not import --"),
        ("date", "Date"),
        ("amount", "Amount"),
        ("amount_out", "Amount (money out only)"),
        ("amount_in", "Amount (money in only)"),
        ("description", "Description / Notes"),
    )

    transaction_import = models.ForeignKey(
        TransactionCsvImport,
        related_name="columns",
        on_delete=models.CASCADE,
        verbose_name=_("transaction import"),
    )
    column_number = models.PositiveSmallIntegerField(verbose_name=_("column number"))
    column_heading = models.CharField(
        max_length=100, default="", blank=True, verbose_name=_("Column")
    )
    # TODO: Create a constraint to limit to_field to only valid values
    to_field = models.CharField(
        max_length=20,
        blank=True,
        default=None,
        null=True,
        choices=TO_FIELDS,
        verbose_name=_("Is"),
    )
    example = models.CharField(
        max_length=200, blank=True, default="", null=False, verbose_name=_("example")
    )

    class Meta:
        unique_together = (
            ("transaction_import", "to_field"),
            ("transaction_import", "column_number"),
        )
        ordering = ["transaction_import", "column_number"]
        verbose_name = _("transactionCsvImportColumn")

    def save(self, *args, **kwargs):
        if not self.to_field:
            self.to_field = None
        return super(TransactionCsvImportColumn, self).save(*args, **kwargs)
