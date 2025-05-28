import datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction, models # Ensure models is imported for F objects
from django.db.models import Q # Import Q for complex queries
from ledger.models import JournalEntry, Transaction as LedgerTransaction # Alias Transaction to avoid conflict
from dateutil.relativedelta import relativedelta # Added for advanced date calculations
# from ledger.utils import calculate_next_recurrence_date # Or define it within this file for now

def calculate_next_recurrence_date(current_next_date, pattern, recurrence_end_date):
    """
    Calculates the next recurrence date based on the provided pattern and current date.

    This function determines the subsequent date for a recurring event, considering daily,
    weekly, monthly, quarterly, or annual patterns. It uses `relativedelta` for month-based
    calculations to correctly handle varying month lengths and leap years.

    Args:
        current_next_date (datetime.date): The date from which to calculate the next recurrence.
                                           This is typically the current `next_recurrence_date` of a template.
        pattern (str): The recurrence pattern. Expected values are 'DAILY', 'WEEKLY',
                       'MONTHLY', 'QUARTERLY', 'ANNUALLY'.
        recurrence_end_date (datetime.date, optional): The date after which the recurrence
                                                     should no longer generate new dates.
                                                     If None, the recurrence is indefinite.

    Returns:
        datetime.date or None: The next calculated recurrence date if successful and within
                               the `recurrence_end_date` (if specified).
                               Returns `None` if the pattern is unrecognized, if `current_next_date`
                               is `None`, or if the calculated next date would be past the
                               `recurrence_end_date`.
    """
    if not current_next_date: # Should not happen if called for an active template
        return None

    next_date = None
    
    if pattern == 'DAILY':
        next_date = current_next_date + datetime.timedelta(days=1)
    elif pattern == 'WEEKLY':
        next_date = current_next_date + datetime.timedelta(weeks=1)
    elif pattern == 'MONTHLY':
        # relativedelta handles month-end arithmetic correctly (e.g., Jan 31 + 1 month = Feb 28/29)
        next_date = current_next_date + relativedelta(months=1)
    elif pattern == 'QUARTERLY':
        next_date = current_next_date + relativedelta(months=3)
    elif pattern == 'ANNUALLY':
        next_date = current_next_date + relativedelta(years=1)
    else: # Unknown pattern
        # If the pattern is not recognized, cannot determine the next date.
        return None 

    # If a recurrence_end_date is set, check if the newly calculated next_date
    # goes beyond it. If so, this recurrence should stop.
    if recurrence_end_date and next_date and next_date > recurrence_end_date:
        return None # Recurrence should stop

    return next_date


class Command(BaseCommand):
    help = 'Processes active recurring journal entry templates to generate new journal entries.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to process recurring journal entries...'))
        today = timezone.now().date()
        
        # Fetch all active recurring journal entry templates that are due for processing.
        # Conditions for a template to be processed:
        # 1. `is_recurring_template` must be True.
        # 2. `status` must be 'POSTED' (i.e., the template is approved and active).
        # 3. `next_recurrence_date` must not be null (template hasn't expired or completed).
        # 4. `next_recurrence_date` must be on or before today.
        # 5. `recurrence_start_date` must be on or before today (template has started).
        # 6. The template has not yet reached its `recurrence_end_date`.
        #    This is checked by:
        #    - `recurrence_end_date` is null (template runs indefinitely), OR
        #    - `recurrence_end_date` is on or after the current `next_recurrence_date`.
        #      (Using F() object to compare model fields directly in the database).
        active_templates = JournalEntry.objects.filter(
            is_recurring_template=True,
            status='POSTED', 
            next_recurrence_date__isnull=False,
            next_recurrence_date__lte=today,
            recurrence_start_date__lte=today
        ).filter(
            Q(recurrence_end_date__isnull=True) | Q(recurrence_end_date__gte=models.F('next_recurrence_date'))
        )

        if not active_templates.exists():
            self.stdout.write(self.style.SUCCESS('No active recurring journal entry templates are due today.'))
            return

        # Loop through each due template and process it.
        for template in active_templates:
            self.stdout.write(f"Processing template ID {template.id} with next recurrence date {template.next_recurrence_date}...")

            try:
                # Use a database transaction to ensure atomicity. If any step fails,
                # the new JE creation and template update are rolled back.
                with transaction.atomic():
                    # 1. Create a new Journal Entry instance from the template.
                    # The new JE's entry_date is the template's current next_recurrence_date.
                    # Its status is 'PENDING' by default, requiring review/posting.
                    # It's marked as NOT a template itself.
                    # Recurrence-specific fields are nullified for the instance.
                    new_je = JournalEntry.objects.create(
                        entry_date=template.next_recurrence_date, 
                        description=f"{template.description} (Recurring from Template #{template.id})",
                        status='PENDING', 
                        is_recurring_template=False, 
                        recurrence_pattern=None,
                        recurrence_start_date=None,
                        recurrence_end_date=None,
                        next_recurrence_date=None,
                        # TODO: Consider copying other relevant fields like created_by, department if applicable
                        # This would depend on specific business requirements for inherited fields.
                    )

                    # 2. Copy all transactions from the template to the new Journal Entry.
                    template_transactions = LedgerTransaction.objects.filter(journal_entry=template)
                    for trans_template in template_transactions:
                        LedgerTransaction.objects.create(
                            journal_entry=new_je,
                            account=trans_template.account,
                            debit_amount=trans_template.debit_amount,
                            credit_amount=trans_template.credit_amount,
                            description=trans_template.description # Retain original transaction description
                        )
                    
                    self.stdout.write(self.style.SUCCESS(f"  Successfully generated Journal Entry ID {new_je.id} for date {new_je.entry_date}."))

                    # 3. Calculate and update the template's next_recurrence_date.
                    original_next_date = template.next_recurrence_date
                    new_next_date = calculate_next_recurrence_date(
                        original_next_date, 
                        template.recurrence_pattern, 
                        template.recurrence_end_date
                    )

                    # If calculate_next_recurrence_date returns a valid date, update the template.
                    if new_next_date: 
                        template.next_recurrence_date = new_next_date
                    else:
                        # If new_next_date is None, it means the template has reached its end_date
                        # or the pattern was unhandled. Mark it as completed by setting next_recurrence_date to None.
                        template.next_recurrence_date = None 
                        self.stdout.write(self.style.WARNING(f"  Template ID {template.id} has reached its recurrence end date or pattern logic concluded. It will no longer generate entries."))
                    
                    template.save()
                    self.stdout.write(f"  Updated next recurrence date for template ID {template.id} to {template.next_recurrence_date}.")

            except Exception as e:
                # Log any errors encountered during processing a specific template.
                # The process will continue with the next template.
                self.stderr.write(self.style.ERROR(f"Error processing template ID {template.id}: {e}"))
                # Depending on error severity, one might choose to re-raise or handle differently.

        self.stdout.write(self.style.SUCCESS('Finished processing recurring journal entries.'))
