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
    readonly_fields = (
        "balance",
    )
    raw_id_fields = (
        'parent',
    )
    search_fields = (
        'code',
        'full_code',
        'name',
    )
    list_filter = (
        'type',
    )

    def balance(self, obj):
        return obj.balance()
    balance.admin_order_field = "balance_sum"

    def get_queryset(self, *args, **kwargs):
        return super().get_queryset(*args, **kwargs).annotate(balance_sum=Sum('legs__amount'))

    def code_(self, obj):
        if obj.is_leaf_node():
            return obj.full_code or "-"
        else:
            return ""
    code_.admin_order_field = "full_code"

    def type_(self, obj):
        return models.Account.TYPES[obj.type]
    type_.admin_order_field = "type"


class LegInline(admin.TabularInline):
    model = models.Leg
    raw_id_fields = (
        "account",
    )
    extra = 0


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
    search_fields = (
        "legs__account__name",
    )
    inlines = [LegInline]

    def debited_accounts(self, obj):
        return ", ".join([str(leg.account) for leg in obj.legs.debits()]) or None

    def credited_accounts(self, obj):
        return ", ".join([str(leg.account) for leg in obj.legs.credits()]) or None

    def total_amount(self, obj):
        return obj.legs.debits().aggregate(Sum("amount"))["amount__sum"]


@admin.register(models.Leg)
class LegAdmin(admin.ModelAdmin):
    list_display = ['id', 'uuid', 'transaction', 'account', 'amount', 'description']
    search_fields = (
        "account__name",
        "account__id",
        "description",
    )
    raw_id_fields = (
        "account",
        'transaction',
    )


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
