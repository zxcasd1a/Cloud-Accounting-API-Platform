from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AccountViewSet, JournalEntryViewSet, TrialBalanceAPIView, 
    IncomeStatementAPIView, BalanceSheetAPIView, CashFlowStatementAPIView,
    T12IncomeStatementAPIView, VendorViewSet, InvoiceViewSet, PurchaseOrderViewSet # Add InvoiceViewSet, PurchaseOrderViewSet
)

router = DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'journal-entries', JournalEntryViewSet)
router.register(r'vendors', VendorViewSet)
router.register(r'invoices', InvoiceViewSet) # Add this line
router.register(r'purchaseorders', PurchaseOrderViewSet, basename='purchaseorder')

urlpatterns = [
    path('', include(router.urls)),
    path('reports/trial-balance/', TrialBalanceAPIView.as_view(), name='trial-balance'), 
    path('reports/income-statement/', IncomeStatementAPIView.as_view(), name='income-statement'), 
    path('reports/balance-sheet/', BalanceSheetAPIView.as_view(), name='balance-sheet'),
    path('reports/cash-flow-statement/', CashFlowStatementAPIView.as_view(), name='cash-flow-statement'),
    path('reports/income-statement/t12/', T12IncomeStatementAPIView.as_view(), name='t12-income-statement'), # New URL for T12 Income Statement
]
