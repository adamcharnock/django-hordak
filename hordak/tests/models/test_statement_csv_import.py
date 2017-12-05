import six
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from hordak.models import TransactionCsvImport
from hordak.tests.utils import DataProvider


class TransactionCsvImportTestCase(DataProvider, TestCase):

    def test_create_columns_ok(self):
        f = SimpleUploadedFile('data.csv',
                               six.binary_type(
                                   b'Number,Date,Account,Amount,Subcategory,Memo\n'
                                   b'1,1/1/1,123456789,123,OTH,Some random notes')
                               )

        inst = TransactionCsvImport.objects.create(has_headings=True, file=f, hordak_import=self.statement_import())
        inst.create_columns()

        columns = inst.columns.all()

        self.assertEqual(columns[0].column_number, 1)
        self.assertEqual(columns[0].column_heading, 'Number')
        self.assertEqual(columns[0].to_field, None)
        self.assertEqual(columns[0].example, '1')

        self.assertEqual(columns[1].column_number, 2)
        self.assertEqual(columns[1].column_heading, 'Date')
        self.assertEqual(columns[1].to_field, 'date')
        self.assertEqual(columns[1].example, '1/1/1')

        self.assertEqual(columns[2].column_number, 3)
        self.assertEqual(columns[2].column_heading, 'Account')
        self.assertEqual(columns[2].to_field, None)
        self.assertEqual(columns[2].example, '123456789')

        self.assertEqual(columns[3].column_number, 4)
        self.assertEqual(columns[3].column_heading, 'Amount')
        self.assertEqual(columns[3].to_field, 'amount')
        self.assertEqual(columns[3].example, '123')

        self.assertEqual(columns[4].column_number, 5)
        self.assertEqual(columns[4].column_heading, 'Subcategory')
        self.assertEqual(columns[4].to_field, None)
        self.assertEqual(columns[4].example, 'OTH')

        self.assertEqual(columns[5].column_number, 6)
        self.assertEqual(columns[5].column_heading, 'Memo')
        self.assertEqual(columns[5].to_field, 'description')
        self.assertEqual(columns[5].example, 'Some random notes')
