from django.db import transaction
from django.test import TransactionTestCase
from django_concurrent_tests.helpers import call_concurrently, make_concurrent_calls
from moneyed import Money

from hordak.models import Account, Leg, Transaction
from hordak.utilities.currency import Balance


@transaction.atomic
def create_transaction(account1_id, account2_id):
    h_trans = Transaction.objects.create()
    Leg.objects.create(
        transaction=h_trans,
        account_id=account1_id,
        amount=Money(1, "USD"),
    )
    Leg.objects.create(
        transaction=h_trans,
        account_id=account2_id,
        amount=Money(-1, "USD"),
    )


@transaction.atomic
def delete_one_transaction(transaction_id):
    Transaction.objects.get(id=transaction_id).delete()


class ConcurrentRunningTotalsTest(TransactionTestCase):
    def test_multiple_concurrent_transactions(self):
        """
        Addin money to account multiple times concurrently should result in correct running totals value.
        """
        account1 = Account.objects.create(name="account1", currencies=["USD"])
        account2 = Account.objects.create(name="account2", currencies=["USD"])
        account1.update_running_totals()
        account2.update_running_totals()
        self.assertEqual(account1.simple_balance(), Balance([Money(0, "USD")]))
        self.assertEqual(account2.simple_balance(), Balance([Money(0, "USD")]))
        call_count = 10
        call_concurrently(
            call_count,
            create_transaction,
            account1_id=account1.id,
            account2_id=account2.id,
        )
        account1.refresh_from_db()
        account2.refresh_from_db()
        self.assertEqual(account1.simple_balance(), Balance([Money(call_count, "USD")]))
        self.assertEqual(
            account2.simple_balance(), Balance([Money(-call_count, "USD")])
        )

        # Not delete the transactions one by one to check if the
        # running totals are updated correctly during delete
        calls = [
            (delete_one_transaction, {"transaction_id": transaction.id})
            for transaction in Transaction.objects.all()
        ]
        make_concurrent_calls(*calls)
        account1.refresh_from_db()
        account2.refresh_from_db()
        self.assertEqual(account1.simple_balance(), Balance([Money(0, "USD")]))
        self.assertEqual(account2.simple_balance(), Balance([Money(0, "USD")]))
