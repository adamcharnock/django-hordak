import logging

import six
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from hordak.models import TransactionCsvImport, StatementLine, TransactionCsvImportColumn
from hordak.tests.utils import DataProvider
from hordak.views import CreateImportView


class DryRunViewTestCase(DataProvider, TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.login()

    def tearDown(self):
        logging.disable(logging.INFO)

    def create_import(self, year=b'2000'):
        f = SimpleUploadedFile('data.csv',
                               six.binary_type(
                                   b'Number,Date,Account,Amount,Subcategory,Memo\n'
                                   b'1,1/1/' + year + b',123456789,123,OTH,Some random notes')
                               )
        self.transaction_import = TransactionCsvImport.objects.create(
            has_headings=True,
            file=f,
            date_format='%d/%m/%Y',
            hordak_import=self.statement_import(),
        )
        self.view_url = reverse('hordak:import_dry_run', args=[self.transaction_import.uuid])
        self.transaction_import.create_columns()

        self.transaction_import.columns.filter(column_number=2).update(to_field='date')
        self.transaction_import.columns.filter(column_number=4).update(to_field='amount')
        self.transaction_import.columns.filter(column_number=6).update(to_field='description')

    def test_get(self):
        self.create_import()

        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(StatementLine.objects.count(), 0)

    def test_post(self):
        self.create_import()

        response = self.client.post(self.view_url)
        result = response.context['result']

        self.assertEqual(len(result.failed_dataset), 0, result.failed_dataset.dict)
        self.assertEqual(result.base_errors, [])
        self.assertEqual(result.totals['new'], 1)
        self.assertEqual(result.totals['update'], 0)
        self.assertEqual(result.totals['delete'], 0)
        self.assertEqual(result.totals['skip'], 0)
        self.assertEqual(result.totals['error'], 0)

        self.assertEqual(StatementLine.objects.count(), 0)

    def test_date_error(self):
        self.create_import(b'1')

        response = self.client.post(self.view_url)
        result = response.context['result']

        self.assertEqual(len(result.failed_dataset), 1, result.failed_dataset.dict)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertEqual(StatementLine.objects.count(), 0)


class ExecuteViewTestCase(DataProvider, TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.login()

    def tearDown(self):
        logging.disable(logging.INFO)

    def create_import(self, year=b'2000'):
        f = SimpleUploadedFile('data.csv',
                               six.binary_type(
                                   b'Number,Date,Account,Amount,Subcategory,Memo\n'
                                   b'1,1/1/' + year + b',123456789,123,OTH,Some random notes')
                               )
        self.transaction_import = TransactionCsvImport.objects.create(
            has_headings=True,
            file=f,
            date_format='%d/%m/%Y',
            hordak_import=self.statement_import()
        )
        self.view_url = reverse('hordak:import_execute', args=[self.transaction_import.uuid])
        self.transaction_import.create_columns()

        self.transaction_import.columns.filter(column_number=2).update(to_field='date')
        self.transaction_import.columns.filter(column_number=4).update(to_field='amount')
        self.transaction_import.columns.filter(column_number=6).update(to_field='description')

    def test_get(self):
        self.create_import()

        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StatementLine.objects.count(), 0)

    def test_post(self):
        self.create_import()

        response = self.client.post(self.view_url)
        result = response.context['result']

        self.assertEqual(len(result.failed_dataset), 0, result.failed_dataset.dict)
        self.assertEqual(result.base_errors, [])
        self.assertEqual(result.totals['new'], 1)
        self.assertEqual(result.totals['update'], 0)
        self.assertEqual(result.totals['delete'], 0)
        self.assertEqual(result.totals['skip'], 0)
        self.assertEqual(result.totals['error'], 0)

        self.assertEqual(StatementLine.objects.count(), 1)

    def test_date_error(self):
        self.create_import(b'1')

        response = self.client.post(self.view_url)
        result = response.context['result']

        self.assertEqual(len(result.failed_dataset), 1, result.failed_dataset.dict)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertEqual(StatementLine.objects.count(), 0)


class CreateImportViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.view_url = reverse('hordak:import_create')
        self.login()

    def test_load(self):
        response = self.client.post(self.view_url)
        self.assertEqual(response.status_code, 200)

    def test_success_url(self):
        view = CreateImportView()
        view.object = TransactionCsvImport.objects.create(hordak_import=self.statement_import())
        self.assertIn(str(view.object.uuid), view.get_success_url())


class SetupImportViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.transaction_import = TransactionCsvImport.objects.create(hordak_import=self.statement_import())
        self.view_url = reverse('hordak:import_setup', args=[self.transaction_import.uuid])
        self.login()

    def test_load(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)

    def test_submit(self):
        column1 = TransactionCsvImportColumn.objects.create(
            transaction_import=self.transaction_import,
            column_number=1,
            column_heading='Transaction Date',
            example='1/1/1'
        )

        column2 = TransactionCsvImportColumn.objects.create(
            transaction_import=self.transaction_import,
            column_number=2,
            column_heading='Transaction Amount',
            example='123.45'
        )

        response = self.client.post(self.view_url, data={
            'date_format': '%d-%m-%Y',

            'columns-INITIAL_FORMS': '2',
            'columns-TOTAL_FORMS': '2',

            'columns-0-id': column1.pk,
            'columns-0-to_field': 'date',

            'columns-1-id': column2.pk,
            'columns-1-to_field': 'amount',
        })
        if response.context:
            # If we have a context then it is going to be because the form has errors
            self.assertFalse(response.context['form'].errors)

        self.transaction_import.refresh_from_db()
        column1.refresh_from_db()
        column2.refresh_from_db()

        self.assertEqual(self.transaction_import.date_format, '%d-%m-%Y')
        self.assertEqual(column1.to_field, 'date')
        self.assertEqual(column2.to_field, 'amount')
