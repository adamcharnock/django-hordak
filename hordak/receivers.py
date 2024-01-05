from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import Leg, RunningTotal


@receiver(pre_save, sender=Leg)
def update_running_totals(sender, instance, **kwargs):
    """
    Update the running total of the account associated with the leg.
    Requires running totals instance to already exist
    for given currency and account.
    """
    if instance.pk:
        # We are updating the leg, so we need to get the old amount
        old_amount = sender.objects.get(pk=instance.pk).amount
        amount_change = instance.amount - old_amount
    else:
        amount_change = instance.amount

    amount_change = instance.account.sign * amount_change
    with transaction.atomic():
        # Lock the specific running total row
        running_total, created = RunningTotal.objects.select_for_update().get_or_create(
            account=instance.account,
            currency=instance.amount.currency,
            defaults={"balance": amount_change},
        )
        if not created:
            running_total.balance += amount_change
            running_total.save()


@receiver(post_delete, sender=Leg)
def update_running_totals_on_delete(sender, instance, **kwargs):
    """Update the running total of the account associated with the leg"""
    RunningTotal.objects.filter(
        account=instance.account,
        currency=instance.amount.currency,
    ).update(balance=F("balance") - instance.account.sign * instance.amount)
