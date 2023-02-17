# Generated by Django 4.0.7 on 2022-09-18 10:33

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("hordak", "0031_alter_account_currencies"),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE OR REPLACE FUNCTION check_account_type()
                RETURNS TRIGGER AS
            $$
            BEGIN
                IF NEW.parent_id::INT::BOOL THEN
                    NEW.type = (SELECT type FROM hordak_account WHERE id = NEW.parent_id);
                END IF;
                RETURN NEW;
            END;
            $$
            LANGUAGE plpgsql;
            """,
            "DROP FUNCTION check_account_type()",
        ),
    ]
