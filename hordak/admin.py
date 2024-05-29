from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.core.cache import cache
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


def update_running_totals(modeladmin, request, queryset):
    for account in queryset:
        account.update_running_totals()


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
    readonly_fields = ("balance", "balance_sum", "income")
    raw_id_fields = ("parent",)
    search_fields = (
        "code",
        "full_code",
        "name",
    )
    list_filter = ("type",)
    actions = [update_running_totals]

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


class CachedDescriptionFilter(SimpleListFilter):
    # Cache description values to make the filter faster

    title = "description"
    parameter_name = "description"

    def lookups(self, request, model_admin):
        cached_filter_values = cache.get("transaction_description_filter_values")

        if cached_filter_values is not None:
            return [(desc, desc) for desc in cached_filter_values]

        distinct_descriptions = model_admin.model.objects.values_list(
            "description", flat=True
        ).distinct()
        cache.set(
            "transaction_description_filter_values", list(distinct_descriptions), 3600
        )  # Cache for 1 hour

        return [(desc, desc) for desc in distinct_descriptions]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(description=self.value())


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
        CachedDescriptionFilter,
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
