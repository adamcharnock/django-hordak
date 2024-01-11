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

    def handle(self, *args, **options):
        print(
            f"{'Checking' if options['check'] else 'Recalculating'} running totals for all accounts"
        )
        output_string = ""
        # We are using Legs subquery because it is quicker
        queryset = Account.objects.filter(pk__in=Leg.objects.values("account"))
        i = 0
        print(f"Found {queryset.count()} accounts")
        for account in queryset.all():
            i += 1
            if i % 100 == 0:
                print(f"Processed {i} accounts")
            faulty_values = account.update_running_totals(check_only=options["check"])
            if faulty_values:
                for currency, rt_value, correct_value in faulty_values:
                    output_string += f"Account {account.name} has faulty running total for {currency}"
                    output_string += f" (should be {correct_value}, is {rt_value})\n"

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
