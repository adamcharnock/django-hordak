from django.core.mail import mail_admins
from django.core.management.base import BaseCommand

from hordak.models import Account, Leg


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
        parser.add_argument(
            "--keep-history",
            action="store_true",
            dest="keep_history",
            default=False,
            help="Append new checkpoint rows instead of replacing existing ones",
        )

    def handle(self, *args, **options):
        # We are using Legs subquery because it is quicker
        queryset = Account.objects.filter(pk__in=Leg.objects.values("account"))
        if options["check"]:
            problems = []
            for account in queryset.all():
                for (
                    currency,
                    effective_value,
                    correct_value,
                ) in account.check_running_totals():
                    if effective_value is None:
                        problems.append(
                            f"Account {account.name} has no checkpoint for {currency} "
                            f"(should be {correct_value})"
                        )
                        continue

                    problems.append(
                        f"Account {account.name} has faulty running total for {currency} "
                        f"(effective {effective_value}, should be {correct_value})"
                    )

            output_string = "\n".join(problems)
            if options["mail_admins"] and output_string:
                mail_admins(
                    "Running totals are incorrect",
                    f"Running totals are incorrect for some accounts\n\n{output_string}",
                )

            return (
                f"Running totals are INCORRECT: \n\n{output_string}"
                if output_string
                else "Running totals are correct"
            )

        for account in queryset.all():
            account.rebuild_running_totals(keep_history=options["keep_history"])

        return f"Rebuilt running total checkpoints for {queryset.count()} accounts."
