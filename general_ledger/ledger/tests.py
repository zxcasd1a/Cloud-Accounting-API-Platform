from django.urls import reverse
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal
import datetime
from dateutil.relativedelta import relativedelta
from django.utils.dateparse import parse_date # Import parse_date

from .models import Account, JournalEntry, Transaction, Vendor, PurchaseOrder, PurchaseOrderLineItem

class BaseReportTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Dates for transactions
        cls.today = timezone.now().date()
        cls.t_minus_1_month = cls.today - relativedelta(months=1)
        cls.t_minus_2_months = cls.today - relativedelta(months=2)
        cls.t_minus_11_months = cls.today - relativedelta(months=11)
        cls.t_minus_12_months = cls.today - relativedelta(months=12)
        cls.t_minus_13_months = cls.today - relativedelta(months=13)
        
        cls.start_of_t_minus_11_months = cls.t_minus_11_months.replace(day=1)


        # Accounts
        cls.cash_main = Account.objects.create(account_code="1010", account_name="Main Bank Account", account_type="ASSET")
        cls.petty_cash = Account.objects.create(account_code="1020", account_name="Petty Cash", account_type="ASSET")
        cls.accounts_receivable = Account.objects.create(account_code="1200", account_name="AR Control", account_type="ASSET")
        cls.equipment = Account.objects.create(account_code="1500", account_name="Equipment", account_type="ASSET")
        
        cls.accounts_payable = Account.objects.create(account_code="2100", account_name="AP Control", account_type="LIABILITY")
        cls.bank_loan = Account.objects.create(account_code="2500", account_name="Bank Loan", account_type="LIABILITY")
        
        cls.common_stock = Account.objects.create(account_code="3000", account_name="Common Stock", account_type="EQUITY")
        # Retained Earnings account is usually not directly posted to; its balance is derived.
        # However, some systems might have it for manual adjustments or year-end closing.
        cls.retained_earnings_acc = Account.objects.create(account_code="3100", account_name="Retained Earnings", account_type="EQUITY")

        cls.room_revenue = Account.objects.create(account_code="4000", account_name="Room Revenue", account_type="REVENUE")
        cls.fb_revenue = Account.objects.create(account_code="4100", account_name="F&B Revenue", account_type="REVENUE")
        
        cls.salaries_expense = Account.objects.create(account_code="5000", account_name="Salaries Expense", account_type="EXPENSE")
        cls.rent_expense = Account.objects.create(account_code="5100", account_name="Rent Expense", account_type="EXPENSE")

        # Account with hierarchy for COA model test
        cls.parent_asset = Account.objects.create(account_code="1000", account_name="Current Assets", account_type="ASSET")
        cls.child_asset = Account.objects.create(
            account_code="1001", account_name="Subsidiary Cash", account_type="ASSET",
            parent_account=cls.parent_asset, department_code="FIN", sub_department_code="TREASURY"
        )

        # Journal Entries and Transactions
        # For simplicity, creating one JE per major event/test case focus.
        # All amounts are Decimal.

        # --- Transactions for Current Period (t_minus_1_month to today) ---
        # Revenue & Cash Collection
        je1_revenue = JournalEntry.objects.create(entry_date=cls.t_minus_1_month, description="Room revenue collected", status="POSTED")
        Transaction.objects.create(journal_entry=je1_revenue, account=cls.cash_main, debit_amount=Decimal("10000.00"), credit_amount=Decimal("0.00"))
        Transaction.objects.create(journal_entry=je1_revenue, account=cls.room_revenue, debit_amount=Decimal("0.00"), credit_amount=Decimal("10000.00"))

        je2_revenue_ar = JournalEntry.objects.create(entry_date=cls.t_minus_1_month, description="F&B revenue on account", status="POSTED")
        Transaction.objects.create(journal_entry=je2_revenue_ar, account=cls.accounts_receivable, debit_amount=Decimal("5000.00"), credit_amount=Decimal("0.00"))
        Transaction.objects.create(journal_entry=je2_revenue_ar, account=cls.fb_revenue, debit_amount=Decimal("0.00"), credit_amount=Decimal("5000.00"))
        
        # Expense & Cash Payment
        je3_expense_cash = JournalEntry.objects.create(entry_date=cls.t_minus_1_month, description="Salaries paid", status="POSTED")
        Transaction.objects.create(journal_entry=je3_expense_cash, account=cls.salaries_expense, debit_amount=Decimal("3000.00"), credit_amount=Decimal("0.00"))
        Transaction.objects.create(journal_entry=je3_expense_cash, account=cls.cash_main, debit_amount=Decimal("0.00"), credit_amount=Decimal("3000.00"))

        # Expense & AP
        je4_expense_ap = JournalEntry.objects.create(entry_date=cls.t_minus_1_month, description="Rent expense incurred", status="POSTED")
        Transaction.objects.create(journal_entry=je4_expense_ap, account=cls.rent_expense, debit_amount=Decimal("2000.00"), credit_amount=Decimal("0.00"))
        Transaction.objects.create(journal_entry=je4_expense_ap, account=cls.accounts_payable, debit_amount=Decimal("0.00"), credit_amount=Decimal("2000.00"))

        # --- Transactions for T12 period, but older than current period ---
        # Revenue (12 months ago, to be included in T12)
        je5_old_revenue = JournalEntry.objects.create(entry_date=cls.start_of_t_minus_11_months, description="Old Room Revenue", status="POSTED")
        Transaction.objects.create(journal_entry=je5_old_revenue, account=cls.cash_main, debit_amount=Decimal("12000.00"), credit_amount=Decimal("0.00"))
        Transaction.objects.create(journal_entry=je5_old_revenue, account=cls.room_revenue, debit_amount=Decimal("0.00"), credit_amount=Decimal("12000.00"))
        
        # Expense (12 months ago)
        je6_old_expense = JournalEntry.objects.create(entry_date=cls.start_of_t_minus_11_months, description="Old Salaries", status="POSTED")
        Transaction.objects.create(journal_entry=je6_old_expense, account=cls.salaries_expense, debit_amount=Decimal("2500.00"), credit_amount=Decimal("0.00"))
        Transaction.objects.create(journal_entry=je6_old_expense, account=cls.cash_main, debit_amount=Decimal("0.00"), credit_amount=Decimal("2500.00"))

        # --- Transactions older than T12 (e.g., 13 months ago) for beginning balances ---
        je7_ancient_cash_setup = JournalEntry.objects.create(entry_date=cls.t_minus_13_months, description="Initial Cash for period start", status="POSTED")
        Transaction.objects.create(journal_entry=je7_ancient_cash_setup, account=cls.cash_main, debit_amount=Decimal("50000.00"), credit_amount=Decimal("0.00"))
        Transaction.objects.create(journal_entry=je7_ancient_cash_setup, account=cls.common_stock, debit_amount=Decimal("0.00"), credit_amount=Decimal("50000.00")) # Offset with equity

        je8_ancient_ar_setup = JournalEntry.objects.create(entry_date=cls.t_minus_13_months, description="Initial AR for period start", status="POSTED")
        Transaction.objects.create(journal_entry=je8_ancient_ar_setup, account=cls.accounts_receivable, debit_amount=Decimal("1000.00"), credit_amount=Decimal("0.00"))
        Transaction.objects.create(journal_entry=je8_ancient_ar_setup, account=cls.room_revenue, debit_amount=Decimal("0.00"), credit_amount=Decimal("1000.00")) # Revenue in distant past

        je9_ancient_ap_setup = JournalEntry.objects.create(entry_date=cls.t_minus_13_months, description="Initial AP for period start", status="POSTED")
        Transaction.objects.create(journal_entry=je9_ancient_ap_setup, account=cls.rent_expense, debit_amount=Decimal("500.00"), credit_amount=Decimal("0.00")) # Expense in distant past
        Transaction.objects.create(journal_entry=je9_ancient_ap_setup, account=cls.accounts_payable, debit_amount=Decimal("0.00"), credit_amount=Decimal("500.00"))
        
        # --- Transactions for Investing/Financing Activities ---
        # Purchase Equipment (Investing) - within current period for Cash Flow test
        je10_buy_equipment = JournalEntry.objects.create(entry_date=cls.t_minus_1_month, description="Buy Equipment", status="POSTED")
        Transaction.objects.create(journal_entry=je10_buy_equipment, account=cls.equipment, debit_amount=Decimal("15000.00"), credit_amount=Decimal("0.00"))
        Transaction.objects.create(journal_entry=je10_buy_equipment, account=cls.cash_main, debit_amount=Decimal("0.00"), credit_amount=Decimal("15000.00"))

        # Take out Loan (Financing) - within current period for Cash Flow test
        je11_take_loan = JournalEntry.objects.create(entry_date=cls.t_minus_1_month, description="Take out Bank Loan", status="POSTED")
        Transaction.objects.create(journal_entry=je11_take_loan, account=cls.cash_main, debit_amount=Decimal("20000.00"), credit_amount=Decimal("0.00"))
        Transaction.objects.create(journal_entry=je11_take_loan, account=cls.bank_loan, debit_amount=Decimal("0.00"), credit_amount=Decimal("20000.00"))
        
        # Journal Entry for Recurring Entry Model Test
        cls.recurring_je_template = JournalEntry.objects.create(
            entry_date=cls.today, description="Monthly Recurring Template", status="DRAFT",
            is_recurring_template=True, recurrence_pattern="MONTHLY", 
            recurrence_start_date=cls.today, next_recurrence_date=cls.today
        )


