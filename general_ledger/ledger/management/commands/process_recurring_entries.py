from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction as db_transaction
from ledger.models import JournalEntry, Transaction # Assuming models are in ledger.models
from dateutil.relativedelta import relativedelta # For date calculations
import datetime

class Command(BaseCommand):
    help = 'Processes recurring journal entries and creates new entries as needed.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to process recurring journal entries...'))
        today = timezone.now().date()

        templates_to_process = JournalEntry.objects.filter(
            is_recurring_template=True,
            next_recurrence_date__lte=today
        )

        for template in templates_to_process:
            if template.recurrence_end_date and template.next_recurrence_date > template.recurrence_end_date:
                self.stdout.write(self.style.WARNING(f"Template '{template.description}' (ID: {template.id}) is past its end date. Skipping."))
                # Optionally, mark as inactive or set next_recurrence_date to None
                # For now, we'll just skip and it won't be picked up again if next_recurrence_date is not updated.
                # If it was already past its end_date but next_recurrence_date was *not* None,
                # it implies it should have been processed one last time on recurrence_end_date.
                # The check above ensures we don't process if next_recurrence_date is *strictly* greater.
                # If next_recurrence_date == recurrence_end_date, it *should* be processed.
                # If next_recurrence_date > recurrence_end_date, it should be skipped.
                # If it has been processed and next_recurrence_date now exceeds recurrence_end_date,
                # it will be set to None later.
                continue

            self.stdout.write(self.style.SUCCESS(f"Processing template: '{template.description}' (ID: {template.id}) for date: {template.next_recurrence_date}"))

            try:
                with db_transaction.atomic():
                    # Create new Journal Entry from template
                    new_entry = JournalEntry.objects.create(
                        entry_date=template.next_recurrence_date,
                        description=f"Recurring: {template.description}", # Append to original description
                        status='DRAFT', # Or 'PENDING' as per requirements
                        is_recurring_template=False,
                        # Clear recurrence fields for the new instance
                        recurrence_pattern=None,
                        recurrence_start_date=None,
                        recurrence_end_date=None,
                        next_recurrence_date=None,
                        # Copy other relevant fields if necessary
                        created_by=template.created_by, # Assuming you want to preserve who created the template
                        company=template.company # Assuming it belongs to the same company
                    )
                    self.stdout.write(self.style.SUCCESS(f"  Created new Journal Entry (ID: {new_entry.id})"))

                    # Copy transactions from template to new entry
                    template_transactions = template.transactions.all()
                    for trans_template in template_transactions:
                        Transaction.objects.create(
                            journal_entry=new_entry,
                            account=trans_template.account,
                            description=trans_template.description,
                            debit_amount=trans_template.debit_amount,
                            credit_amount=trans_template.credit_amount
                        )
                    self.stdout.write(self.style.SUCCESS(f"  Copied {template_transactions.count()} transactions to new entry."))

                    # Calculate next recurrence date for the template
                    current_next_date = template.next_recurrence_date
                    new_next_date = None

                    if template.recurrence_pattern == 'DAILY':
                        new_next_date = current_next_date + relativedelta(days=1)
                    elif template.recurrence_pattern == 'WEEKLY':
                        new_next_date = current_next_date + relativedelta(weeks=1)
                    elif template.recurrence_pattern == 'MONTHLY':
                        new_next_date = current_next_date + relativedelta(months=1)
                    elif template.recurrence_pattern == 'QUARTERLY':
                        new_next_date = current_next_date + relativedelta(months=3)
                    elif template.recurrence_pattern == 'ANNUALLY':
                        new_next_date = current_next_date + relativedelta(years=1)
                    
                    if new_next_date:
                        if template.recurrence_end_date and new_next_date > template.recurrence_end_date:
                            template.next_recurrence_date = None # Mark as complete or stop recurrence
                            template.status = 'COMPLETED' # Example: Update status of template
                            self.stdout.write(self.style.SUCCESS(f"  Template '{template.description}' (ID: {template.id}) has reached its recurrence end date. It will not recur again."))
                        else:
                            template.next_recurrence_date = new_next_date
                            self.stdout.write(self.style.SUCCESS(f"  Updated template '{template.description}' (ID: {template.id}) next recurrence date to {new_next_date}."))
                    else:
                        # This case should ideally not be reached if pattern is set,
                        # but as a fallback, or if pattern is invalid/None for a template:
                        template.next_recurrence_date = None 
                        self.stdout.write(self.style.WARNING(f"  Template '{template.description}' (ID: {template.id}) has no valid recurrence pattern or new date could not be calculated. It will not recur again."))

                    template.save()

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing template '{template.description}' (ID: {template.id}): {e}"))
        
        self.stdout.write(self.style.SUCCESS('Finished processing recurring journal entries.'))
