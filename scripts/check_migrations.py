#!/usr/bin/env python3
"""Pre-commit hook to check Django migrations for hardcoded values.

This script ensures migrations use variable references from hordak.defaults
instead of hardcoded values like max_digits=20, default_currency="EUR", etc.
"""

import re
import sys
from pathlib import Path

HISTORICAL_MIGRATIONS = {
    "0001_initial.py",
    "0004_auto_20161113_1932.py",
    "0025_auto_20180829_1605.py",
    "0026_auto_20190723_0929.py",
}


def check_migration_file(filepath):
    """Check a single migration file for common hardcoding issues."""
    errors = []

    with open(filepath, "r") as f:
        content = f.read()
        lines = content.split("\n")

    # Skip if this is __init__.py or not a Python file
    if filepath.name == "__init__.py" or not filepath.name.endswith(".py"):
        return errors

    # Skip historical migrations that predate this validation (before issue #138 fix)
    # These migrations are already deployed and shouldn't be modified
    if filepath.name in HISTORICAL_MIGRATIONS:
        return errors

    # Check 1: Hardcoded max_digits values (should use MAX_DIGITS variable)
    # Allow max_digits in migrations that import MAX_DIGITS and use it
    has_max_digits_import = (
        "from hordak.defaults import" in content and "MAX_DIGITS" in content
    )

    for i, line in enumerate(lines, 1):
        # Check for hardcoded max_digits=<number>
        if re.search(r"max_digits\s*=\s*\d+", line):
            # Allow if MAX_DIGITS is used
            if "max_digits=MAX_DIGITS" not in line and "MAX_DIGITS" in line:
                continue  # Using the variable, OK
            elif "max_digits=MAX_DIGITS" in line:
                continue  # Using the variable, OK
            elif not has_max_digits_import:
                msg = (
                    "{}:{}: Hardcoded max_digits value found. "
                    "Use MAX_DIGITS from hordak.defaults instead.\n  {}"
                ).format(filepath.name, i, line.strip())
                errors.append(msg)

        # Check 2: Hardcoded default_currency="EUR" or similar
        if re.search(r'default_currency\s*=\s*["\']', line):
            # Allow if using get_internal_currency
            if "get_internal_currency" not in content:
                msg = (
                    "{}:{}: Hardcoded default_currency found. "
                    "Use hordak.defaults.get_internal_currency instead.\n  {}"
                ).format(filepath.name, i, line.strip())
                errors.append(msg)

        # Check 3: Large hardcoded choices arrays (likely currency choices)
        # Look for patterns like choices=[ with many tuples
        if "choices=[" in line or "choices = [" in line:
            # Count tuple-like patterns in the next 50 lines
            tuple_count = 0
            for j in range(i, min(i + 50, len(lines))):
                if re.search(r'\("[\w]{3}",\s*"', lines[j]):
                    tuple_count += 1

            if tuple_count > 50:  # Likely hardcoded currency list
                msg = (
                    "{}:{}: Large hardcoded choices array detected "
                    "(likely currencies). "
                    "Use hordak.models.core.get_currency_choices() instead."
                ).format(filepath.name, i)
                errors.append(msg)

    # Check 4: Ensure migrations that use MAX_DIGITS/DECIMAL_PLACES actually import them
    uses_max_digits = "max_digits=MAX_DIGITS" in content
    uses_decimal_places = "decimal_places=DECIMAL_PLACES" in content

    has_imports = "from hordak.defaults import" in content

    if (uses_max_digits or uses_decimal_places) and not has_imports:
        errors.append(
            f"{filepath.name}: Uses MAX_DIGITS or DECIMAL_PLACES but doesn't import from hordak.defaults"
        )

    return errors


def main():
    """Check all provided migration files."""
    if len(sys.argv) < 2:
        print("Usage: check_migrations.py <migration_file> [<migration_file> ...]")
        return 0

    all_errors = []

    for filepath_str in sys.argv[1:]:
        filepath = Path(filepath_str)

        # Only check migration files
        if "migrations" not in filepath.parts:
            continue

        errors = check_migration_file(filepath)
        all_errors.extend(errors)

    if all_errors:
        print("❌ Migration validation failed:\n")
        for error in all_errors:
            print(f"  {error}\n")
        print("\nMigration Best Practices:")
        print("  ✅ Use 'from hordak.defaults import MAX_DIGITS, DECIMAL_PLACES'")
        print("  ✅ Use 'max_digits=MAX_DIGITS' not 'max_digits=20'")
        print(
            "  ✅ Use 'default_currency=hordak.defaults.get_internal_currency' not 'default_currency=\"EUR\"'"
        )
        print(
            "  ✅ Use 'choices=hordak.models.core.get_currency_choices()' not hardcoded currency lists"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