class TestAccountModel(TestCase):
    def test_create_account_with_hierarchy(self):
        parent = Account.objects.create(account_code="P100", account_name="Parent Asset", account_type="ASSET")
        child = Account.objects.create(
            account_code="C101", account_name="Child Cash", account_type="ASSET",
            parent_account=parent, department_code="FIN", sub_department_code="OPS"
        )
        retrieved_child = Account.objects.get(account_code="C101")
        self.assertEqual(retrieved_child.parent_account, parent)
        self.assertEqual(retrieved_child.department_code, "FIN")
        self.assertEqual(retrieved_child.sub_department_code, "OPS")

class TestJournalEntryModel(TestCase):
    def test_create_recurring_journal_entry(self):
        today = timezone.now().date()
        je = JournalEntry.objects.create(
            entry_date=today, description="Test Recurring JE", status="DRAFT",
            is_recurring_template=True,
            recurrence_pattern="WEEKLY",
            recurrence_start_date=today,
            recurrence_end_date=today + relativedelta(months=3),
            next_recurrence_date=today
        )
        retrieved_je = JournalEntry.objects.get(pk=je.pk)
        self.assertTrue(retrieved_je.is_recurring_template)
        self.assertEqual(retrieved_je.recurrence_pattern, "WEEKLY")
        self.assertEqual(retrieved_je.recurrence_start_date, today)


