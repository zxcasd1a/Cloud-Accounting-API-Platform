from rest_framework import serializers
from .models import Account, JournalEntry, Transaction
from django.db import transaction as db_transaction # Renamed to avoid conflict
from decimal import Decimal # Import Decimal for calculations

class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = '__all__'

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['account', 'debit_amount', 'credit_amount', 'description']

class JournalEntrySerializer(serializers.ModelSerializer):
    transactions = TransactionSerializer(many=True)

    class Meta:
        model = JournalEntry
        fields = [
            'entry_date', 'description', 'status', 'recurring_schedule', 
            'recurrence_pattern', 'recurrence_start_date', 'recurrence_end_date', 
            'next_recurrence_date', 'is_recurring_template', 'transactions'
        ]

    def validate(self, data):
        transactions_data = data.get('transactions', [])
        if not transactions_data:
            raise serializers.ValidationError("A journal entry must have at least one transaction.")

        total_debits = sum(t.get('debit_amount', 0) for t in transactions_data)
        total_credits = sum(t.get('credit_amount', 0) for t in transactions_data)

        if total_debits != total_credits:
            raise serializers.ValidationError("Total debits must equal total credits.")
        
        for t_data in transactions_data:
            if t_data.get('debit_amount', 0) > 0 and t_data.get('credit_amount', 0) > 0:
                raise serializers.ValidationError("A single transaction cannot have both debit and credit amounts.")
            if t_data.get('debit_amount', 0) == 0 and t_data.get('credit_amount', 0) == 0:
                raise serializers.ValidationError("A transaction must have either a debit or a credit amount.")

        return data

    def create(self, validated_data):
        transactions_data = validated_data.pop('transactions')
        with db_transaction.atomic(): # Use the renamed import
            journal_entry = JournalEntry.objects.create(**validated_data)
            for transaction_data in transactions_data:
                Transaction.objects.create(journal_entry=journal_entry, **transaction_data)
        return journal_entry

# New Serializers for Trial Balance
class TrialBalanceAccountSerializer(serializers.Serializer):
    account_code = serializers.CharField()
    account_name = serializers.CharField()
    total_debits = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_credits = serializers.DecimalField(max_digits=12, decimal_places=2)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)

class TrialBalanceReportSerializer(serializers.Serializer):
    accounts = TrialBalanceAccountSerializer(many=True)
    overall_total_debits = serializers.DecimalField(max_digits=15, decimal_places=2)
    overall_total_credits = serializers.DecimalField(max_digits=15, decimal_places=2)
    report_date = serializers.DateField(required=False) # Optional: to filter by date
    as_of_date = serializers.DateField(required=False) # Optional: to specify the "as of" date for the report

# Serializers for Income Statement
class IncomeStatementAccountSerializer(serializers.Serializer):
    account_code = serializers.CharField()
    account_name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    account_type = serializers.CharField() # REVENUE or EXPENSE

class IncomeStatementSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    revenue_accounts = serializers.ListField(child=IncomeStatementAccountSerializer())
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    expense_accounts = serializers.ListField(child=IncomeStatementAccountSerializer())
    total_expenses = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_income = serializers.DecimalField(max_digits=15, decimal_places=2)

# Serializers for Balance Sheet
class BalanceSheetAccountSerializer(serializers.Serializer):
    account_code = serializers.CharField()
    account_name = serializers.CharField()
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    account_type = serializers.CharField() # ASSET, LIABILITY, or EQUITY

class BalanceSheetSerializer(serializers.Serializer):
    as_of_date = serializers.DateField()
    asset_accounts = serializers.ListField(child=BalanceSheetAccountSerializer())
    total_assets = serializers.DecimalField(max_digits=15, decimal_places=2)
    liability_accounts = serializers.ListField(child=BalanceSheetAccountSerializer())
    total_liabilities = serializers.DecimalField(max_digits=15, decimal_places=2)
    equity_accounts = serializers.ListField(child=BalanceSheetAccountSerializer()) # Excluding Retained Earnings here, will be part of total_equity
    total_equity = serializers.DecimalField(max_digits=15, decimal_places=2) # Includes individual equity accounts + retained_earnings
    retained_earnings = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_liabilities_and_equity = serializers.DecimalField(max_digits=15, decimal_places=2)

# Serializers for Cash Flow Statement
class CashFlowActivitySerializer(serializers.Serializer):
    description = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)

class CashFlowStatementSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    net_income = serializers.DecimalField(max_digits=15, decimal_places=2)
    adjustments_to_net_income = serializers.ListField(child=CashFlowActivitySerializer())
    net_cash_from_operating_activities = serializers.DecimalField(max_digits=15, decimal_places=2)
    cash_flows_from_investing_activities = serializers.ListField(child=CashFlowActivitySerializer())
    net_cash_from_investing_activities = serializers.DecimalField(max_digits=15, decimal_places=2)
    cash_flows_from_financing_activities = serializers.ListField(child=CashFlowActivitySerializer())
    net_cash_from_financing_activities = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_change_in_cash = serializers.DecimalField(max_digits=15, decimal_places=2)
    cash_at_beginning_of_period = serializers.DecimalField(max_digits=15, decimal_places=2)
    cash_at_end_of_period = serializers.DecimalField(max_digits=15, decimal_places=2)
