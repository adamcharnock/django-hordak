from decimal import Decimal, DecimalException

from django.utils.datetime_safe import datetime
from import_export import resources
from import_export.results import Result as _Result

from hordak.models import StatementLine, TransactionCsvImportColumn
from hordak.utilities.statement_import import DATE_FORMATS


class Result(_Result):
    def append_failed_row(self, row, error):
        # This class can be removed once this is merged:
        #   https://github.com/django-import-export/django-import-export/pull/526
        row_values = [v for (k, v) in row.items()]
        row_values.append(str(error.error))
        self.failed_dataset.append(row_values)


class StatementLineResource(resources.ModelResource):
    class Meta:
        model = StatementLine
        fields = ("date", "amount", "description")

    def __init__(self, date_format, statement_import):
        self.date_format = date_format
        self.statement_import = statement_import

    @classmethod
    def get_result_class(self):
        return Result

    def before_import(self, dataset, using_transactions, dry_run, **kwargs):
        # We're going to need this to check for duplicates (because
        # there could be multiple identical transactions)
        self.dataset = dataset
        similar_totals = [0] * len(self.dataset)

        for i, row in enumerate(dataset):
            num_similar = self._get_num_similar_rows(row, until=i)
            similar_totals[i] = num_similar

        # Add a new 'similar_total' column. This is a integer of how many
        # identical rows precede this one.
        self.dataset.append_col(similar_totals, header="similar_total")

    def before_save_instance(self, instance, using_transactions, dry_run):
        # We need to record this statement line against the parent statement import
        # instance passed to the constructor
        instance.statement_import = self.statement_import

    def get_instance(self, instance_loader, row):
        # We never update, we either create or skip
        return None

    def init_instance(self, row=None):
        # Attach the row to the instance as we'll need it in skip_row()
        instance = super(StatementLineResource, self).init_instance(row)
        instance._row = row
        return instance

    def skip_row(self, instance, original):
        # Skip this row if the database already contains the requsite number of
        # rows identical to this one.
        return instance._row["similar_total"] < self._get_num_similar_objects(instance)

    def _get_num_similar_objects(self, obj):
        """Get any statement lines which would be considered a duplicate of obj"""
        return StatementLine.objects.filter(
            date=obj.date, amount=obj.amount, description=obj.description
        ).count()

    def _get_num_similar_rows(self, row, until=None):
        """Get the number of rows similar to row which precede the index `until`"""
        return len(list(filter(lambda r: row == r, self.dataset[:until])))

    def import_obj(self, obj, data, dry_run):
        F = TransactionCsvImportColumn.TO_FIELDS
        use_dual_amounts = F.amount_out in data and F.amount_in in data

        if F.date not in data:
            raise ValueError("No date column found")

        try:
            date = datetime.strptime(data[F.date], self.date_format).date()
        except ValueError:
            raise ValueError(
                "Invalid value for date. Expected {}".format(dict(DATE_FORMATS)[self.date_format])
            )

        description = data[F.description]

        # Do we have in/out columns, or just one amount column?
        if use_dual_amounts:
            amount_out = data[F.amount_out]
            amount_in = data[F.amount_in]

            if amount_in and amount_out:
                raise ValueError("Values found for both Amount In and Amount Out")
            if not amount_in and not amount_out:
                raise ValueError("Value required for either Amount In or Amount Out")

            if amount_out:
                try:
                    amount = abs(Decimal(amount_out)) * -1
                except DecimalException:
                    raise ValueError("Invalid value found for Amount Out")
            else:
                try:
                    amount = abs(Decimal(amount_in))
                except DecimalException:
                    raise ValueError("Invalid value found for Amount In")
        else:
            if F.amount not in data:
                raise ValueError("No amount column found")
            if not data[F.amount]:
                raise ValueError("No value found for amount")
            try:
                amount = Decimal(data[F.amount])
            except:
                raise DecimalException("Invalid value found for Amount")

        if amount == Decimal("0"):
            raise ValueError("Amount of zero not allowed")

        data = dict(date=date, amount=amount, description=description)
        return super(StatementLineResource, self).import_obj(obj, data, dry_run)