class TestIncomeStatementAPI(BaseReportTestCase):
    def test_get_income_statement_success(self):
        url = reverse('income-statement')
        start_date = self.t_minus_1_month.strftime('%Y-%m-%d')
        end_date = self.today.strftime('%Y-%m-%d')
        response = self.client.get(url, {'start_date': start_date, 'end_date': end_date})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['start_date'], parse_date(start_date)) # response.data already a date object
        self.assertEqual(response.data['end_date'], parse_date(end_date)) # response.data already a date object
        
        # Expected calculations for t_minus_1_month to today:
        # Room Revenue: 10000, F&B Revenue: 5000 => Total Revenue = 15000
        # Salaries: 3000, Rent: 2000 => Total Expenses = 5000
        # Net Income = 15000 - 5000 = 10000
        self.assertEqual(Decimal(response.data['total_revenue']), Decimal("15000.00"))
        self.assertEqual(Decimal(response.data['total_expenses']), Decimal("5000.00"))
        self.assertEqual(Decimal(response.data['net_income']), Decimal("10000.00"))
        self.assertTrue(len(response.data['revenue_accounts']) > 0)
        self.assertTrue(len(response.data['expense_accounts']) > 0)

    def test_get_income_statement_invalid_dates(self):
        url = reverse('income-statement')
        response = self.client.get(url, {'start_date': 'invalid-date', 'end_date': self.today.strftime('%Y-%m-%d')})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(url, {'start_date': self.today.strftime('%Y-%m-%d')}) # Missing end_date
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class TestT12IncomeStatementAPI(BaseReportTestCase):
    def test_get_t12_income_statement_with_end_date(self):
        url = reverse('t12-income-statement')
        end_date_param = self.today.strftime('%Y-%m-%d')
        response = self.client.get(url, {'end_date': end_date_param})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        expected_end_date = self.today
        expected_start_date = (expected_end_date - relativedelta(months=11)).replace(day=1)
        
        self.assertEqual(response.data['end_date'], expected_end_date) # response.data already a date object
        self.assertEqual(response.data['start_date'], expected_start_date) # response.data already a date object

        # Expected calculations for T12 period (start_of_t_minus_11_months to today):
        # Current Period Revenue: 15000, Current Period Expenses: 5000
        # Old Revenue (at start_of_t_minus_11_months): 12000
        # Old Salaries (at start_of_t_minus_11_months): 2500
        # Total Revenue = 15000 + 12000 = 27000
        # Total Expenses = 5000 + 2500 = 7500
        # Net Income = 27000 - 7500 = 19500
        self.assertEqual(Decimal(response.data['total_revenue']), Decimal("27000.00"))
        self.assertEqual(Decimal(response.data['total_expenses']), Decimal("7500.00"))
        self.assertEqual(Decimal(response.data['net_income']), Decimal("19500.00"))

    def test_get_t12_income_statement_default_end_date(self):
        url = reverse('t12-income-statement')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['end_date'], self.today) # response.data already a date object, Default to today

