from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from hordak.models import Account, Leg


@receiver(post_save, sender=Leg)
def recompute_running_totals_on_leg_update(sender, instance, created, **kwargs):
    if created:
        return
    Account.objects.get(pk=instance.account_id).rebuild_running_totals()


@receiver(post_delete, sender=Leg)
def recompute_running_totals_on_leg_delete(sender, instance, **kwargs):
    Account.objects.get(pk=instance.account_id).rebuild_running_totals()
