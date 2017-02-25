import six
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from hordak.forms.statement_import import TransactionImportForm
from hordak.models import Account, TransactionImport
from hordak.tests.utils import DataProvider


class TransactionImportFormTestCase(DataProvider, TestCase):

    def setUp(self):
        self.account = self.account(is_bank_account=True, type=Account.TYPES.asset)
        self.f = SimpleUploadedFile('data.csv',
                                    six.binary_type(b'Number,Date,Account,Amount,Subcategory,Memo'))

    def test_create(self):
        form = TransactionImportForm(data=dict(bank_account=self.account.pk), files=dict(file=self.f))
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        obj = TransactionImport.objects.get()
        self.assertEqual(obj.columns.count(), 6)
        self.assertEqual(obj.hordak_import.bank_account, self.account)

    def test_edit(self):
        obj = TransactionImport.objects.create(
            hordak_import=self.statement_import(bank_account=self.account),
            has_headings=True,
            file=self.f
        )
        form = TransactionImportForm(data=dict(bank_account=self.account.pk), files=dict(file=self.f), instance=obj)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(obj.columns.count(), 0)
