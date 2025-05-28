from rest_framework import viewsets, status
from rest_framework.decorators import action # Added action
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Q
from decimal import Decimal
from .models import Account, JournalEntry, Transaction, Vendor, Invoice, PurchaseOrder # Add Invoice, PurchaseOrder
from .serializers import (
    AccountSerializer, JournalEntrySerializer, TrialBalanceReportSerializer, 
    TrialBalanceAccountSerializer, IncomeStatementSerializer, BalanceSheetSerializer,
    CashFlowStatementSerializer, VendorSerializer, InvoiceSerializer, PurchaseOrderSerializer # Add InvoiceSerializer, PurchaseOrderSerializer
)
from django.utils.dateparse import parse_date
from django.utils import timezone # For default end_date
import datetime as dt # For timedelta and date objects, aliased as dt
from dateutil.relativedelta import relativedelta # For month calculations

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

class IncomeStatementAPIView(APIView):
    def get(self, request):
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if not start_date_str or not end_date_str:
            return Response({"error": "Both start_date and end_date are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        if not start_date or not end_date:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
            
        if start_date > end_date:
            return Response({"error": "start_date cannot be after end_date."}, status=status.HTTP_400_BAD_REQUEST)

        revenue_accounts_data = []
        expense_accounts_data = []
        total_revenue = Decimal('0.00')
        total_expenses = Decimal('0.00')

        accounts = Account.objects.filter(Q(account_type='REVENUE') | Q(account_type='EXPENSE')).order_by('account_code')

        for account in accounts:
            transactions = Transaction.objects.filter(
                account=account,
                journal_entry__entry_date__range=[start_date, end_date],
                journal_entry__status='POSTED'
            )
            
            debits = transactions.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            credits = transactions.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')

            account_balance = Decimal('0.00')
            if account.account_type == 'REVENUE':
                account_balance = credits - debits
                total_revenue += account_balance
                if account_balance != Decimal('0.00'): # Only include accounts with activity
                    revenue_accounts_data.append({
                        'account_code': account.account_code,
                        'account_name': account.account_name,
                        'amount': account_balance,
                        'account_type': account.account_type
                    })
            elif account.account_type == 'EXPENSE':
                account_balance = debits - credits
                total_expenses += account_balance
                if account_balance != Decimal('0.00'): # Only include accounts with activity
                    expense_accounts_data.append({
                        'account_code': account.account_code,
                        'account_name': account.account_name,
                        'amount': account_balance,
                        'account_type': account.account_type
                    })
        
        net_income = total_revenue - total_expenses

        report_data = {
            'start_date': start_date,
            'end_date': end_date,
            'revenue_accounts': revenue_accounts_data,
            'total_revenue': total_revenue,
            'expense_accounts': expense_accounts_data,
            'total_expenses': total_expenses,
            'net_income': net_income
        }

        serializer = IncomeStatementSerializer(data=report_data)
        if serializer.is_valid():
            return Response(serializer.validated_data)
        else:
            # Log serializer errors if possible, or return them for debugging
            # For now, returning a generic error or the serializer.errors
            return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class T12IncomeStatementAPIView(APIView):
    def get(self, request):
        end_date_str = request.query_params.get('end_date')

        if end_date_str:
            try:
                end_date = parse_date(end_date_str)
                if not end_date: # parse_date returns None for invalid date string
                    raise ValueError
            except ValueError:
                return Response({"error": "Invalid date format for end_date. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            end_date = timezone.now().date()

        # Calculate T12 start_date: 1st day of the month, 11 months prior to end_date's month
        # Example: if end_date is 2023-03-15, 11 months prior is 2022-04-15. start_date becomes 2022-04-01.
        start_date_month_eval = end_date - relativedelta(months=11)
        start_date = dt.date(start_date_month_eval.year, start_date_month_eval.month, 1)
        
        # Core Income Statement Logic (adapted from IncomeStatementAPIView)
        revenue_accounts_data = []
        expense_accounts_data = []
        total_revenue = Decimal('0.00')
        total_expenses = Decimal('0.00')

        accounts = Account.objects.filter(Q(account_type='REVENUE') | Q(account_type='EXPENSE')).order_by('account_code')

        for account in accounts:
            transactions = Transaction.objects.filter(
                account=account,
                journal_entry__entry_date__range=[start_date, end_date],
                journal_entry__status='POSTED'
            )
            
            debits = transactions.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            credits = transactions.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')

            account_balance = Decimal('0.00')
            if account.account_type == 'REVENUE':
                account_balance = credits - debits
                total_revenue += account_balance
                if account_balance != Decimal('0.00'): # Only include accounts with activity
                    revenue_accounts_data.append({
                        'account_code': account.account_code,
                        'account_name': account.account_name,
                        'amount': account_balance,
                        'account_type': account.account_type
                    })
            elif account.account_type == 'EXPENSE':
                account_balance = debits - credits
                total_expenses += account_balance
                if account_balance != Decimal('0.00'): # Only include accounts with activity
                    expense_accounts_data.append({
                        'account_code': account.account_code,
                        'account_name': account.account_name,
                        'amount': account_balance,
                        'account_type': account.account_type
                    })
        
        net_income = total_revenue - total_expenses

        report_data = {
            'start_date': start_date,
            'end_date': end_date,
            'revenue_accounts': revenue_accounts_data,
            'total_revenue': total_revenue,
            'expense_accounts': expense_accounts_data,
            'total_expenses': total_expenses,
            'net_income': net_income
        }

        serializer = IncomeStatementSerializer(data=report_data) # Reusing existing serializer
        if serializer.is_valid():
            return Response(serializer.validated_data)
        else:
            return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.all()
    serializer_class = PurchaseOrderSerializer
    # permission_classes = [...] # Add permissions later if needed

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        purchase_order = self.get_object()
        if purchase_order.status in [PurchaseOrder.DRAFT, PurchaseOrder.PENDING_APPROVAL]:
            purchase_order.status = PurchaseOrder.APPROVED
            purchase_order.save()
            return Response({'status': 'Purchase Order approved'}, status=status.HTTP_200_OK)
        return Response(
            {'error': f'Purchase Order cannot be approved from its current state: {purchase_order.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        purchase_order = self.get_object()
        allowed_statuses_for_cancellation = [PurchaseOrder.DRAFT, PurchaseOrder.PENDING_APPROVAL, PurchaseOrder.APPROVED]
        if purchase_order.status in allowed_statuses_for_cancellation:
            purchase_order.status = PurchaseOrder.CANCELLED
            purchase_order.save()
            return Response({'status': 'Purchase Order cancelled'}, status=status.HTTP_200_OK)
        return Response(
            {'error': f'Purchase Order cannot be cancelled from its current state: {purchase_order.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        purchase_order = self.get_object()
        # For now, full receipt is assumed. Partial receipts would require more complex logic
        # and potentially input about which lines/quantities are received.
        if purchase_order.status in [PurchaseOrder.APPROVED, PurchaseOrder.PARTIALLY_RECEIVED]:
            # In a more complex scenario, you might check if all items are received
            # and then change status to RECEIVED. If only some are, it might be PARTIALLY_RECEIVED.
            # For this placeholder, we'll just mark it as RECEIVED.
            purchase_order.status = PurchaseOrder.RECEIVED 
            purchase_order.save()
            # TODO: Add logic here to create ReceivingSlip objects or update inventory based on line items.
            # This is a placeholder for now.
            return Response({'status': 'Purchase Order marked as received. Further processing (e.g., inventory update) placeholder.'}, status=status.HTTP_200_OK)
        return Response(
            {'error': f'Purchase Order cannot be marked as received from its current state: {purchase_order.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        invoice = self.get_object()
        # Allow approval from DRAFT or PENDING_APPROVAL
        if invoice.status in [Invoice.DRAFT, Invoice.PENDING_APPROVAL]:
            invoice.status = Invoice.APPROVED
            invoice.save()
            return Response({'status': 'Invoice approved'}, status=status.HTTP_200_OK)
        return Response({'status': f'Invoice cannot be approved from its current state: {invoice.status}'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        invoice = self.get_object()
        # Allow rejection from DRAFT or PENDING_APPROVAL
        if invoice.status in [Invoice.DRAFT, Invoice.PENDING_APPROVAL]:
            invoice.status = Invoice.REJECTED
            invoice.save()
            return Response({'status': 'Invoice rejected'}, status=status.HTTP_200_OK)
        return Response({'status': f'Invoice cannot be rejected from its current state: {invoice.status}'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def mark_as_paid(self, request, pk=None):
        invoice = self.get_object()
        # Only allow marking as paid if currently APPROVED
        if invoice.status == Invoice.APPROVED:
            invoice.status = Invoice.PAID
            invoice.save()
            return Response({'status': 'Invoice marked as paid'}, status=status.HTTP_200_OK)
        return Response({'status': f'Invoice cannot be marked as paid from its current state: {invoice.status}'}, status=status.HTTP_400_BAD_REQUEST)

class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer

class CashFlowStatementAPIView(APIView):
    
    def _get_account_balance(self, account_code, as_of_date):
        """Helper to get balance for a single account as of a specific date."""
        try:
            account = Account.objects.get(account_code=account_code)
        except Account.DoesNotExist:
            return Decimal('0.00')

        transactions = Transaction.objects.filter(
            account=account,
            journal_entry__entry_date__lte=as_of_date,
            journal_entry__status='POSTED'
        )
        debits = transactions.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
        credits = transactions.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        
        if account.account_type in ['ASSET', 'EXPENSE']:
            return debits - credits
        elif account.account_type in ['LIABILITY', 'EQUITY', 'REVENUE']:
            return credits - debits
        return Decimal('0.00')

    def _get_cash_accounts_balance(self, as_of_date):
        """Helper to get total balance of cash and cash equivalent accounts."""
        # Simplified: Assumes cash accounts have "Cash" or "Bank" in their name.
        # This should be made more robust in a real system (e.g., a flag on the Account model).
        cash_accounts = Account.objects.filter(
            Q(account_type='ASSET') & (Q(account_name__icontains="Cash") | Q(account_name__icontains="Bank"))
        )
        total_cash_balance = Decimal('0.00')
        for account in cash_accounts:
            transactions = Transaction.objects.filter(
                account=account,
                journal_entry__entry_date__lte=as_of_date,
                journal_entry__status='POSTED'
            )
            debits = transactions.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            credits = transactions.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
            total_cash_balance += (debits - credits) # Assets are debit positive
        return total_cash_balance

    def get(self, request):
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if not start_date_str or not end_date_str:
            return Response({"error": "Both start_date and end_date are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)
            if not start_date or not end_date: # parse_date returns None for invalid date string
                raise ValueError
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        
        if start_date > end_date:
            return Response({"error": "start_date cannot be after end_date."}, status=status.HTTP_400_BAD_REQUEST)

        # A. Calculate Net Income for the period
        total_revenue = Decimal('0.00')
        revenue_accounts_qs = Account.objects.filter(account_type='REVENUE')
        for acc in revenue_accounts_qs:
            transactions = Transaction.objects.filter(
                account=acc,
                journal_entry__entry_date__range=[start_date, end_date],
                journal_entry__status='POSTED'
            )
            debits = transactions.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            credits = transactions.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
            total_revenue += (credits - debits)

        total_expenses = Decimal('0.00')
        expense_accounts_qs = Account.objects.filter(account_type='EXPENSE')
        for acc in expense_accounts_qs:
            transactions = Transaction.objects.filter(
                account=acc,
                journal_entry__entry_date__range=[start_date, end_date],
                journal_entry__status='POSTED'
            )
            debits = transactions.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            credits = transactions.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
            total_expenses += (debits - credits)
        
        net_income = total_revenue - total_expenses

        # B. Cash at Beginning of Period
        day_before_start_date = start_date - dt.timedelta(days=1) # Use aliased dt
        cash_at_beginning_of_period = self._get_cash_accounts_balance(day_before_start_date)
        
        # C. Cash at End of Period
        cash_at_end_of_period = self._get_cash_accounts_balance(end_date)
        
        # D. Net Change in Cash
        net_change_in_cash = cash_at_end_of_period - cash_at_beginning_of_period

        # E. Cash Flows from Operating Activities (Indirect Method - Simplified)
        adjustments_to_net_income = []
        
        # Simplified Working Capital Changes (Example: Accounts Receivable and Payable)
        # Accounts Receivable (Asset)
        ar_start_balance = self._get_account_balance("1200", day_before_start_date) # Assuming 1200 is AR
        ar_end_balance = self._get_account_balance("1200", end_date)
        change_in_ar = ar_end_balance - ar_start_balance
        if change_in_ar != Decimal('0.00'):
             # Increase in AR is a cash outflow (-) from net income perspective
            adjustments_to_net_income.append({'description': 'Change in Accounts Receivable', 'amount': -change_in_ar})

        # Accounts Payable (Liability)
        ap_start_balance = self._get_account_balance("2100", day_before_start_date) # Assuming 2100 is AP
        ap_end_balance = self._get_account_balance("2100", end_date)
        change_in_ap = ap_end_balance - ap_start_balance
        if change_in_ap != Decimal('0.00'):
            # Increase in AP is a cash inflow (+) from net income perspective
            adjustments_to_net_income.append({'description': 'Change in Accounts Payable', 'amount': change_in_ap})

        sum_of_adjustments = sum(item['amount'] for item in adjustments_to_net_income)
        net_cash_from_operating_activities = net_income + sum_of_adjustments

        # F. Cash Flows from Investing Activities (Placeholder/Simplified)
        # Example: Change in a generic 'Fixed Assets' account
        investing_activities = []
        fixed_assets_start = self._get_account_balance("1500", day_before_start_date) # Assuming 1500 is Fixed Assets
        fixed_assets_end = self._get_account_balance("1500", end_date)
        change_in_fixed_assets = fixed_assets_end - fixed_assets_start
        if change_in_fixed_assets != Decimal('0.00'):
            # Increase in fixed assets is a cash outflow
            investing_activities.append({'description': 'Change in Fixed Assets (Net)', 'amount': -change_in_fixed_assets})
        net_cash_from_investing_activities = sum(item['amount'] for item in investing_activities)


        # G. Cash Flows from Financing Activities (Placeholder/Simplified)
        # Example: Change in a generic 'Long-term Debt' account
        financing_activities = []
        long_term_debt_start = self._get_account_balance("2500", day_before_start_date) # Assuming 2500 is LTD
        long_term_debt_end = self._get_account_balance("2500", end_date)
        change_in_ltd = long_term_debt_end - long_term_debt_start
        if change_in_ltd != Decimal('0.00'):
            # Increase in LTD is a cash inflow
            financing_activities.append({'description': 'Change in Long-term Debt (Net)', 'amount': change_in_ltd})
        net_cash_from_financing_activities = sum(item['amount'] for item in financing_activities)

        # H. Reconciliation (Calculated net_change_in_cash vs sum of activities)
        # For this simplified version, we use the net_change_in_cash calculated from beginning/end balances.
        # A more robust version would ensure sum of activities matches this.
        # calculated_net_change_from_activities = net_cash_from_operating_activities + net_cash_from_investing_activities + net_cash_from_financing_activities
        # if net_change_in_cash != calculated_net_change_from_activities:
        #     print(f"Warning: Cash flow activities do not reconcile to net change in cash. Calculated: {calculated_net_change_from_activities}, From Balances: {net_change_in_cash}")


        report_data = {
            'start_date': start_date,
            'end_date': end_date,
            'net_income': net_income,
            'adjustments_to_net_income': adjustments_to_net_income,
            'net_cash_from_operating_activities': net_cash_from_operating_activities,
            'cash_flows_from_investing_activities': investing_activities,
            'net_cash_from_investing_activities': net_cash_from_investing_activities,
            'cash_flows_from_financing_activities': financing_activities,
            'net_cash_from_financing_activities': net_cash_from_financing_activities,
            'net_change_in_cash': net_change_in_cash,
            'cash_at_beginning_of_period': cash_at_beginning_of_period,
            'cash_at_end_of_period': cash_at_end_of_period,
        }

        serializer = CashFlowStatementSerializer(data=report_data)
        if serializer.is_valid():
            return Response(serializer.validated_data)
        else:
            return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BalanceSheetAPIView(APIView):
    def get(self, request):
        as_of_date_str = request.query_params.get('as_of_date')

        if not as_of_date_str:
            return Response({"error": "as_of_date is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            as_of_date = parse_date(as_of_date_str)
            if not as_of_date: # parse_date returns None for invalid date string
                raise ValueError 
        except ValueError:
            return Response({"error": "Invalid date format for as_of_date. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate Retained Earnings
        total_historic_revenue = Decimal('0.00')
        revenue_accounts_qs = Account.objects.filter(account_type='REVENUE')
        for acc in revenue_accounts_qs:
            transactions = Transaction.objects.filter(
                account=acc,
                journal_entry__entry_date__lte=as_of_date,
                journal_entry__status='POSTED'
            )
            debits = transactions.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            credits = transactions.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
            total_historic_revenue += (credits - debits)

        total_historic_expenses = Decimal('0.00')
        expense_accounts_qs = Account.objects.filter(account_type='EXPENSE')
        for acc in expense_accounts_qs:
            transactions = Transaction.objects.filter(
                account=acc,
                journal_entry__entry_date__lte=as_of_date,
                journal_entry__status='POSTED'
            )
            debits = transactions.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            credits = transactions.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
            total_historic_expenses += (debits - credits)
        
        retained_earnings = total_historic_revenue - total_historic_expenses

        asset_accounts_data = []
        liability_accounts_data = []
        equity_accounts_data = [] # For explicit equity accounts, excluding retained earnings

        total_assets = Decimal('0.00')
        total_liabilities = Decimal('0.00')
        total_equity_accounts_balance = Decimal('0.00') # Sum of balances of explicit equity accounts

        accounts = Account.objects.filter(
            Q(account_type='ASSET') | Q(account_type='LIABILITY') | Q(account_type='EQUITY')
        ).order_by('account_code')

        for account in accounts:
            transactions = Transaction.objects.filter(
                account=account,
                journal_entry__entry_date__lte=as_of_date,
                journal_entry__status='POSTED'
            )
            debits = transactions.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            credits = transactions.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')

            balance = Decimal('0.00')
            if account.account_type == 'ASSET':
                balance = debits - credits
                total_assets += balance
                if balance != Decimal('0.00'):
                     asset_accounts_data.append({
                        'account_code': account.account_code,
                        'account_name': account.account_name,
                        'balance': balance,
                        'account_type': account.account_type
                    })
            elif account.account_type == 'LIABILITY':
                balance = credits - debits
                total_liabilities += balance
                if balance != Decimal('0.00'):
                    liability_accounts_data.append({
                        'account_code': account.account_code,
                        'account_name': account.account_name,
                        'balance': balance,
                        'account_type': account.account_type
                    })
            elif account.account_type == 'EQUITY':
                balance = credits - debits # Capital, Drawings etc.
                total_equity_accounts_balance += balance
                if balance != Decimal('0.00'):
                    equity_accounts_data.append({
                        'account_code': account.account_code,
                        'account_name': account.account_name,
                        'balance': balance,
                        'account_type': account.account_type
                    })
        
        total_equity = total_equity_accounts_balance + retained_earnings
        total_liabilities_and_equity = total_liabilities + total_equity
        
        # Basic check for Balance Sheet equation
        # Note: This is a data integrity check, not a strict validation that would fail the report.
        # Small discrepancies might occur due to floating point issues if not careful, though Decimal helps.
        if total_assets != total_liabilities_and_equity:
            # Consider logging a warning if a logging mechanism is in place
            print(f"Warning: Balance Sheet out of balance. Assets: {total_assets}, L&E: {total_liabilities_and_equity}")


        report_data = {
            'as_of_date': as_of_date,
            'asset_accounts': asset_accounts_data,
            'total_assets': total_assets,
            'liability_accounts': liability_accounts_data,
            'total_liabilities': total_liabilities,
            'equity_accounts': equity_accounts_data, # Explicit equity accounts
            'retained_earnings': retained_earnings,
            'total_equity': total_equity, # Sum of explicit equity accounts + retained earnings
            'total_liabilities_and_equity': total_liabilities_and_equity
        }

        serializer = BalanceSheetSerializer(data=report_data)
        if serializer.is_valid():
            return Response(serializer.validated_data)
        else:
            return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
