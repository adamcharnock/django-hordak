"""Tests for migration consistency and best practices."""

from pathlib import Path

from django.test import TestCase

from scripts.check_migrations import HISTORICAL_MIGRATIONS, check_migration_file


class MigrationConsistencyTestCase(TestCase):
    """Validate migrations using the same rules as the pre-commit hook."""

    def get_migration_files(self):
        migration_dir = Path(__file__).parent.parent / "migrations"
        return [
            f
            for f in migration_dir.glob("*.py")
            if not f.name.startswith("__") and f.name not in HISTORICAL_MIGRATIONS
        ]

    def test_migrations_pass_precommit_validation(self):
        errors = []
        for migration_file in self.get_migration_files():
            errors.extend(check_migration_file(migration_file))

        self.assertFalse(
            errors,
            "Migrations failed validation:\n  {}".format("\n  ".join(errors)),
        )
