from django.db import models

class Account(models.Model):
    ACCOUNT_TYPES = [
        ('ASSET', 'Asset'),
        ('LIABILITY', 'Liability'),
        ('EQUITY', 'Equity'),
        ('REVENUE', 'Revenue'),
        ('EXPENSE', 'Expense'),
    ]
    account_code = models.CharField(max_length=20, unique=True)
    account_name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)
    is_customizable = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.account_code} - {self.account_name}"

class JournalEntry(models.Model):
    STATUS_CHOICES = [
        ('POSTED', 'Posted'),
        ('PENDING', 'Pending'),
        ('DRAFT', 'Draft'),
    ]
    entry_date = models.DateField()
    description = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    recurring_schedule = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Journal Entry {self.id} - {self.entry_date} - {self.status}"

class Transaction(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='transactions')
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    debit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Transaction {self.id} for JE {self.journal_entry.id} - Account: {self.account.account_code}"
