from django.db import migrations, models
from django.db.models import Max
from django.utils import timezone


def backfill_runningtotal_checkpoint(apps, schema_editor):
    RunningTotal = apps.get_model("hordak", "RunningTotal")
    Leg = apps.get_model("hordak", "Leg")
    now = timezone.now()
    for rt in RunningTotal.objects.all().iterator():
        max_id = Leg.objects.filter(account_id=rt.account_id).aggregate(m=Max("id"))[
            "m"
        ]
        rt.includes_leg_id = max_id if max_id is not None else 0
        rt.created_at = now
        rt.save(update_fields=["includes_leg_id", "created_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("hordak", "0038_merge_0035_runningtotal_0037_auto_20230516_0142"),
    ]

    operations = [
        migrations.AddField(
            model_name="runningtotal",
            name="includes_leg_id",
            field=models.BigIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="runningtotal",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.RunPython(
            backfill_runningtotal_checkpoint,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="runningtotal",
            name="includes_leg_id",
            field=models.BigIntegerField(),
        ),
        migrations.AlterField(
            model_name="runningtotal",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AddIndex(
            model_name="runningtotal",
            index=models.Index(
                fields=["account", "currency", "-includes_leg_id"],
                name="hordak_runtot_acc_cur_ilid",
            ),
        ),
    ]
