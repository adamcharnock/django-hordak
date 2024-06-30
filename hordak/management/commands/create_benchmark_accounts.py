# flake8: noqa
import random
import sys
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import connection
from django.db import transaction as db_transaction
from moneyed import Money

from hordak.models import Account, Leg, Transaction


class Command(BaseCommand):
    help = (
        "Create accounts for benchmarking against. "
        "Expects `./manage.py create_chart_of_accounts` to be run first."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            default=False,
            help="Delete all existing benchmark accounts from database",
        )
        parser.add_argument(
            "--multiplier",
            type=int,
            default=10_000,
            help="Scale up how many accounts we create",
        )

    def handle(self, *args, **options):
        m = options["multiplier"]

        bank: Account = Account.objects.get(name="Bank")
        assets: Account = Account.objects.get(name="Fixed")
        expenses: Account = Account.objects.get(name="Direct")
        income: Account = Account.objects.get(name="Income")
        liabilities: Account = Account.objects.get(name="Non-Current")
        capital: Account = Account.objects.get(name="Capital - Ordinary Shares")

        customer_income = Account.objects.create(name="Customer Income", parent=income)
        customer_liabilities = Account.objects.create(
            name="Customer Liabilities", parent=income
        )

        if options["clear"]:
            print("Deleting existing benchmark accounts...")
            with connection.cursor():
                Account.objects.filter(parent=customer_income).delete()
                Account.objects.filter(parent=customer_liabilities).delete()

        print("Creating: Customer income accounts...")
        _create_many(customer_income, "Customer Sales", count=m)

        print("Creating: Customer liability accounts...")
        _create_many(customer_liabilities, "Customer Liabilities", count=m)

        print("Rebuilding tree...")
        Account.objects.rebuild()

        print("Done")
        print("")

        print(f"Total accounts: {str(Account.objects.count())}")


def _create_many(parent: Optional[Account], name, count: int):
    accounts = []
    total_created = 0

    def _save():
        with db_transaction.atomic():
            Account.objects.bulk_create(accounts)
        sys.stdout.write(f"{round((total_created / count) * 100, 1)}% ")
        sys.stdout.flush()

    for _ in range(0, count):
        account = Account(parent=parent, name=f"{name} {total_created+1}")
        account.lft = 0
        account.rght = 0
        account.tree_id = 0
        account.level = 0
        accounts.append(account)
        total_created += 1
        if len(accounts) >= 50000:
            _save()
            accounts = []

    _save()
    print("")
