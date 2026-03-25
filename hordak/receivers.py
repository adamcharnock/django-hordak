from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from hordak import defaults
from hordak.models import Account, Leg


@receiver(post_save, sender=Leg)
def recompute_running_totals_on_leg_save(sender, instance, created, **kwargs):
    if not created:
        Account.objects.get(pk=instance.account_id).rebuild_running_totals()
        return

    threshold = defaults.CHECKPOINT_THRESHOLD
    if not threshold:
        return

    account = Account.objects.get(pk=instance.account_id)
    latest = (
        account.running_totals.filter(currency=instance.amount_currency)
        .order_by("-includes_leg_id")
        .values_list("includes_leg_id", flat=True)
        .first()
    )
    if latest is None:
        return
    if instance.pk - latest >= threshold:
        account.advance_checkpoint()


@receiver(post_delete, sender=Leg)
def recompute_running_totals_on_leg_delete(sender, instance, **kwargs):
    Account.objects.get(pk=instance.account_id).rebuild_running_totals()
