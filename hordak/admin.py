from django.contrib import admin
from django.db import transaction as db_transaction
from django import forms
from django.db.models import Sum

from mptt.admin import MPTTModelAdmin

from hordak.models import TransactionCsvImportColumn, TransactionCsvImport
from . import models


@admin.register(models.Account)
class AccountAdmin(MPTTModelAdmin):
    list_display = ("name", "code_", "type_", "balance")

    def code_(self, obj):
        if obj.is_leaf_node():
            return obj.full_code or "-"
        else:
            return ""

    def type_(self, obj):
        return models.Account.TYPES[obj.type]


class LegInline(admin.TabularInline):
    model = models.Leg


@admin.register(models.Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "timestamp",
        "debited_accounts",
        "total_amount",
        "credited_accounts",
        "uuid",
    ]
    readonly_fields = ("timestamp",)
    inlines = [LegInline]

    def debited_accounts(self, obj):
        return ", ".join([str(leg.account) for leg in obj.legs.debits()]) or None

    def credited_accounts(self, obj):
        return ", ".join([str(leg.account) for leg in obj.legs.credits()]) or None

    def total_amount(self, obj):
        return obj.legs.debits().aggregate(Sum("amount"))["amount__sum"]


@admin.register(models.Leg)
class LegAdmin(admin.ModelAdmin):
    pass


@admin.register(models.StatementImport)
class StatementImportAdmin(admin.ModelAdmin):
    readonly_fields = ("timestamp",)


@admin.register(models.StatementLine)
class StatementLineAdmin(admin.ModelAdmin):
    readonly_fields = ("timestamp",)


class TransactionImportColumnInline(admin.TabularInline):
    model = TransactionCsvImportColumn


@admin.register(TransactionCsvImport)
class TaskMetaAdmin(admin.ModelAdmin):
    list_display = ["id", "uuid", "state", "timestamp", "has_headings"]
    inlines = [TransactionImportColumnInline]
