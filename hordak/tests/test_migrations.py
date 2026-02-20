"""Tests for migration consistency and best practices."""

import re
from pathlib import Path

from django.test import TestCase

HISTORICAL_MIGRATIONS = {
    "0001_initial.py",
    "0004_auto_20161113_1932.py",
    "0025_auto_20180829_1605.py",
    "0026_auto_20190723_0929.py",
}


class MigrationConsistencyTestCase(TestCase):
    """Test that migrations follow best practices and use variables instead of hardcoded values."""

    def get_migration_files(self):
        """Get all migration files."""
        migration_dir = Path(__file__).parent.parent / "migrations"
        return [
            f
            for f in migration_dir.glob("*.py")
            if not f.name.startswith("__") and f.name not in HISTORICAL_MIGRATIONS
        ]

    def test_migrations_use_max_digits_variable(self):
        """Check that migrations use MAX_DIGITS variable instead of hardcoded values."""
        errors = []

        for migration_file in self.get_migration_files():
            with open(migration_file) as f:
                content = f.read()

            # Skip files that don't have max_digits
            if "max_digits" not in content:
                continue

            # Check if using hardcoded max_digits values
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                # Look for max_digits=<number> pattern
                match = re.search(r"max_digits\s*=\s*(\d+)", line)
                if match:
                    # Check if it's using the variable MAX_DIGITS
                    if "MAX_DIGITS" in line:
                        continue  # Using variable, OK

                    # Check if MAX_DIGITS is imported
                    if (
                        "from hordak.defaults import" in content
                        and "MAX_DIGITS" in content
                    ):
                        # Has import but still using hardcoded value
                        msg = "{}:{}: Hardcoded max_digits={} found. Should use MAX_DIGITS variable.".format(
                            migration_file.name, i, match.group(1)
                        )
                        errors.append(msg)

        if errors:
            self.fail(
                "Migrations with hardcoded max_digits values:\n  "
                + "\n  ".join(errors)
                + "\n\nMigrations should use MAX_DIGITS from hordak.defaults"
            )

    def test_migrations_use_decimal_places_variable(self):
        """Check that migrations use DECIMAL_PLACES variable instead of hardcoded values."""
        errors = []

        for migration_file in self.get_migration_files():
            with open(migration_file) as f:
                content = f.read()

            # Skip files that don't have decimal_places
            if "decimal_places" not in content:
                continue

            # Skip if correctly imports DECIMAL_PLACES
            if "from hordak.defaults import" in content and "DECIMAL_PLACES" in content:
                # Check that it's actually used, not just imported
                if re.search(r"decimal_places\s*=\s*\d+", content):
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        match = re.search(r"decimal_places\s*=\s*(\d+)", line)
                        if match and "DECIMAL_PLACES" not in line:
                            msg = "{}:{}: Hardcoded decimal_places={} found.".format(
                                migration_file.name, i, match.group(1)
                            )
                            errors.append(msg)

        if errors:
            self.fail(
                "Migrations with hardcoded decimal_places values:\n  "
                + "\n  ".join(errors)
                + "\n\nMigrations should use DECIMAL_PLACES from hordak.defaults"
            )

    def test_migrations_use_get_internal_currency(self):
        """Check that migrations use get_internal_currency instead of hardcoded currency."""
        errors = []

        for migration_file in self.get_migration_files():
            with open(migration_file) as f:
                content = f.read()

            # Look for default_currency="<CURRENCY>" pattern
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                match = re.search(r'default_currency\s*=\s*["\']([A-Z]{3})["\']', line)
                if match:
                    # Check if using get_internal_currency
                    if "get_internal_currency" not in content:
                        msg = (
                            '{}:{}: Hardcoded default_currency="{}" found. '
                            "Should use hordak.defaults.get_internal_currency"
                        ).format(migration_file.name, i, match.group(1))
                        errors.append(msg)

        if errors:
            self.fail(
                "Migrations with hardcoded default_currency:\n  "
                + "\n  ".join(errors)
                + "\n\nMigrations should use hordak.defaults.get_internal_currency"
            )

    def test_migrations_use_get_currency_choices(self):
        """Check that migrations use get_currency_choices() instead of hardcoded choices."""
        errors = []

        for migration_file in self.get_migration_files():
            with open(migration_file) as f:
                content = f.read()

            # Look for large hardcoded choices arrays (likely currencies)
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if "choices=[" in line or "choices = [" in line:
                    # Count currency-like tuples in next 50 lines
                    tuple_count = 0
                    for j in range(i, min(i + 50, len(lines))):
                        if re.search(r'\("[A-Z]{3}",\s*"', lines[j]):
                            tuple_count += 1

                    if tuple_count > 50:  # Likely hardcoded currency list
                        # Check if using get_currency_choices
                        if "get_currency_choices" not in content:
                            msg = (
                                "{}:{}: Large hardcoded choices array detected "
                                "({} currencies). Should use "
                                "hordak.models.core.get_currency_choices()"
                            ).format(migration_file.name, i, tuple_count)
                            errors.append(msg)

        if errors:
            self.fail(
                "Migrations with hardcoded currency choices:\n  "
                + "\n  ".join(errors)
                + "\n\nMigrations should use hordak.models.core.get_currency_choices()"
            )

    def test_migration_imports_match_usage(self):
        """Check that migrations import the variables they use."""
        errors = []

        for migration_file in self.get_migration_files():
            with open(migration_file) as f:
                content = f.read()

            uses_max_digits = "max_digits=MAX_DIGITS" in content
            uses_decimal_places = "decimal_places=DECIMAL_PLACES" in content
            uses_get_internal_currency = "get_internal_currency" in content
            uses_get_currency_choices = "get_currency_choices()" in content

            has_defaults_import = "from hordak.defaults import" in content
            has_hordak_defaults = "import hordak.defaults" in content
            has_models_core = "import hordak.models.core" in content

            if (uses_max_digits or uses_decimal_places) and not has_defaults_import:
                errors.append(
                    f"{migration_file.name}: "
                    f"Uses MAX_DIGITS or DECIMAL_PLACES but doesn't import from hordak.defaults"
                )

            if uses_get_internal_currency and not (
                has_defaults_import or has_hordak_defaults
            ):
                errors.append(
                    f"{migration_file.name}: "
                    f"Uses get_internal_currency but doesn't import hordak.defaults"
                )

            if uses_get_currency_choices and not has_models_core:
                errors.append(
                    f"{migration_file.name}: "
                    f"Uses get_currency_choices() but doesn't import hordak.models.core"
                )

        if errors:
            self.fail("Migrations with missing imports:\n  " + "\n  ".join(errors))
