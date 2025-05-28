from django.contrib import admin
from .models import Account, JournalEntry, Transaction, PurchaseOrder, PurchaseOrderLineItem

# Register your models here.
admin.site.register(Account)
admin.site.register(JournalEntry)
admin.site.register(Transaction)

# Admin class for PurchaseOrderLineItem (Inline)
class PurchaseOrderLineItemInline(admin.TabularInline):
    model = PurchaseOrderLineItem
    extra = 1  # Show one empty extra line item form by default
    fields = ('item_description', 'quantity', 'unit_price', 'total_price', 'product_or_service_code', 'account', 'department_code')
    readonly_fields = ('total_price',)

# Admin class for PurchaseOrder
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'vendor', 'order_date', 'status', 'total_amount', 'created_at')
    list_filter = ('status', 'order_date', 'vendor')
    search_fields = ('po_number', 'vendor__name')
    inlines = [PurchaseOrderLineItemInline]
    readonly_fields = ('created_at', 'updated_at', 'total_amount')
    
    # Optional: If you want to make 'status' read-only in the form as well, add it here.
    # For now, it remains editable in the admin form unless added to readonly_fields.

# Register PurchaseOrder with its custom admin class
admin.site.register(PurchaseOrder, PurchaseOrderAdmin)

# It's generally not necessary to register PurchaseOrderLineItem separately
# if it's only managed as an inline, so we won't register it directly.
