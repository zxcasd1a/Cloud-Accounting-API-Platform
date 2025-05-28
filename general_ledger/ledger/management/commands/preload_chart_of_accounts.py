import csv
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings # To build default filepath
from ledger.models import Account
import os
from django.db import transaction

class Command(BaseCommand):
    help = 'Preloads the Chart of Accounts from a CSV file based on USALI.'

    def add_arguments(self, parser):
        # The default path needs to be relative to the project's base directory.
        # Assuming 'general_ledger' is at the root of the project where manage.py is.
        # If 'ledger' is an app within 'general_ledger' project directory
        default_csv_path = os.path.join(settings.BASE_DIR, 'general_ledger', 'ledger', 'data', 'usali_chart_of_accounts.csv')
        
        parser.add_argument(
            '--filepath',
            type=str,
            default=default_csv_path,
            help=f'Specifies the path to the CSV file. Defaults to {default_csv_path}'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='If set, deletes all existing Account objects before importing.'
        )

    def handle(self, *args, **options):
        filepath = options['filepath']
        overwrite = options['overwrite']

        # Validate account_type choices
        valid_account_types = [choice[0] for choice in Account.ACCOUNT_TYPES]

        if not os.path.exists(filepath):
            raise CommandError(f"File not found at path: {filepath}")

        if overwrite:
            self.stdout.write(self.style.WARNING('Deleting all existing Account objects...'))
            count, _ = Account.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} Account objects.'))

        accounts_map = {} # For first pass: account_code -> Account instance
        rows_data = [] # To store rows for second pass
        created_count = 0
        
        self.stdout.write(self.style.SUCCESS(f"Starting first pass: Reading accounts from {filepath}"))
        try:
            with open(filepath, mode='r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    rows_data.append(row) # Store for second pass
                    
                    account_code = row.get('account_code')
                    account_name = row.get('account_name')
                    account_type = row.get('account_type')
                    is_customizable_str = row.get('is_customizable', 'TRUE').upper()

                    if not all([account_code, account_name, account_type]):
                        self.stdout.write(self.style.WARNING(f"Skipping row due to missing required fields: {row}"))
                        continue

                    if account_type not in valid_account_types:
                        self.stdout.write(self.style.WARNING(f"Invalid account_type '{account_type}' for account {account_code}. Skipping."))
                        continue
                    
                    is_customizable = is_customizable_str == 'TRUE'

                    if account_code in accounts_map:
                        self.stdout.write(self.style.WARNING(f"Duplicate account_code '{account_code}' found in CSV. Skipping subsequent entry."))
                        continue

                    try:
                        # Create account without parent in the first pass
                        account = Account(
                            account_code=account_code,
                            name=account_name,
                            account_type=account_type,
                            is_customizable=is_customizable,
                            # parent_account will be set in the second pass
                            # department_code and sub_department_code are not directly in Account model
                            # but could be part of a related model or handled differently if needed.
                            # For now, assuming they are not directly mapped or are optional/handled elsewhere.
                        )
                        # Not saving yet, will do it in a transaction after both passes or per account in second pass
                        accounts_map[account_code] = account
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error creating account object for code {account_code}: {e}"))
                        
        except FileNotFoundError:
            raise CommandError(f"CSV file not found at path: {filepath}")
        except Exception as e:
            raise CommandError(f"Error reading CSV file: {e}")
        
        self.stdout.write(self.style.SUCCESS(f"First pass completed. {len(accounts_map)} potential accounts mapped."))
        self.stdout.write(self.style.SUCCESS("Starting second pass: Linking parent accounts and saving."))

        try:
            with transaction.atomic(): # Use a transaction for the saving part
                for row_dict in rows_data:
                    account_code = row_dict.get('account_code')
                    parent_account_code = row_dict.get('parent_account_code')

                    account_to_save = accounts_map.get(account_code)
                    if not account_to_save:
                        # This account might have been skipped due to errors in first pass
                        continue

                    if parent_account_code:
                        parent_account_instance = accounts_map.get(parent_account_code)
                        if parent_account_instance:
                            account_to_save.parent_account = parent_account_instance
                        else:
                            self.stdout.write(self.style.WARNING(
                                f"Parent account with code '{parent_account_code}' not found for account '{account_code}'. Skipping parent link."
                            ))
                    
                    # Now save the account (it's either new or updated with parent)
                    account_to_save.save()
                    created_count +=1
                    # self.stdout.write(self.style.SUCCESS(f"Successfully created/updated account: {account_to_save.account_code} - {account_to_save.name}"))

        except Exception as e:
            raise CommandError(f"Error during second pass (linking parents and saving): {e}")

        self.stdout.write(self.style.SUCCESS(f'Successfully preloaded {created_count} accounts.'))