class TestBalanceSheetAPI(BaseReportTestCase):
    def test_get_balance_sheet_success(self):
        url = reverse('balance-sheet')
        as_of_date_str = self.today.strftime('%Y-%m-%d')
        response = self.client.get(url, {'as_of_date': as_of_date_str})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['as_of_date'], parse_date(as_of_date_str)) # response.data already a date object

        # Simplified Balance Calculation (as of self.today)
        # Initial Cash: 50000
        # Revenue Cash: +10000 (JE1) +12000 (JE5) = +22000
        # Expense Cash: -3000 (JE3) -2500 (JE6) = -5500
        # Equipment Purchase: -15000 (JE10)
        # Loan: +20000 (JE11)
        # Cash = 50000 + 22000 - 5500 - 15000 + 20000 = 71500
        # AR: Initial 1000 (JE8) + 5000 (JE2) = 6000
        # Equipment: 15000 (JE10)
        # Total Assets = 71500 (Cash) + 6000 (AR) + 15000 (Equipment) = 92500

        # AP: Initial 500 (JE9) + 2000 (JE4) = 2500
        # Bank Loan: 20000 (JE11)
        # Total Liabilities = 2500 + 20000 = 22500
        
        # Common Stock: 50000 (JE7)
        # Retained Earnings Calculation (all time up to self.today):
        # Historic Revenue (JE8): 1000
        # Historic Expense (JE9): 500
        # T12 Revenue (JE1, JE2, JE5): 10000 + 5000 + 12000 = 27000
        # T12 Expense (JE3, JE4, JE6): 3000 + 2000 + 2500 = 7500
        # Total Historic Revenue = 1000 + 27000 = 28000
        # Total Historic Expenses = 500 + 7500 = 8000
        # Retained Earnings = 28000 - 8000 = 20000
        # Total Equity = 50000 (Common Stock) + 20000 (Retained Earnings) = 70000
        # Total Liabilities & Equity = 22500 + 70000 = 92500

        self.assertEqual(Decimal(response.data['total_assets']), Decimal("92500.00"))
        self.assertEqual(Decimal(response.data['total_liabilities']), Decimal("22500.00"))
        self.assertEqual(Decimal(response.data['retained_earnings']), Decimal("20000.00"))
        self.assertEqual(Decimal(response.data['total_equity']), Decimal("70000.00"))
        self.assertEqual(Decimal(response.data['total_liabilities_and_equity']), Decimal("92500.00"))
        self.assertEqual(Decimal(response.data['total_assets']), Decimal(response.data['total_liabilities_and_equity']))

    def test_get_balance_sheet_invalid_date(self):
        url = reverse('balance-sheet')
        response = self.client.get(url) # Missing as_of_date
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class TestCashFlowStatementAPI(BaseReportTestCase):
    def test_get_cash_flow_statement_success(self):
        url = reverse('cash-flow-statement')
        # Use a period covering JE1, JE2, JE3, JE4, JE10, JE11
        # Start date: day before t_minus_1_month
        # End date: t_minus_1_month (to capture only those JEs for simpler calc)
        # Or more simply, define a clear period like the last month.
        # For this test, let's use from t_minus_2_months to t_minus_1_month to isolate current period activity
        
        start_date = self.t_minus_2_months.strftime('%Y-%m-%d') # A date before JE1, JE2 etc.
        end_date = self.t_minus_1_month.strftime('%Y-%m-%d') # Date of JE1, JE2 etc.
        
        response = self.client.get(url, {'start_date': start_date, 'end_date': end_date})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Net Income for period t_minus_2_months to t_minus_1_month
        # Revenue (JE1, JE2): 10000 + 5000 = 15000
        # Expenses (JE3, JE4): 3000 + 2000 = 5000
        # Net Income = 10000
        self.assertEqual(Decimal(response.data['net_income']), Decimal("10000.00"))

        # Cash at Beginning: (Cash from JE7: 50000) + (Cash from JE5: 12000) - (Cash from JE6: 2500)
        # = 50000 + 12000 - 2500 = 59500 (Cash before t_minus_2_months, using start_of_t_minus_11_months as a proxy if it's older)
        # For simplicity, let's trace cash only based on setup.
        # Cash before start_date (t_minus_2_months):
        # JE7 (+50000), JE5 (+12000), JE6 (-2500) = 59500
        # This needs _get_cash_accounts_balance to be accurate based on dates.
        # View uses account_code "1010" and "1020" etc. for cash.
        # Cash from JE7: 50000 to 1010 at t_minus_13_months
        # Cash from JE5: 12000 to 1010 at start_of_t_minus_11_months
        # Cash from JE6: -2500 from 1010 at start_of_t_minus_11_months
        # Balance of 1010 before t_minus_2_months = 50000 + 12000 - 2500 = 59500
        self.assertEqual(Decimal(response.data['cash_at_beginning_of_period']), Decimal("59500.00"))

        # Cash at End of Period (t_minus_1_month):
        # Beginning Cash: 59500
        # JE1: +10000
        # JE3: -3000
        # JE10 (Equipment): -15000
        # JE11 (Loan): +20000
        # Cash at end = 59500 + 10000 - 3000 - 15000 + 20000 = 71500
        self.assertEqual(Decimal(response.data['cash_at_end_of_period']), Decimal("71500.00"))
        self.assertEqual(Decimal(response.data['net_change_in_cash']), Decimal("12000.00")) # 71500 - 59500

        # Operating Activities:
        # Net Income: 10000
        # Change in AR (1200): (JE2: +5000 for period). AR Before period (JE8: +1000).
        # AR at t_minus_2_months (before period): 1000
        # AR at t_minus_1_month (end of period): 1000 + 5000 = 6000
        # Increase in AR = 5000. Cash Flow Adj = -5000
        # Change in AP (2100): (JE4: +2000 for period). AP Before period (JE9: +500)
        # AP at t_minus_2_months (before period): 500
        # AP at t_minus_1_month (end of period): 500 + 2000 = 2500
        # Increase in AP = 2000. Cash Flow Adj = +2000
        # Net Cash from Ops = 10000 - 5000 + 2000 = 7000
        self.assertEqual(Decimal(response.data['net_cash_from_operating_activities']), Decimal("7000.00"))
        
        # Investing Activities:
        # Change in Equipment (1500): JE10: +15000. Cash Flow Adj = -15000
        self.assertEqual(Decimal(response.data['net_cash_from_investing_activities']), Decimal("-15000.00"))

        # Financing Activities:
        # Change in Loan (2500): JE11: +20000. Cash Flow Adj = +20000
        self.assertEqual(Decimal(response.data['net_cash_from_financing_activities']), Decimal("20000.00"))

        # Check reconciliation: 7000 (Ops) - 15000 (Inv) + 20000 (Fin) = 12000. Matches Net Change in Cash.

    def test_get_cash_flow_statement_invalid_dates(self):
        url = reverse('cash-flow-statement')
        response = self.client.get(url, {'start_date': 'invalid-date'}) # Missing end_date & invalid
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

