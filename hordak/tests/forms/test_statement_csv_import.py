import six
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from hordak.forms.statement_csv_import import TransactionCsvImportForm
from hordak.models import Account, TransactionCsvImport
from hordak.tests.utils import DataProvider


class TransactionCsvImportFormTestCase(DataProvider, TestCase):

    def setUp(self):
        self.account = self.account(is_bank_account=True, type=Account.TYPES.asset)
        self.f = SimpleUploadedFile('data.csv',
                                    six.binary_type(b'Number,Date,Account,Amount,Subcategory,Memo'))

    def test_create(self):
        form = TransactionCsvImportForm(data=dict(bank_account=self.account.pk), files=dict(file=self.f))
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        obj = TransactionCsvImport.objects.get()
        self.assertEqual(obj.columns.count(), 6)
        self.assertEqual(obj.hordak_import.bank_account, self.account)

    def test_edit(self):
        obj = TransactionCsvImport.objects.create(
            hordak_import=self.statement_import(bank_account=self.account),
            has_headings=True,
            file=self.f
        )
        form = TransactionCsvImportForm(data=dict(bank_account=self.account.pk), files=dict(file=self.f), instance=obj)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(obj.columns.count(), 0)
