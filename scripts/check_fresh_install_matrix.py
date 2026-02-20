#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

SCENARIOS = [
    {
        "name": "baseline",
        "db_name": "fresh_install_base",
        "HORDAK_MAX_DIGITS": "20",
        "HORDAK_DECIMAL_PLACES": "2",
        "HORDAK_INTERNAL_CURRENCY": "EUR",
        "DEFAULT_CURRENCY": "GBP",
        "HORDAK_CURRENCIES_JSON": '["GBP","USD","EUR"]',
        "CURRENCIES_JSON": '["EUR","USD","GBP"]',
    },
    {
        "name": "high_precision",
        "db_name": "fresh_install_precision",
        "HORDAK_MAX_DIGITS": "28",
        "HORDAK_DECIMAL_PLACES": "6",
        "HORDAK_INTERNAL_CURRENCY": "EUR",
        "DEFAULT_CURRENCY": "GBP",
        "HORDAK_CURRENCIES_JSON": '["GBP","USD","EUR"]',
        "CURRENCIES_JSON": '["EUR","USD","GBP"]',
    },
    {
        "name": "currency_override",
        "db_name": "fresh_install_currency",
        "HORDAK_MAX_DIGITS": "20",
        "HORDAK_DECIMAL_PLACES": "2",
        "HORDAK_INTERNAL_CURRENCY": "USD",
        "DEFAULT_CURRENCY": "USD",
        "HORDAK_CURRENCIES_JSON": '["USD","EUR"]',
        "CURRENCIES_JSON": '["USD","EUR"]',
    },
    {
        "name": "combined_custom",
        "db_name": "fresh_install_combined",
        "HORDAK_MAX_DIGITS": "24",
        "HORDAK_DECIMAL_PLACES": "4",
        "HORDAK_INTERNAL_CURRENCY": "GBP",
        "DEFAULT_CURRENCY": "GBP",
        "HORDAK_CURRENCIES_JSON": '["GBP","EUR","USD"]',
        "CURRENCIES_JSON": '["GBP","EUR","USD"]',
    },
]


def run(command, env=None):
    subprocess.run(command, check=True, env=env)


def main():
    repo_root = Path(__file__).resolve().parents[1]
    os.chdir(repo_root)

    settings_ci = repo_root / "example_project" / "settings_ci.py"
    settings_ci.write_text(
        "\n".join(
            [
                "from .settings import *  # noqa",
                "import json",
                "import os",
                "",
                'if os.getenv("HORDAK_MAX_DIGITS"):',
                '    HORDAK_MAX_DIGITS = int(os.environ["HORDAK_MAX_DIGITS"])',
                'if os.getenv("HORDAK_DECIMAL_PLACES"):',
                '    HORDAK_DECIMAL_PLACES = int(os.environ["HORDAK_DECIMAL_PLACES"])',
                'if os.getenv("HORDAK_INTERNAL_CURRENCY"):',
                '    HORDAK_INTERNAL_CURRENCY = os.environ["HORDAK_INTERNAL_CURRENCY"]',
                'if os.getenv("DEFAULT_CURRENCY"):',
                '    DEFAULT_CURRENCY = os.environ["DEFAULT_CURRENCY"]',
                'if os.getenv("HORDAK_CURRENCIES_JSON"):',
                '    HORDAK_CURRENCIES = json.loads(os.environ["HORDAK_CURRENCIES_JSON"])',
                'if os.getenv("CURRENCIES_JSON"):',
                '    CURRENCIES = json.loads(os.environ["CURRENCIES_JSON"])',
                "",
            ]
        )
    )

    pg_host = os.getenv("HORDAK_CI_PG_HOST", "localhost")
    pg_user = os.getenv("HORDAK_CI_PG_USER", "postgres")
    pg_password = os.getenv("HORDAK_CI_PG_PASSWORD", "postgres")

    base_env = os.environ.copy()
    base_env["PYTHONPATH"] = str(repo_root)
    base_env["DJANGO_SETTINGS_MODULE"] = "example_project.settings_ci"
    base_env["PGPASSWORD"] = pg_password

    for scenario in SCENARIOS:
        print("=== Fresh install scenario: {} ===".format(scenario["name"]))
        db_name = scenario["db_name"]
        database_url = "postgresql://{}:{}@{}/{}".format(
            pg_user,
            pg_password,
            pg_host,
            db_name,
        )

        run(
            [
                "psql",
                "-h",
                pg_host,
                "-U",
                pg_user,
                "-c",
                "DROP DATABASE IF EXISTS {}".format(db_name),
            ],
            env=base_env,
        )
        run(
            [
                "psql",
                "-h",
                pg_host,
                "-U",
                pg_user,
                "-c",
                "CREATE DATABASE {}".format(db_name),
            ],
            env=base_env,
        )

        scenario_env = base_env.copy()
        scenario_env.update(scenario)
        scenario_env["DATABASE_URL"] = database_url

        run(["./manage.py", "migrate", "--run-syncdb"], env=scenario_env)
        run(
            ["./manage.py", "makemigrations", "--check", "--dry-run", "hordak"],
            env=scenario_env,
        )


if __name__ == "__main__":
    main()
