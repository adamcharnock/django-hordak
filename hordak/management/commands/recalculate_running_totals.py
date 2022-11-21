from django.core.mail import mail_admins
from django.core.management.base import BaseCommand

from hordak.models import Account


class Command(BaseCommand):
    help = "Recalculate running totals for all accounts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            dest="check",
            default=False,
            help="Check if the running totals are correct",
        )
        parser.add_argument(
            "--mail-admins",
            action="store_true",
            dest="mail_admins",
            default=False,
            help="Mail admins if the running totals are incorrect",
        )

    def handle(self, *args, **options):
        print("Recalculating running totals for all accounts")
        all_values_are_correct = True
        queryset = Account.objects.exclude(legs=None)
        i = 0
        print(f"Found {queryset.count()} accounts")
        for account in queryset:
            i += 1
            if i % 1000 == 0:
                print(f"Processed {i} accounts")
            value_correct = account.update_running_totals(check_only=options["check"])
            if not value_correct:
                all_values_are_correct = False

        if options["mail_admins"] and not all_values_are_correct:
            mail_admins(
                "Running totals are incorrect",
                "Running totals are incorrect for some accounts",
            )

        return 0 if all_values_are_correct else "Running totals are incorrect"
