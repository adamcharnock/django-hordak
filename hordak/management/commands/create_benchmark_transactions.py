# flake8: noqa
import random
import sys

from django.core.management.base import BaseCommand
from django.db import connection
from django.db import transaction as db_transaction
from moneyed import Money

from hordak.models import Account, Leg, Transaction


class Command(BaseCommand):
    help = (
        "Create transactions for benchmarking against. "
        "Expects `./manage.py create_chart_of_accounts` to be run first."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            default=False,
            help="Delete all existing transactions from database",
        )
        parser.add_argument(
            "--multiplier",
            type=int,
            default=10_000,
            help="Scale up how many transactions we create",
        )

    def handle(self, *args, **options):
        m = options["multiplier"]
        if options["clear"]:
            with connection.cursor() as cur:
                cur.execute("TRUNCATE hordak_transaction CASCADE")

        bank: Account = Account.objects.get(name="Bank")
        assets: Account = Account.objects.get(name="Fixed")
        expenses: Account = Account.objects.get(name="Direct")
        liabilities: Account = Account.objects.get(name="Non-Current")
        capital: Account = Account.objects.get(name="Capital - Ordinary Shares")

        print("Creating: Bank | Liabilities")
        _create_many(bank, liabilities, count=m)
        print("Creating: Liabilities | Capital")
        _create_many(liabilities, capital, count=m)
        print("Creating: Assets | Expenses")
        _create_many(assets, expenses, count=m)
        print("Done")
        print("")

        print(
            f"Bank:         {str(bank.get_balance()):<15}  {str(bank.legs.count()):<15}"
        )
        print(
            f"Assets:       {str(assets.get_balance()):<15}  {str(assets.legs.count()):<15}"
        )
        print(
            f"Expenses:     {str(expenses.get_balance()):<15}  {str(expenses.legs.count()):<15}"
        )
        print(
            f"Liabilities:  {str(liabilities.get_balance()):<15}  {str(liabilities.legs.count()):<15}"
        )
        print(
            f"Capital:      {str(capital.get_balance()):<15}  {str(capital.legs.count()):<15}"
        )


def _create_many(debit: Account, credit: Account, count: int):
    random.seed(f"{debit.full_code}-{credit.full_code}")
    transactions = []
    legs = []
    total_created = 0

    def _save():
        with db_transaction.atomic():
            Transaction.objects.bulk_create(transactions)
            Leg.objects.bulk_create(legs)
        sys.stdout.write(f"{round((total_created / count) * 100, 1)}% ")
        sys.stdout.flush()

    for _ in range(0, count):
        transaction, legs_ = _transfer_no_commit(debit, credit)
        transactions.append(transaction)
        total_created += 1
        legs += legs_
        if len(legs) >= 50000:
            _save()
            legs = []
            transactions = []

    _save()
    print("")


def _transfer_no_commit(
    debit: Account, credit: Account, amount=None
) -> tuple[Transaction, list[Leg]]:
    if not amount:
        amount = Money(round((random.random() + 0.1) * 100, 2), debit.currencies[0])

    transaction = Transaction()
    legs = []
    legs.append(Leg(transaction=transaction, account=debit, debit=amount))
    legs.append(Leg(transaction=transaction, account=credit, credit=amount))
    return transaction, legs
