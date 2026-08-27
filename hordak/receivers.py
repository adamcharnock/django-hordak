from django.conf import settings
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from hordak import defaults
from hordak.models import Account, Leg


@receiver(pre_save, sender=Leg)
def remember_leg_account_before_save(sender, instance, **kwargs):
    if instance.pk is None:
        instance._running_total_previous_account_id = None
        return

    instance._running_total_previous_account_id = (
        Leg.objects.filter(pk=instance.pk).values_list("account_id", flat=True).first()
    )


@receiver(post_save, sender=Leg)
def maintain_running_totals_on_leg_save(sender, instance, created, **kwargs):
    account = Account.objects.get(pk=instance.account_id)
    previous_account_id = getattr(instance, "_running_total_previous_account_id", None)

    if not created:
        if previous_account_id and previous_account_id != instance.account_id:
            previous_account = Account.objects.filter(pk=previous_account_id).first()
            if previous_account is not None:
                previous_account.invalidate_running_totals()
        account.invalidate_running_totals()
        return

    threshold = getattr(
        settings,
        "HORDAK_CHECKPOINT_THRESHOLD",
        defaults.CHECKPOINT_THRESHOLD,
    )
    if not threshold:
        return

    latest_included_leg_id = (
        account.running_totals.filter(currency=instance.currency)
        .order_by("-includes_leg_id")
        .values_list("includes_leg_id", flat=True)
        .first()
    )
    if latest_included_leg_id is None:
        return

    if instance.pk - latest_included_leg_id >= threshold:
        account.advance_checkpoint()


@receiver(post_delete, sender=Leg)
def maintain_running_totals_on_leg_delete(sender, instance, **kwargs):
    account = Account.objects.filter(pk=instance.account_id).first()
    if account is not None:
        account.invalidate_running_totals()