# Helper to parse dates from response if needed, though direct comparison works if format is exact
# Removed redundant parse_date_from_response as parse_date from django.utils.dateparse is used directly.

class PurchaseOrderAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vendor = Vendor.objects.create(name="Test Vendor Inc.")
        cls.expense_account = Account.objects.create(account_code="6000", account_name="Test Expense Account", account_type="EXPENSE")
        cls.today = timezone.now().date()

        # Sample Purchase Order for use in multiple tests
        cls.po1 = PurchaseOrder.objects.create(
            po_number="PO001",
            vendor=cls.vendor,
            order_date=cls.today,
            status=PurchaseOrder.DRAFT,
            total_amount=Decimal("0.00") # Will be updated by line items if created directly
        )
        cls.po1_line1 = PurchaseOrderLineItem.objects.create(
            purchase_order=cls.po1,
            item_description="Test Item 1",
            quantity=Decimal("2.00"),
            unit_price=Decimal("50.00"),
            account=cls.expense_account
        ) # total_price = 100.00
        cls.po1.total_amount = cls.po1_line1.total_price # Manually update PO total for this direct model creation
        cls.po1.save()


    def test_create_purchase_order_model(self):
        po = PurchaseOrder.objects.create(
            po_number="PO002",
            vendor=self.vendor,
            order_date=self.today,
            status=PurchaseOrder.PENDING_APPROVAL,
            total_amount=Decimal("150.00")
        )
        self.assertEqual(PurchaseOrder.objects.count(), 2) # po1 + po
        self.assertEqual(po.po_number, "PO002")

    def test_create_purchase_order_line_item_model(self):
        po_for_line_test = PurchaseOrder.objects.create(
            po_number="PO-LINETEST", vendor=self.vendor, order_date=self.today
        )
        line_item = PurchaseOrderLineItem.objects.create(
            purchase_order=po_for_line_test,
            item_description="Widget A",
            quantity=Decimal("10.00"),
            unit_price=Decimal("5.50"),
            account=self.expense_account
        )
        self.assertEqual(line_item.total_price, Decimal("55.00")) # 10 * 5.50
        self.assertEqual(po_for_line_test.line_items.count(), 1)
        self.assertEqual(po_for_line_test.line_items.first(), line_item)

    def _get_sample_po_payload(self, po_number="PO-API-TEST"):
        return {
            "po_number": po_number,
            "vendor": self.vendor.id,
            "order_date": self.today.strftime('%Y-%m-%d'),
            "line_items": [
                {
                    "item_description": "API Item 1",
                    "quantity": "3.00",
                    "unit_price": "25.00", # Total 75.00
                    "account": self.expense_account.id
                },
                {
                    "item_description": "API Item 2",
                    "quantity": "1.00",
                    "unit_price": "125.00", # Total 125.00
                    "account": self.expense_account.id
                }
            ]
            # total_amount is read-only, should be calculated by serializer
        }

    def test_create_purchase_order_via_api_valid(self):
        url = reverse('purchaseorder-list') # DefaultRouter generates basename-list
        payload = self._get_sample_po_payload()
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PurchaseOrder.objects.count(), 2) # po1 + this new one
        
        created_po = PurchaseOrder.objects.get(po_number="PO-API-TEST")
        self.assertEqual(created_po.vendor, self.vendor)
        self.assertEqual(created_po.line_items.count(), 2)
        # Expected total: (3 * 25) + (1 * 125) = 75 + 125 = 200
        self.assertEqual(created_po.total_amount, Decimal("200.00"))
        self.assertEqual(response.data['total_amount'], "200.00")

    def test_create_purchase_order_api_no_line_items(self):
        url = reverse('purchaseorder-list')
        payload = self._get_sample_po_payload()
        payload.pop("line_items") # Remove line items
        
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("line_items", response.data) # Check if error is related to line_items


    def test_list_purchase_orders_api(self):
        url = reverse('purchaseorder-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1) # Only po1 created in setUpTestData
        self.assertEqual(response.data[0]['po_number'], self.po1.po_number)

    def test_retrieve_purchase_order_api(self):
        url = reverse('purchaseorder-detail', kwargs={'pk': self.po1.pk})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['po_number'], self.po1.po_number)
        self.assertEqual(len(response.data['line_items']), 1)
        self.assertEqual(Decimal(response.data['total_amount']), self.po1.total_amount)

    def test_approve_purchase_order_action(self):
        url = reverse('purchaseorder-approve', kwargs={'pk': self.po1.pk})
        self.assertEqual(self.po1.status, PurchaseOrder.DRAFT) # Initial state
        
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.po1.refresh_from_db()
        self.assertEqual(self.po1.status, PurchaseOrder.APPROVED)
        
        # Try to approve again (should fail or do nothing gracefully)
        response_already_approved = self.client.post(url, format='json')
        self.assertEqual(response_already_approved.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response_already_approved.data)


    def test_cancel_purchase_order_action(self):
        # First approve it to test cancellation from APPROVED state
        self.po1.status = PurchaseOrder.APPROVED
        self.po1.save()

        url = reverse('purchaseorder-cancel', kwargs={'pk': self.po1.pk})
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.po1.refresh_from_db()
        self.assertEqual(self.po1.status, PurchaseOrder.CANCELLED)

        # Try to cancel a DRAFT PO
        draft_po = PurchaseOrder.objects.create(po_number="PO-DRAFT-CANCEL", vendor=self.vendor, order_date=self.today, status=PurchaseOrder.DRAFT)
        url_draft_cancel = reverse('purchaseorder-cancel', kwargs={'pk': draft_po.pk})
        response_draft = self.client.post(url_draft_cancel, format='json')
        self.assertEqual(response_draft.status_code, status.HTTP_200_OK)
        draft_po.refresh_from_db()
        self.assertEqual(draft_po.status, PurchaseOrder.CANCELLED)

        # Try to cancel an already cancelled PO
        response_already_cancelled = self.client.post(url, format='json')
        self.assertEqual(response_already_cancelled.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response_already_cancelled.data)


    def test_receive_purchase_order_action(self):
        self.po1.status = PurchaseOrder.APPROVED # Set to approved first
        self.po1.save()
        
        url = reverse('purchaseorder-receive', kwargs={'pk': self.po1.pk})
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.po1.refresh_from_db()
        self.assertEqual(self.po1.status, PurchaseOrder.RECEIVED)
        self.assertIn("placeholder", response.data['status'].lower()) # Check for placeholder message

        # Try to receive a DRAFT PO (invalid)
        draft_po = PurchaseOrder.objects.create(po_number="PO-DRAFT-RECEIVE", vendor=self.vendor, order_date=self.today, status=PurchaseOrder.DRAFT)
        url_draft_receive = reverse('purchaseorder-receive', kwargs={'pk': draft_po.pk})
        response_draft = self.client.post(url_draft_receive, format='json')
        self.assertEqual(response_draft.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response_draft.data)

        # Try to receive an already received PO
        response_already_received = self.client.post(url, format='json')
        # Assuming receiving a fully received PO might be idempotent or lead to partial logic in future,
        # but for now, the view only allows from APPROVED or PARTIALLY_RECEIVED.
        # If it's already RECEIVED, it should be an error based on current view logic.
        self.assertEqual(response_already_received.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response_already_received.data)


