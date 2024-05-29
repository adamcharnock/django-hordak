# Generated by Django 4.0.7 on 2022-09-18 10:33

from django.db import migrations

# WHY DOES THIS MIGRATION EXIST?
# Postgres seems to need this function/trigger to be recreated
# following the migration to bigint IDs.
# Otherwise we get the error:
#      django.db.utils.ProgrammingError: type of parameter 14 (bigint) does not match that when preparing the plan (integer)


def create_trigger(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
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
        """
        )

    elif schema_editor.connection.vendor == "mysql":
        # we have to call this procedure in Leg.on_commit, because MySQL does not support deferred triggers
        pass
    else:
        raise NotImplementedError(
            "Database vendor %s not supported" % schema_editor.connection.vendor
        )


def drop_trigger(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP FUNCTION check_account_type() CASCADE")
        # Recreate check_account_type as it was in migration 0016
        schema_editor.execute(
            """
            CREATE OR REPLACE FUNCTION check_account_type()
                RETURNS TRIGGER AS
            $$
            BEGIN
                IF NEW.parent_id::BOOL THEN
                    NEW.type = (SELECT type FROM hordak_account WHERE id = NEW.parent_id);
                END IF;
                RETURN NEW;
            END;
            $$
            LANGUAGE plpgsql;
        """
        )
        schema_editor.execute(
            """
            CREATE TRIGGER check_account_type_trigger
            BEFORE INSERT OR UPDATE ON hordak_account
            FOR EACH ROW
            WHEN (pg_trigger_depth() = 0)
            EXECUTE PROCEDURE check_account_type();
        """
        )
    elif schema_editor.connection.vendor == "mysql":
        pass
    else:
        raise NotImplementedError(
            "Database vendor %s not supported" % schema_editor.connection.vendor
        )


class Migration(migrations.Migration):
    dependencies = (("hordak", "0038_alter_account_id_alter_leg_id_and_more"),)
    atomic = False

    operations = [
        migrations.RunPython(create_trigger, reverse_code=drop_trigger),
    ]
