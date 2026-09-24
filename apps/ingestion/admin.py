from django.contrib import admin
from .models import ProcuringEntity, Vendor, Contract, RawRecord


@admin.register(ProcuringEntity)
class ProcuringEntityAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'state', 'created_at')
    search_fields = ('name',)
    list_filter = ('type', 'state')


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'cac_number', 'state', 'created_at')
    search_fields = ('name', 'cac_number')
    list_filter = ('state',)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('title', 'entity', 'vendor', 'amount', 'award_date', 'nocopo_id')
    search_fields = ('title', 'nocopo_id')
    list_filter = ('method', 'category', 'currency')
    raw_id_fields = ('entity', 'vendor')


@admin.register(RawRecord)
class RawRecordAdmin(admin.ModelAdmin):
    list_display = ('raw_id', 'source_file', 'is_validated', 'is_imported', 'created_at')
    list_filter = ('is_validated', 'is_imported')
