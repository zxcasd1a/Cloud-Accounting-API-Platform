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
        fields = ['entry_date', 'description', 'status', 'recurring_schedule', 'transactions']

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
