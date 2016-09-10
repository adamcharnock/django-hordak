from django.contrib import admin

from mptt.admin import MPTTModelAdmin

from . import models


@admin.register(models.Account)
class AccountAdmin(MPTTModelAdmin):
    list_display = ('name', 'full_code', 'type')

    def full_code(self, obj):
        if obj.is_leaf_node():
            return obj.full_code
        else:
            return ''


@admin.register(models.Transaction)
class TransactionAdmin(admin.ModelAdmin):
    readonly_fields = ('timestamp',)


@admin.register(models.Leg)
class LegAdmin(admin.ModelAdmin):
    pass


@admin.register(models.StatementImport)
class StatementImportAdmin(admin.ModelAdmin):
    readonly_fields = ('timestamp',)


@admin.register(models.StatementLine)
class StatementLineAdmin(admin.ModelAdmin):
    readonly_fields = ('timestamp',)
