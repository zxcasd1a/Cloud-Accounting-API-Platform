from django.contrib import admin
from .models import Account, JournalEntry, Transaction

# Register your models here.
admin.site.register(Account)
admin.site.register(JournalEntry)
admin.site.register(Transaction)
