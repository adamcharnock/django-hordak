from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hordak", "0040_merge_alter_account_name_runningtotal_checkpoint"),
    ]

    operations = [
        migrations.AlterField(
            model_name="runningtotal",
            name="id",
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
    ]
