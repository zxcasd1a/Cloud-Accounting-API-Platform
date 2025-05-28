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
    parent_account = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    department_code = models.CharField(max_length=20, null=True, blank=True)
    sub_department_code = models.CharField(max_length=20, null=True, blank=True)

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
    recurring_schedule = models.CharField(max_length=50, null=True, blank=True) # Existing field, may need re-evaluation later

    # New fields for recurring entries
    RECURRENCE_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('ANNUALLY', 'Annually'),
    ]
    recurrence_pattern = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, null=True, blank=True)
    recurrence_start_date = models.DateField(null=True, blank=True)
    recurrence_end_date = models.DateField(null=True, blank=True)
    next_recurrence_date = models.DateField(null=True, blank=True, db_index=True)
    is_recurring_template = models.BooleanField(default=False)

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

class Vendor(models.Model):
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    address_line_1 = models.CharField(max_length=255, null=True, blank=True)
    address_line_2 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    zip_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    payment_terms = models.CharField(max_length=100, null=True, blank=True)  # e.g., "Net 30", "Net 60"
    has_w9 = models.BooleanField(default=False)  # For W9 form status
    tax_id_number = models.CharField(max_length=50, null=True, blank=True)  # e.g., EIN, SSN for 1099 purposes
    is_1099_eligible = models.BooleanField(default=False)  # Indicates if the vendor is eligible for 1099 reporting
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Invoice(models.Model):
    PENDING_APPROVAL = 'PENDING_APPROVAL'
    APPROVED = 'APPROVED'
    PAID = 'PAID'
    REJECTED = 'REJECTED'
    DRAFT = 'DRAFT'
    
    STATUS_CHOICES = [
        (PENDING_APPROVAL, 'Pending Approval'),
        (APPROVED, 'Approved'),
        (PAID, 'Paid'),
        (REJECTED, 'Rejected'),
        (DRAFT, 'Draft'),
    ]

    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='invoices')
    invoice_number = models.CharField(max_length=100, unique=True)
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    scanned_image_placeholder = models.FileField(upload_to='invoice_scans/', null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Invoice {self.invoice_number} for {self.vendor.name}"

class InvoiceLineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    expense_account = models.ForeignKey(
        Account, 
        on_delete=models.PROTECT, 
        related_name='invoice_line_items',
        limit_choices_to={'account_type': 'EXPENSE'} # Use the actual stored value
    )
    description = models.TextField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    department_code = models.CharField(max_length=20, null=True, blank=True)
    sub_department_code = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f"Line for Invoice {self.invoice.invoice_number} - {self.expense_account.account_name} - {self.amount}"
