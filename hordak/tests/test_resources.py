import logging
from decimal import Decimal

import tablib
from django.test import TestCase
from django.utils.datetime_safe import date

from hordak.models import Account, StatementImport, StatementLine
from hordak.resources import StatementLineResource
from hordak.tests.utils import DataProvider


class StatementLineResourceTestCase(DataProvider, TestCase):
    """Test the resource definition in test_resources.py"""

    def setUp(self):
        self.account = self.account(is_bank_account=True, type=Account.TYPES.asset)
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.INFO)

    def makeResource(self):
        statement_import = StatementImport.objects.create(bank_account=self.account, source="csv")
        return StatementLineResource("%d/%m/%Y", statement_import)

    def test_import_one(self):
        dataset = tablib.Dataset(
            ["15/6/2016", "5.10", "Example payment"], headers=["date", "amount", "description"]
        )
        self.makeResource().import_data(dataset)

        self.assertEqual(StatementLine.objects.count(), 1)
        obj = StatementLine.objects.get()
        self.assertEqual(obj.date, date(2016, 6, 15))
        self.assertEqual(obj.amount, Decimal("5.10"))
        self.assertEqual(obj.description, "Example payment")

    def test_import_skip_duplicates(self):
        dataset = tablib.Dataset(
            ["15/6/2016", "5.10", "Example payment"], headers=["date", "amount", "description"]
        )
        self.makeResource().import_data(dataset)
        # Now do the import again
        self.makeResource().import_data(dataset)

        # The record in the second should have been ignored
        self.assertEqual(StatementLine.objects.count(), 1)

    def test_import_two_identical(self):
        """Ensure they both get imported and that one doesnt get skipped as a duplicate

        After all, if there are two imported rows that look identical, it is probably because
        there are two identical transactions.
        """
        dataset = tablib.Dataset(
            ["15/6/2016", "5.10", "Example payment"],
            ["15/6/2016", "5.10", "Example payment"],
            headers=["date", "amount", "description"],
        )
        self.makeResource().import_data(dataset)

        self.assertEqual(StatementLine.objects.count(), 2)

    def test_import_a_few(self):
        dataset = tablib.Dataset(
            ["15/6/2016", "5.10", "Example payment"],
            ["16/6/2016", "10.91", "Another payment"],
            ["17/6/2016", "-1.23", "Paying someone"],
            headers=["date", "amount", "description"],
        )
        self.makeResource().import_data(dataset)

        self.assertEqual(StatementLine.objects.count(), 3)
        objs = StatementLine.objects.all().order_by("pk")

        self.assertEqual(objs[0].date, date(2016, 6, 15))
        self.assertEqual(objs[0].amount, Decimal("5.10"))
        self.assertEqual(objs[0].description, "Example payment")

        self.assertEqual(objs[1].date, date(2016, 6, 16))
        self.assertEqual(objs[1].amount, Decimal("10.91"))
        self.assertEqual(objs[1].description, "Another payment")

        self.assertEqual(objs[2].date, date(2016, 6, 17))
        self.assertEqual(objs[2].amount, Decimal("-1.23"))
        self.assertEqual(objs[2].description, "Paying someone")

    def test_import_a_few_with_identical_transactions(self):
        dataset = tablib.Dataset(
            ["15/6/2016", "5.10", "Example payment"],
            ["16/6/2016", "10.91", "Another payment"],
            ["16/6/2016", "10.91", "Another payment"],
            ["17/6/2016", "-1.23", "Paying someone"],
            headers=["date", "amount", "description"],
        )
        self.makeResource().import_data(dataset)

        self.assertEqual(StatementLine.objects.count(), 4)
        objs = StatementLine.objects.all().order_by("pk")

        self.assertEqual(objs[0].date, date(2016, 6, 15))
        self.assertEqual(objs[0].amount, Decimal("5.10"))
        self.assertEqual(objs[0].description, "Example payment")

        self.assertEqual(objs[1].date, date(2016, 6, 16))
        self.assertEqual(objs[1].amount, Decimal("10.91"))
        self.assertEqual(objs[1].description, "Another payment")

        self.assertEqual(objs[2].date, date(2016, 6, 16))
        self.assertEqual(objs[2].amount, Decimal("10.91"))
        self.assertEqual(objs[2].description, "Another payment")

        self.assertEqual(objs[3].date, date(2016, 6, 17))
        self.assertEqual(objs[3].amount, Decimal("-1.23"))
        self.assertEqual(objs[3].description, "Paying someone")

    def test_split_amounts(self):
        dataset = tablib.Dataset(
            ["15/6/2016", "", "100.56", "Example payment"],
            ["16/6/2016", "60.31", "", "Example income"],
            ["17/6/2016", "", "-102.56", "Example payment 2"],
            headers=["date", "amount_in", "amount_out", "description"],
        )
        self.makeResource().import_data(dataset)

        self.assertEqual(StatementLine.objects.count(), 3)

        obj = StatementLine.objects.all().order_by("date")
        self.assertEqual(obj[0].date, date(2016, 6, 15))
        self.assertEqual(obj[0].amount, Decimal("-100.56"))
        self.assertEqual(obj[0].description, "Example payment")

        self.assertEqual(obj[1].date, date(2016, 6, 16))
        self.assertEqual(obj[1].amount, Decimal("60.31"))
        self.assertEqual(obj[1].description, "Example income")

        self.assertEqual(obj[2].date, date(2016, 6, 17))
        self.assertEqual(obj[2].amount, Decimal("-102.56"))
        self.assertEqual(obj[2].description, "Example payment 2")

    def test_error_no_date(self):
        dataset = tablib.Dataset(["5.10", "Example payment"], headers=["amount", "description"])
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn("No date", str(result.row_errors()[0][1][0].error))

    def test_error_empty_date(self):
        dataset = tablib.Dataset(
            ["", "5.10", "Example payment"], headers=["date", "amount", "description"]
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn("Expected dd/mm/yyyy", str(result.row_errors()[0][1][0].error))

    def test_error_empty_amounts(self):
        dataset = tablib.Dataset(
            ["15/6/2016", "", "", "Example payment"],
            headers=["date", "amount_in", "amount_out", "description"],
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn("Value required", str(result.row_errors()[0][1][0].error))

    def test_error_empty_amount(self):
        dataset = tablib.Dataset(
            ["15/6/2016", "", "Example payment"], headers=["date", "amount", "description"]
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn("No value found", str(result.row_errors()[0][1][0].error))

    def test_error_both_amounts(self):
        dataset = tablib.Dataset(
            ["15/6/2016", "5.10", "1.20", "Example payment"],
            headers=["date", "amount_in", "amount_out", "description"],
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn("Values found for both", str(result.row_errors()[0][1][0].error))

    def test_error_neither_amount(self):
        dataset = tablib.Dataset(
            ["15/6/2016", "", "", "Example payment"],
            headers=["date", "amount_in", "amount_out", "description"],
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn("either", str(result.row_errors()[0][1][0].error))

    def test_error_invalid_in_amount(self):
        dataset = tablib.Dataset(
            ["15/6/2016", "a", "", "Example payment"],
            headers=["date", "amount_in", "amount_out", "description"],
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn("Invalid", str(result.row_errors()[0][1][0].error))

    def test_error_invalid_out_amount(self):
        dataset = tablib.Dataset(
            ["15/6/2016", "", "a", "Example payment"],
            headers=["date", "amount_in", "amount_out", "description"],
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn("Invalid", str(result.row_errors()[0][1][0].error))

    def test_error_invalid_amount(self):
        dataset = tablib.Dataset(
            ["15/6/2016", "a", "Example payment"], headers=["date", "amount", "description"]
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn("Invalid", str(result.row_errors()[0][1][0].error))

    def test_error_no_amount(self):
        dataset = tablib.Dataset(["15/6/2016", "Example payment"], headers=["date", "description"])
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn("No amount", str(result.row_errors()[0][1][0].error))

    def test_error_zero_amount(self):
        dataset = tablib.Dataset(
            ["15/6/2016", "0", "Example payment"], headers=["date", "amount", "description"]
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn("zero not allowed", str(result.row_errors()[0][1][0].error))
