from unittest import skip

from django.db import connection


def _id(obj):
    return obj


def postgres_only(reason="Test is postgresql-specific"):
    if not connection.vendor == "postgresql":
        return skip(reason)
    return _id


def mysql_only(reason="Test is postgresql-specific"):
    if not connection.vendor == "mysql":
        return skip(reason)
    return _id