# Tests for Recurring Journal Entries

from ledger.management.commands.process_recurring_journal_entries import calculate_next_recurrence_date
from django.core.management import call_command
from io import StringIO

class TestCalculateNextRecurrenceDate(TestCase):
    def test_daily_pattern(self):
        current = datetime.date(2023, 1, 1)
        expected = datetime.date(2023, 1, 2)
        self.assertEqual(calculate_next_recurrence_date(current, 'DAILY', None), expected)

    def test_weekly_pattern(self):
        current = datetime.date(2023, 1, 1)
        expected = datetime.date(2023, 1, 8)
        self.assertEqual(calculate_next_recurrence_date(current, 'WEEKLY', None), expected)

    def test_monthly_pattern_mid_month(self):
        current = datetime.date(2023, 1, 15)
        expected = datetime.date(2023, 2, 15)
        self.assertEqual(calculate_next_recurrence_date(current, 'MONTHLY', None), expected)

    def test_monthly_pattern_end_of_month_to_shorter_month(self):
        current = datetime.date(2023, 1, 31)
        expected = datetime.date(2023, 2, 28) # Non-leap year
        self.assertEqual(calculate_next_recurrence_date(current, 'MONTHLY', None), expected)
    
    def test_monthly_pattern_end_of_month_to_longer_month_from_short(self):
        current = datetime.date(2023, 2, 28) # Non-leap year
        expected = datetime.date(2023, 3, 28) # relativedelta aims for same day
        # If specific end-of-month logic is desired (e.g. Feb 28 -> Mar 31), it's not default for relativedelta.
        # The current implementation of calculate_next_recurrence_date uses simple relativedelta(months=1)
        # which for Feb 28, 2023 would give Mar 28, 2023.
        # If the requirement were Feb 28 -> Mar 31, the function would need more complex logic.
        # For now, testing existing behavior.
        self.assertEqual(calculate_next_recurrence_date(current, 'MONTHLY', None), expected)

    def test_monthly_pattern_leap_year_feb_29_to_mar(self):
        current = datetime.date(2024, 2, 29) # Leap year
        expected = datetime.date(2024, 3, 29) # relativedelta aims for same day.
        self.assertEqual(calculate_next_recurrence_date(current, 'MONTHLY', None), expected)

    def test_quarterly_pattern(self):
        current = datetime.date(2023, 1, 15)
        expected = datetime.date(2023, 4, 15)
        self.assertEqual(calculate_next_recurrence_date(current, 'QUARTERLY', None), expected)
        current = datetime.date(2023, 11, 30)
        expected = datetime.date(2024, 2, 29) # Jumps to Feb 29 in a leap year
        self.assertEqual(calculate_next_recurrence_date(current, 'QUARTERLY', None), expected)


    def test_annually_pattern_simple(self):
        current = datetime.date(2023, 3, 1)
        expected = datetime.date(2024, 3, 1)
        self.assertEqual(calculate_next_recurrence_date(current, 'ANNUALLY', None), expected)

    def test_annually_pattern_leap_year_handling(self):
        # Feb 29 in a leap year to next year (non-leap)
        current_leap = datetime.date(2024, 2, 29)
        expected_non_leap = datetime.date(2025, 2, 28)
        self.assertEqual(calculate_next_recurrence_date(current_leap, 'ANNUALLY', None), expected_non_leap)
        
        # From Feb 28 in a non-leap year, preceding a leap year
        current_non_leap_to_leap = datetime.date(2023, 2, 28)
        expected_leap_from_non_leap = datetime.date(2024, 2, 28) # Stays on 28th
        self.assertEqual(calculate_next_recurrence_date(current_non_leap_to_leap, 'ANNUALLY', None), expected_leap_from_non_leap)


    def test_recurrence_end_date_before(self):
        current = datetime.date(2023, 1, 1)
        end_date = datetime.date(2023, 1, 10)
        expected = datetime.date(2023, 1, 2)
        self.assertEqual(calculate_next_recurrence_date(current, 'DAILY', end_date), expected)

    def test_recurrence_end_date_exact(self):
        current = datetime.date(2023, 1, 9)
        end_date = datetime.date(2023, 1, 10)
        expected = datetime.date(2023, 1, 10)
        self.assertEqual(calculate_next_recurrence_date(current, 'DAILY', end_date), expected)

    def test_recurrence_end_date_after(self):
        current = datetime.date(2023, 1, 10)
        end_date = datetime.date(2023, 1, 10)
        # Next calculated date (2023-01-11) is after end_date (2023-01-10)
        self.assertIsNone(calculate_next_recurrence_date(current, 'DAILY', end_date))

    def test_recurrence_end_date_none(self):
        current = datetime.date(2023, 1, 1)
        expected = datetime.date(2023, 1, 2)
        self.assertEqual(calculate_next_recurrence_date(current, 'DAILY', None), expected)
        
    def test_unknown_pattern(self):
        current = datetime.date(2023, 1, 1)
        self.assertIsNone(calculate_next_recurrence_date(current, 'INVALID_PATTERN', None))


