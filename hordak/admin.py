from django.contrib import admin
from django.db.models import Prefetch, Q
from mptt.admin import MPTTModelAdmin

from hordak.models import TransactionCsvImport, TransactionCsvImportColumn

from . import models


try:  # SubquerySum is quicker, but django-sql-utils can remain as optional dependency.
    from sql_util.utils import SubquerySum as Sum

    legs_filter = Q(amount__lt=0)
except ImportError:
    from django.db.models import Sum

    legs_filter = Q(legs__amount__lt=0)


@admin.register(models.Account)
class AccountAdmin(MPTTModelAdmin):
    list_display = (
        "name",
        "code_",
        "type_",
        "currencies",
        "balance_sum",
        "income",
    )
    readonly_fields = ("balance",)
    raw_id_fields = ("parent",)
    search_fields = (
        "code",
        "full_code",
        "name",
        "userprofile__email",
        "subscribed_userprofile__email",
        "userprofile__first_name",
        "subscribed_userprofile__first_name",
        "userprofile__last_name",
        "subscribed_userprofile__last_name",
    )
    list_filter = ("type",)

    @admin.display(ordering="balance_sum")
    def balance(self, obj):
        return obj.balance()

    @admin.display(ordering="balance_sum")
    def balance_sum(self, obj):
        if obj.balance_sum:
            return -obj.balance_sum
        return "-"

    balance_sum.admin_order_field = "balance_sum"

    @admin.display(ordering="income")
    def income(self, obj):
        if obj.income:
            return -obj.income
        return "-"

    def get_queryset(self, *args, **kwargs):
        return (
            super()
            .get_queryset(*args, **kwargs)
            .annotate(
                balance_sum=Sum("legs__amount"),
                income=Sum("legs__amount", filter=legs_filter),
            )
        )

    @admin.display(ordering="full_code")
    def code_(self, obj):
        if obj.is_leaf_node():
            return obj.full_code or "-"
        return ""

    @admin.display(ordering="type")
    def type_(self, obj):
        if obj.type:
            return models.Account.TYPES[obj.type]
        return "-"


class LegInline(admin.TabularInline):
    model = models.Leg
    raw_id_fields = ("account",)
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
        "date",
        "description",
    ]
    list_filter = [
        "description",
    ]
    readonly_fields = ("timestamp",)
    search_fields = ("legs__account__name",)
    inlines = [LegInline]

    def debited_accounts(self, obj):
        return ", ".join([str(leg.account.name) for leg in obj.debit_legs]) or None

    def total_amount(self, obj):
        return obj.total_amount

    def credited_accounts(self, obj):
        return ", ".join([str(leg.account.name) for leg in obj.credit_legs]) or None

    def get_queryset(self, *args, **kwargs):
        return (
            super()
            .get_queryset(*args, **kwargs)
            .prefetch_related(
                Prefetch(
                    "legs",
                    queryset=models.Leg.objects.filter(amount__gt=0).select_related(
                        "account"
                    ),
                    to_attr="debit_legs",
                ),
                Prefetch(
                    "legs",
                    queryset=models.Leg.objects.filter(amount__lt=0).select_related(
                        "account"
                    ),
                    to_attr="credit_legs",
                ),
            )
            .annotate(
                total_amount=Sum("legs__amount", filter=legs_filter),
            )
        )


@admin.register(models.Leg)
class LegAdmin(admin.ModelAdmin):
    list_display = ["id", "uuid", "transaction", "account", "amount", "description"]
    search_fields = (
        "account__name",
        "account__id",
        "description",
    )
    raw_id_fields = (
        "account",
        "transaction",
    )
    list_filter = (
        "account__type",
        "transaction__description",
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
