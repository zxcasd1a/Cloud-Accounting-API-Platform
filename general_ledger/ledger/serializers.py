from rest_framework import serializers
from .models import Account, JournalEntry, Transaction, Vendor, Invoice, InvoiceLineItem # Add InvoiceLineItem
from django.db import transaction # Changed import for decorator use
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

class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'

# First, define InvoiceLineItemSerializer
class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = ['id', 'expense_account', 'description', 'amount', 'department_code', 'sub_department_code']
        # Optional: To ensure only expense accounts can be selected if not fully handled by model's limit_choices_to in DRF context:
        extra_kwargs = {
            'expense_account': {
                # Queryset to enforce that only expense accounts can be selected.
                # This might be redundant if model's limit_choices_to is well-respected by DRF for validation,
                # but can provide clearer error messages or ensure stricter enforcement at serializer level.
                'queryset': Account.objects.filter(account_type='EXPENSE'),
                'error_messages': {'does_not_exist': 'Selected account is not a valid expense account or does not exist.'}
            }
        }

class InvoiceSerializer(serializers.ModelSerializer):
    line_items = InvoiceLineItemSerializer(many=True) 

    class Meta:
        model = Invoice
        fields = [
            'id', 'vendor', 'invoice_number', 'invoice_date', 'due_date', 
            'total_amount', 'status', 'scanned_image_placeholder', 'notes', 
            'created_at', 'updated_at', 'line_items' 
        ]
        read_only_fields = ['status', 'created_at', 'updated_at']

    def validate_line_items(self, line_items_data):
        if not line_items_data:
            raise serializers.ValidationError("An invoice must have at least one line item.")
        return line_items_data
        
    def validate(self, data):
        # Ensure total_amount matches sum of line_items if line_items are present
        # This validation is only performed if line_items are part of the input data.
        # If line_items are not provided (e.g. during a partial update not affecting them),
        # this validation might not be triggered for them.
        if 'line_items' in data: # Only validate if line_items are being processed
            line_items_data = data.get('line_items', [])
            # The validate_line_items method above ensures line_items_data is not empty if present.
            # However, if it's an update and line_items is an empty list, this could pass.
            # The previous check `validate_line_items` handles the "must have at least one" case.
            
            total_from_lines = sum(item.get('amount', Decimal('0.00')) for item in line_items_data) # Ensure Decimal sum
            invoice_total_amount = data.get('total_amount', Decimal('0.00'))

            if total_from_lines != invoice_total_amount:
                raise serializers.ValidationError(
                    f"The sum of line item amounts ({total_from_lines}) must equal the invoice total amount ({invoice_total_amount})."
                )
        return data

    @transaction.atomic 
    def create(self, validated_data):
        line_items_data = validated_data.pop('line_items')
        invoice = Invoice.objects.create(**validated_data)
        for item_data in line_items_data:
            InvoiceLineItem.objects.create(invoice=invoice, **item_data)
        return invoice

    @transaction.atomic 
    def update(self, instance, validated_data):
        line_items_data = validated_data.pop('line_items', None)

        # Update Invoice instance fields
        instance.vendor = validated_data.get('vendor', instance.vendor)
        instance.invoice_number = validated_data.get('invoice_number', instance.invoice_number)
        instance.invoice_date = validated_data.get('invoice_date', instance.invoice_date)
        instance.due_date = validated_data.get('due_date', instance.due_date)
        instance.total_amount = validated_data.get('total_amount', instance.total_amount)
        instance.scanned_image_placeholder = validated_data.get('scanned_image_placeholder', instance.scanned_image_placeholder)
        instance.notes = validated_data.get('notes', instance.notes)
        # Status is read-only and handled by actions, so not updated here directly.
        # created_at and updated_at are auto-managed.
        instance.save()

        if line_items_data is not None: 
            instance.line_items.all().delete()
            for item_data in line_items_data:
                InvoiceLineItem.objects.create(invoice=instance, **item_data)
        
        return instance
