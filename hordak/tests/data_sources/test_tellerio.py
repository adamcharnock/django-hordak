from decimal import Decimal

from datetime import date
from uuid import UUID

from django.test.testcases import TestCase
import requests_mock

from hordak.data_sources import tellerio
from hordak.models import StatementImport
from hordak.models.core import StatementLine, Account
from hordak.tests.utils import DataProvider


class TellerIoDataSourceTestCase(DataProvider, TestCase):

    def setUp(self):
        self.bank = self.account(name='bank', type=Account.TYPES.asset, is_bank_account=True)

    @requests_mock.mock()
    def test_simple(self, m):
        m.get(
            'https://api.teller.io/accounts/11111111-1111-4111-1111-111111111111/transactions',
            json=EXAMPLE_JSON,
            headers={
                'Authorization': 'Bearer testtoken'
            }
        )

        tellerio.do_import(
            token='testtoken',
            account_uuid='11111111-1111-4111-1111-111111111111',
            bank_account=self.bank
        )

        self.assertEqual(StatementImport.objects.count(), 1)
        self.assertEqual(StatementLine.objects.count(), 3)

        statement_import = StatementImport.objects.get()
        line1, line2, line3 = StatementLine.objects.order_by('-date').all()

        self.assertEqual(statement_import.source, 'teller.io')
        self.assertEqual(statement_import.extra, {
            'account_uuid': '11111111-1111-4111-1111-111111111111',
        })

        self.assertEqual(line1.uuid, UUID('11111111-1111-4111-2222-111111111111'))
        self.assertEqual(line1.amount, Decimal('-11.35'))
        self.assertEqual(line1.description, 'MARKS&SPENCER PLC, 3903 24MAR17 CD , MARKS&SPENCER PLC , PANTHEON GB')
        self.assertEqual(line1.type, 'card_payment')
        self.assertEqual(line1.statement_import, statement_import)
        self.assertEqual(line1.date, date(2017, 3, 27))
        self.assertEqual(line1.source_data, EXAMPLE_JSON[0])

        self.assertEqual(line2.uuid, UUID('11111111-1111-4111-3333-111111111111'))
        self.assertEqual(line2.amount, Decimal('-22.55'))
        self.assertEqual(line2.description, 'HARE & TORTOISE, 3903 25MAR17 CD , HARE & TORTOISE , BRUNSW , LONDON GB')
        self.assertEqual(line1.type, 'card_payment')
        self.assertEqual(line2.statement_import, statement_import)
        self.assertEqual(line2.date, date(2017, 3, 26))
        self.assertEqual(line2.source_data, EXAMPLE_JSON[1])

    @requests_mock.mock()
    def test_does_not_duplicate(self, m):
        m.get(
            'https://api.teller.io/accounts/11111111-1111-4111-1111-111111111111/transactions', json=EXAMPLE_JSON,
        )
        m.get(
            'https://api.teller.io/accounts/11111111-1111-4111-1111-111111111111/transactions', json=EXAMPLE_JSON,
        )
        tellerio.do_import(
            token='testtoken',
            account_uuid='11111111-1111-4111-1111-111111111111',
            bank_account=self.bank
        )
        tellerio.do_import(
            token='testtoken',
            account_uuid='11111111-1111-4111-1111-111111111111',
            bank_account=self.bank
        )
        self.assertEqual(StatementLine.objects.count(), 3)

    @requests_mock.mock()
    def test_since_none(self, m):
        m.get(
            'https://api.teller.io/accounts/11111111-1111-4111-1111-111111111111/transactions', json=EXAMPLE_JSON,
        )
        tellerio.do_import(
            token='testtoken',
            account_uuid='11111111-1111-4111-1111-111111111111',
            bank_account=self.bank,
            since=date(2017, 3, 28)
        )
        self.assertEqual(StatementLine.objects.count(), 0)

    @requests_mock.mock()
    def test_since_on_cutoff(self, m):
        m.get(
            'https://api.teller.io/accounts/11111111-1111-4111-1111-111111111111/transactions', json=EXAMPLE_JSON,
        )
        tellerio.do_import(
            token='testtoken',
            account_uuid='11111111-1111-4111-1111-111111111111',
            bank_account=self.bank,
            since=date(2017, 3, 27)
        )
        self.assertEqual(StatementLine.objects.count(), 1)

    @requests_mock.mock()
    def test_since_all(self, m):
        m.get(
            'https://api.teller.io/accounts/11111111-1111-4111-1111-111111111111/transactions', json=EXAMPLE_JSON,
        )
        tellerio.do_import(
            token='testtoken',
            account_uuid='11111111-1111-4111-1111-111111111111',
            bank_account=self.bank,
            since=date(2017, 3, 20)
        )
        self.assertEqual(StatementLine.objects.count(), 3)


EXAMPLE_JSON = [
    {
        'amount': '-11.35',
        'counterparty': 'MARKS&SPENCER PLC',
        'date': '2017-03-27',
        'description': '3903 24MAR17 CD , MARKS&SPENCER PLC , PANTHEON GB',
        'id': '11111111-1111-4111-2222-111111111111',
        'links': {
            'self': 'https://api.teller.io/accounts/11111111-1111-1111-1111-111111111111/transactions/:id'
        },
        'running_balance': '7717.81',
        'type': 'card_payment'
    },
    {
        'id': '11111111-1111-4111-3333-111111111111',
        'links': {
            'self': 'https://api.teller.io/accounts/11111111-1111-1111-1111-111111111111/transactions/:id'
        },
        'description': '3903 25MAR17 CD , HARE & TORTOISE , BRUNSW , LONDON GB',
        'type': 'card_payment',
        'counterparty': 'HARE & TORTOISE',
        'running_balance': '7737.16',
        'amount': '-22.55',
        'date': '2017-03-26'
    },
    {
        'counterparty': 'MARKS&SPENCER PLC',
        'running_balance': '7729.16',
        'amount': '-8.00',
        'date': '2017-03-25',
        'id': '11111111-1111-4111-4444-111111111111',
        'links': {
            'self': 'https://api.teller.io/accounts/11111111-1111-1111-1111-111111111111/transactions/:id'
        },
        'type': 'card_payment',
        'description': '3903 26MAR17 CD , MARKS&SPENCER PLC , PANTHEON GB'
    },

]
