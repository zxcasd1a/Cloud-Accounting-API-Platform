from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AccountViewSet, JournalEntryViewSet, TrialBalanceAPIView # Add TrialBalanceAPIView

router = DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'journal-entries', JournalEntryViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('reports/trial-balance/', TrialBalanceAPIView.as_view(), name='trial-balance'), # New URL for Trial Balance
]
