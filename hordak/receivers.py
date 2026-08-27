from django.conf import settings
from django.db import connections
from django.db import transaction as db_transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from hordak import defaults
from hordak.models import Account, Leg, RunningTotal


def _threshold():
    return getattr(
        settings,
        "HORDAK_CHECKPOINT_THRESHOLD",
        defaults.CHECKPOINT_THRESHOLD,
    )


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
    if created:
        if not _threshold():
            # Checkpoints are opt-in: with no threshold configured, creating
            # legs must not cost any extra queries.
            return
        _schedule_maintenance(instance, ranges={instance.currency: instance.pk})
        return

    # Existing checkpoints for the affected accounts are stale regardless of
    # the threshold setting; drop them so reads inside this transaction fall
    # back to the full-sum path. Deleting via the queryset keeps this a
    # single DELETE per account, with no account row fetched.
    previous_account_id = getattr(instance, "_running_total_previous_account_id", None)
    affected_account_ids = {instance.account_id}
    if previous_account_id and previous_account_id != instance.account_id:
        affected_account_ids.add(previous_account_id)

    for account_id in affected_account_ids:
        deleted, _ = RunningTotal.objects.filter(account_id=account_id).delete()
        if deleted or _threshold():
            # A concurrent on-commit advance may still be building a
            # checkpoint from data that predates this change; only a fenced
            # re-invalidation after our commit can catch it. Skipped when the
            # feature is off and no checkpoints existed -- then only a
            # concurrent manual rebuild could race, and manual mode is
            # periodic-consistency by design.
            _schedule_maintenance(instance, invalidate_account_id=account_id)


@receiver(post_delete, sender=Leg)
def maintain_running_totals_on_leg_delete(sender, instance, **kwargs):
    deleted, _ = RunningTotal.objects.filter(account_id=instance.account_id).delete()
    if deleted or _threshold():
        _schedule_maintenance(instance, invalidate_account_id=instance.account_id)


def _schedule_maintenance(instance, ranges=None, invalidate_account_id=None):
    """Register (or merge into) this transaction's on-commit maintenance.

    Maintenance must not run inside the writing transaction: a checkpoint
    computed there cannot see other transactions' uncommitted legs with lower
    ids, so it would permanently exclude them -- and advance_checkpoint's
    select_for_update would be held until the outer transaction commits. One
    callback is kept per account and transaction; it is found again by
    scanning the connection's pending on-commit callbacks, so a rollback
    discards it together with the writes it belongs to.
    """
    alias = instance._state.db
    account_id = invalidate_account_id or instance.account_id
    connection = connections[alias]

    state = None
    for entry in connection.run_on_commit:
        func = entry[1]
        if getattr(func, "_hordak_checkpoint_account", None) == account_id:
            state = func._hordak_checkpoint_state
            break

    if state is None:
        state = {"invalidate": False, "currencies": {}}

        def maintain():
            _run_maintenance(alias, account_id, state)

        maintain._hordak_checkpoint_account = account_id
        maintain._hordak_checkpoint_state = state
        db_transaction.on_commit(maintain, using=alias)

    if invalidate_account_id is not None:
        state["invalidate"] = True
    if ranges:
        for currency, leg_id in ranges.items():
            id_range = state["currencies"].setdefault(currency, [leg_id, leg_id])
            id_range[0] = min(id_range[0], leg_id)
            id_range[1] = max(id_range[1], leg_id)


def _run_maintenance(alias, account_id, state):
    """Post-commit checkpoint maintenance, serialized per account.

    The select_for_update fence makes concurrent maintenance for the same
    account strictly ordered: whatever a racing advance built from data that
    predates this commit is either visible here (and removed) or starts
    after us (and sees our committed writes).
    """
    threshold = _threshold()
    with db_transaction.atomic(using=alias):
        account = (
            Account.objects.using(alias)
            .select_for_update()
            .filter(pk=account_id)
            .first()
        )
        if account is None:
            # The account was deleted after the leg change committed (e.g.
            # cascade); there is nothing left to maintain.
            return

        if state["invalidate"]:
            RunningTotal.objects.using(alias).filter(account_id=account_id).delete()
            return

        advance_needed = False
        for currency, (min_leg_id, max_leg_id) in state["currencies"].items():
            latest_included_leg_id = (
                RunningTotal.objects.using(alias)
                .filter(account_id=account_id, currency=currency)
                .order_by("-includes_leg_id")
                .values_list("includes_leg_id", flat=True)
                .first()
            )
            if latest_included_leg_id is None:
                continue

            if latest_included_leg_id >= min_leg_id:
                # A concurrent transaction advanced this checkpoint while (at
                # least) leg min_leg_id was still uncommitted, so its balance
                # cannot include that leg. Our own advance runs only below,
                # after this check, and always includes every committed leg --
                # a checkpoint at or past our lowest id here is provably
                # foreign and wrong. Drop it; reads fall back to the full sum
                # and the next threshold crossing rebuilds.
                RunningTotal.objects.using(alias).filter(
                    account_id=account_id,
                    currency=currency,
                    includes_leg_id__gte=min_leg_id,
                ).delete()
                continue

            if max_leg_id - latest_included_leg_id >= threshold:
                advance_needed = True

        if advance_needed:
            account.advance_checkpoint()
