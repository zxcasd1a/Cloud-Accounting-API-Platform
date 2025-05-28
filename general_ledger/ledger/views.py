from rest_framework import viewsets
from rest_framework.views import APIView # Add APIView
from rest_framework.response import Response # Add Response
from django.db.models import Sum, Q # Add Sum and Q
from decimal import Decimal # Add Decimal
from .models import Account, JournalEntry, Transaction
from .serializers import AccountSerializer, JournalEntrySerializer, TrialBalanceReportSerializer, TrialBalanceAccountSerializer # Add TrialBalance serializers
from django.utils.dateparse import parse_date # For parsing date parameters

class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = JournalEntry.objects.all()
    serializer_class = JournalEntrySerializer

class TrialBalanceAPIView(APIView):
    def get(self, request):
        as_of_date_str = request.query_params.get('as_of_date')
        as_of_date = None
        if as_of_date_str:
            as_of_date = parse_date(as_of_date_str)

        accounts_data = []
        overall_total_debits = Decimal('0.00')
        overall_total_credits = Decimal('0.00')

        accounts = Account.objects.all().order_by('account_code')

        for account in accounts:
            # Filter transactions by status 'POSTED' and optionally by date
            transaction_filters = Q(journal_entry__status='POSTED', account=account)
            if as_of_date:
                transaction_filters &= Q(journal_entry__entry_date__lte=as_of_date)

            account_transactions = Transaction.objects.filter(transaction_filters)
            
            total_debits = account_transactions.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            total_credits = account_transactions.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')

            balance = total_debits - total_credits
            
            accounts_data.append({
                'account_code': account.account_code,
                'account_name': account.account_name,
                'total_debits': total_debits,
                'total_credits': total_credits,
                'balance': balance
            })
            
            overall_total_debits += total_debits
            overall_total_credits += total_credits

        report_data = {
            'accounts': accounts_data,
            'overall_total_debits': overall_total_debits,
            'overall_total_credits': overall_total_credits,
        }
        if as_of_date:
            report_data['as_of_date'] = as_of_date


        serializer = TrialBalanceReportSerializer(data=report_data)
        serializer.is_valid(raise_exception=True) # Validate the data before returning
        return Response(serializer.validated_data)
