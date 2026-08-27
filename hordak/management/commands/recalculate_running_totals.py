from django.core.mail import mail_admins
from django.core.management.base import BaseCommand

from hordak.models import Account, Leg


class Command(BaseCommand):
    help = "Rebuild running total checkpoints for all accounts with legs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            default=False,
            help="Check whether running total checkpoints are correct.",
        )
        parser.add_argument(
            "--mail-admins",
            action="store_true",
            default=False,
            help="Mail admins when checkpoint problems are found during --check.",
        )
        parser.add_argument(
            "--keep-history",
            action="store_true",
            default=False,
            help="Append new checkpoints instead of replacing existing ones.",
        )

    def handle(self, *args, **options):
        accounts = Account.objects.filter(
            pk__in=Leg.objects.order_by()
            .values_list("account_id", flat=True)
            .distinct()
        )

        if options["check"]:
            problems = []
            for account in accounts.iterator():
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

            output = "\n".join(problems)
            if options["mail_admins"] and output:
                mail_admins(
                    "Running totals are incorrect",
                    f"Running totals are incorrect for some accounts\n\n{output}",
                )

            if output:
                self.stdout.write("Running totals are INCORRECT:\n\n{}".format(output))
                return

            self.stdout.write("Running totals are correct")
            return

        for account in accounts.iterator():
            account.rebuild_running_totals(keep_history=options["keep_history"])

        self.stdout.write(
            f"Rebuilt running total checkpoints for {accounts.count()} accounts."
        )