class TestProcessRecurringJournalEntries(APITestCase): # Using APITestCase for potential future API interactions / consistency
    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.now().date()
        cls.debit_account = Account.objects.create(account_code="D100", account_name="Test Debit Acc", account_type="EXPENSE")
        cls.credit_account = Account.objects.create(account_code="C100", account_name="Test Credit Acc", account_type="ASSET")

    def setUp(self):
        # Clean up JournalEntry and Transaction before each test method to ensure isolation
        JournalEntry.objects.all().delete()
        Transaction.objects.all().delete()

        # Common template setup, can be overridden in specific tests
        self.template1 = JournalEntry.objects.create(
            description="Monthly Rent Template",
            status='POSTED',
            is_recurring_template=True,
            recurrence_pattern='MONTHLY',
            recurrence_start_date=self.today - relativedelta(months=2),
            next_recurrence_date=self.today
        )
        Transaction.objects.create(journal_entry=self.template1, account=self.debit_account, debit_amount=Decimal("100.00"))
        Transaction.objects.create(journal_entry=self.template1, account=self.credit_account, credit_amount=Decimal("100.00"))

    def test_no_due_templates(self):
        # Modify template1 so it's not due today
        self.template1.next_recurrence_date = self.today + relativedelta(days=1)
        self.template1.save()
        
        out = StringIO()
        call_command('process_recurring_journal_entries', stdout=out)
        
        self.assertIn("No active recurring journal entry templates are due today.", out.getvalue())
        # Count should be 1 (only the template itself)
        self.assertEqual(JournalEntry.objects.count(), 1)


    def test_one_daily_template_due(self):
        self.template1.recurrence_pattern = 'DAILY'
        self.template1.next_recurrence_date = self.today # Ensure it's due today
        self.template1.save()

        out = StringIO()
        call_command('process_recurring_journal_entries', stdout=out)

        self.assertEqual(JournalEntry.objects.filter(is_recurring_template=False).count(), 1)
        new_je = JournalEntry.objects.get(is_recurring_template=False, description__icontains=self.template1.description)
        
        self.assertEqual(new_je.entry_date, self.today)
        self.assertEqual(new_je.status, 'PENDING')
        self.assertEqual(new_je.transactions.count(), 2) # Check copied transactions
        
        self.template1.refresh_from_db()
        self.assertEqual(self.template1.next_recurrence_date, self.today + relativedelta(days=1))
        self.assertIn(f"Successfully generated Journal Entry ID {new_je.id}", out.getvalue())

    def test_one_monthly_template_due(self):
        # template1 is already set up as monthly and due today in setUp
        out = StringIO()
        call_command('process_recurring_journal_entries', stdout=out)

        self.assertEqual(JournalEntry.objects.filter(is_recurring_template=False).count(), 1)
        new_je = JournalEntry.objects.get(is_recurring_template=False)
        
        self.assertEqual(new_je.entry_date, self.today)
        self.template1.refresh_from_db()
        self.assertEqual(self.template1.next_recurrence_date, self.today + relativedelta(months=1))
        self.assertIn(f"Successfully generated Journal Entry ID {new_je.id}", out.getvalue())

    def test_template_reaches_recurrence_end_date(self):
        self.template1.next_recurrence_date = self.today
        # Set end_date so that next calculated date is after it
        self.template1.recurrence_end_date = self.today + relativedelta(days=15) # e.g. if monthly
        # If pattern is monthly, next date will be today + 1 month, which is > today + 15 days
        self.template1.save()

        out = StringIO()
        call_command('process_recurring_journal_entries', stdout=out)
        
        self.assertEqual(JournalEntry.objects.filter(is_recurring_template=False).count(), 1)
        new_je = JournalEntry.objects.get(is_recurring_template=False)
        self.assertEqual(new_je.entry_date, self.today)

        self.template1.refresh_from_db()
        self.assertIsNone(self.template1.next_recurrence_date)
        self.assertIn("has reached its recurrence end date", out.getvalue())


    def test_template_with_recurrence_end_date_equals_next_recurrence_date(self):
        self.template1.next_recurrence_date = self.today
        self.template1.recurrence_end_date = self.today # End date is today
        self.template1.save()

        out = StringIO()
        call_command('process_recurring_journal_entries', stdout=out)

        self.assertEqual(JournalEntry.objects.filter(is_recurring_template=False).count(), 1)
        new_je = JournalEntry.objects.get(is_recurring_template=False)
        self.assertEqual(new_je.entry_date, self.today)

        self.template1.refresh_from_db()
        self.assertIsNone(self.template1.next_recurrence_date)
        self.assertIn("has reached its recurrence end date", out.getvalue())


    def test_template_with_next_recurrence_date_in_past(self):
        past_date = self.today - relativedelta(days=3)
        self.template1.next_recurrence_date = past_date
        self.template1.recurrence_pattern = 'DAILY' # easier to test catch-up
        self.template1.save()

        out = StringIO()
        # Running it once should process the oldest due date
        call_command('process_recurring_journal_entries', stdout=out)
        
        self.assertEqual(JournalEntry.objects.filter(is_recurring_template=False).count(), 1)
        new_je = JournalEntry.objects.get(is_recurring_template=False)
        self.assertEqual(new_je.entry_date, past_date) # JE created for the past due date

        self.template1.refresh_from_db()
        self.assertEqual(self.template1.next_recurrence_date, past_date + relativedelta(days=1))
        self.assertIn(f"Successfully generated Journal Entry ID {new_je.id} for date {past_date}", out.getvalue())
        
        # If we run it again, it should process the next one (past_date + 1 day)
        # This tests the loop or multiple runs of the command for catch-up
        # For this test, one run processes one past due item.
        # A full catch-up loop isn't in the current command, it processes based on "next_recurrence_date <= today"

    def test_template_status_not_posted(self):
        self.template1.status = 'DRAFT'
        self.template1.save()
        
        out = StringIO()
        call_command('process_recurring_journal_entries', stdout=out)
        self.assertIn("No active recurring journal entry templates are due today.", out.getvalue())
        self.assertEqual(JournalEntry.objects.filter(is_recurring_template=False).count(), 0)


    def test_template_is_not_recurring_template(self):
        self.template1.is_recurring_template = False
        self.template1.save()

        out = StringIO()
        call_command('process_recurring_journal_entries', stdout=out)
        self.assertIn("No active recurring journal entry templates are due today.", out.getvalue())
        self.assertEqual(JournalEntry.objects.filter(is_recurring_template=False).count(), 0)
        
    def test_command_output_logging(self):
        out = StringIO()
        err = StringIO()
        call_command('process_recurring_journal_entries', stdout=out, stderr=err)
        
        output = out.getvalue()
        self.assertIn("Starting to process recurring journal entries...", output)
        # Based on setUp, template1 is due
        self.assertIn(f"Processing template ID {self.template1.id}", output)
        self.assertIn("Successfully generated Journal Entry ID", output) # Dynamic ID
        self.assertIn(f"Updated next recurrence date for template ID {self.template1.id}", output)
        self.assertIn("Finished processing recurring journal entries.", output)
        self.assertEqual(err.getvalue(), "") # No errors expected

    # Simulating error during processing one template is complex and might require mocking.
    # For now, focusing on the standard paths.
    # def test_error_during_processing_one_template(self):
    #     # Setup: Create two templates, one that will cause an error
    #     # e.g., by mocking a .save() to raise an exception on the second template.
    #     # Verify: First template processed, error logged for second, command finishes.
    #     pass
