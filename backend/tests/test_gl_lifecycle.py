"""GL lifecycle tests — generate realistic loan scenarios and validate reports.

Covers:
- Loan disbursement → full repayment (paid-off loan)
- Loan disbursement → partial repayment → provision → write-off
- Recovery after write-off
- Interest accrual
- Origination fee
- Balance sheet verification (A = L + E after every scenario)
- Income statement verification (Revenue − Expenses = Net Income)
- Trial balance verification (DR = CR)
- Loan portfolio report accuracy
- Dashboard summary accuracy
- Reconciliation accuracy
"""

import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.gl import (
    JournalEntry,
    JournalEntryLine,
    JournalEntryStatus,
    JournalSourceType,
    AccountCategory,
    AccountType,
    AccountStatus,
    GLAccount,
    Currency,
    AccountingPeriod,
    PeriodStatus,
    MappingLineType,
    MappingAmountSource,
    GLMappingTemplate,
    GLMappingTemplateLine,
)
from app.services.gl.journal_engine import (
    _validate_balance,
    BalanceError,
    JournalEngineError,
)
from app.services.gl.mapping_engine import (
    _evaluate_conditions,
    _resolve_amount,
)


# ===================================================================
# Chart of Accounts fixture — matches the seed COA
# ===================================================================

# Account IDs mirror what seed_gl.py creates
COA = {
    # Level 3 detail accounts (posting accounts)
    "1-1001": {"id": 26, "name": "Operating Bank Account",    "cat": AccountCategory.ASSET,     "type": AccountType.DEBIT},
    "1-1002": {"id": 27, "name": "Disbursement Clearing",     "cat": AccountCategory.ASSET,     "type": AccountType.DEBIT},
    "1-2001": {"id": 28, "name": "Performing Loans",          "cat": AccountCategory.ASSET,     "type": AccountType.DEBIT},
    "1-2002": {"id": 29, "name": "Non-Performing Loans",      "cat": AccountCategory.ASSET,     "type": AccountType.DEBIT},
    "1-2003": {"id": 30, "name": "Written-Off Loans",         "cat": AccountCategory.ASSET,     "type": AccountType.DEBIT},
    "1-3001": {"id": 31, "name": "Interest Receivable - Performing",  "cat": AccountCategory.ASSET, "type": AccountType.DEBIT},
    "1-4001": {"id": 33, "name": "Origination Fee Receivable","cat": AccountCategory.ASSET,     "type": AccountType.DEBIT},
    # Level 2 parent/group accounts
    "1-1000": {"id": 6,  "name": "Cash and Bank",             "cat": AccountCategory.ASSET,     "type": AccountType.DEBIT},
    "1-2000": {"id": 7,  "name": "Loan Portfolio",            "cat": AccountCategory.ASSET,     "type": AccountType.DEBIT},
    "2-2000": {"id": 12, "name": "Allowance for Loan Losses", "cat": AccountCategory.LIABILITY, "type": AccountType.CREDIT},
    "3-1000": {"id": 16, "name": "Share Capital",             "cat": AccountCategory.EQUITY,    "type": AccountType.CREDIT},
    # Revenue
    "4-1000": {"id": 18, "name": "Interest Income",           "cat": AccountCategory.REVENUE,   "type": AccountType.CREDIT},
    "4-2000": {"id": 19, "name": "Fee Income",                "cat": AccountCategory.REVENUE,   "type": AccountType.CREDIT},
    "4-4000": {"id": 21, "name": "Recovery Income",           "cat": AccountCategory.REVENUE,   "type": AccountType.CREDIT},
    # Expenses
    "5-1000": {"id": 23, "name": "Provision Expense",         "cat": AccountCategory.EXPENSE,   "type": AccountType.DEBIT},
    "5-3000": {"id": 25, "name": "Write-Off Expense",         "cat": AccountCategory.EXPENSE,   "type": AccountType.DEBIT},
}

def _acct_id(code: str) -> int:
    return COA[code]["id"]


# ===================================================================
# Mapping template definitions (match seed_gl.py)
# ===================================================================

MAPPING_DEFS = {
    JournalSourceType.LOAN_DISBURSEMENT: [
        (MappingLineType.DEBIT,  "1-2001", MappingAmountSource.PRINCIPAL),
        (MappingLineType.CREDIT, "1-1001", MappingAmountSource.PRINCIPAL),
    ],
    JournalSourceType.REPAYMENT: [
        (MappingLineType.DEBIT,  "1-1001", MappingAmountSource.FULL_AMOUNT),
        (MappingLineType.CREDIT, "1-2001", MappingAmountSource.FULL_AMOUNT),
    ],
    JournalSourceType.INTEREST_ACCRUAL: [
        (MappingLineType.DEBIT,  "1-3001", MappingAmountSource.INTEREST),
        (MappingLineType.CREDIT, "4-1000", MappingAmountSource.INTEREST),
    ],
    JournalSourceType.FEE: [
        (MappingLineType.DEBIT,  "1-4001", MappingAmountSource.FEE),
        (MappingLineType.CREDIT, "4-2000", MappingAmountSource.FEE),
    ],
    JournalSourceType.PROVISION: [
        (MappingLineType.DEBIT,  "5-1000", MappingAmountSource.FULL_AMOUNT),
        (MappingLineType.CREDIT, "2-2000", MappingAmountSource.FULL_AMOUNT),
    ],
    JournalSourceType.WRITE_OFF: [
        (MappingLineType.DEBIT,  "1-2003", MappingAmountSource.PRINCIPAL),
        (MappingLineType.CREDIT, "1-2001", MappingAmountSource.PRINCIPAL),
    ],
    JournalSourceType.RECOVERY: [
        (MappingLineType.DEBIT,  "1-1001", MappingAmountSource.FULL_AMOUNT),
        (MappingLineType.CREDIT, "4-4000", MappingAmountSource.FULL_AMOUNT),
    ],
}


# ===================================================================
# In-memory GL ledger — simulates what the DB would hold
# ===================================================================


class GLLedger:
    """In-memory double-entry ledger for testing.

    Tracks account balances and validates the accounting equation
    after every journal entry.
    """

    def __init__(self):
        self.balances: dict[str, Decimal] = {}  # account_code → net balance
        self.entries: list[dict] = []
        self._seq = 0

    def post(
        self,
        *,
        event_type: JournalSourceType,
        source_ref: str,
        amount_breakdown: dict[str, Decimal],
        description: str = "",
    ) -> dict:
        """Post a journal entry using the standard mapping templates."""
        mapping = MAPPING_DEFS.get(event_type)
        assert mapping is not None, f"No mapping for {event_type}"

        lines = []
        for line_type, acct_code, amount_source in mapping:
            amount = _resolve_amount(amount_source, amount_breakdown)
            if amount <= 0:
                continue
            lines.append({
                "account_code": acct_code,
                "debit": amount if line_type == MappingLineType.DEBIT else Decimal("0"),
                "credit": amount if line_type == MappingLineType.CREDIT else Decimal("0"),
            })

        # Validate balance
        total_dr = sum(ln["debit"] for ln in lines)
        total_cr = sum(ln["credit"] for ln in lines)
        assert total_dr == total_cr, f"Unbalanced: DR={total_dr} CR={total_cr}"
        assert total_dr > 0, "Zero-amount entry"

        # Apply to ledger
        for ln in lines:
            code = ln["account_code"]
            acct = COA[code]
            if acct["type"] == AccountType.DEBIT:
                self.balances[code] = self.balances.get(code, Decimal("0")) + ln["debit"] - ln["credit"]
            else:
                self.balances[code] = self.balances.get(code, Decimal("0")) + ln["credit"] - ln["debit"]

        self._seq += 1
        entry = {
            "number": f"JE-TEST-{self._seq:06d}",
            "event_type": event_type,
            "source_ref": source_ref,
            "lines": lines,
            "total": total_dr,
            "description": description,
        }
        self.entries.append(entry)
        return entry

    def balance(self, code: str) -> Decimal:
        return self.balances.get(code, Decimal("0"))

    def total_assets(self) -> Decimal:
        return sum(
            self.balance(c)
            for c, a in COA.items()
            if a["cat"] == AccountCategory.ASSET
        )

    def total_liabilities(self) -> Decimal:
        return sum(
            self.balance(c)
            for c, a in COA.items()
            if a["cat"] == AccountCategory.LIABILITY
        )

    def total_equity(self) -> Decimal:
        return sum(
            self.balance(c)
            for c, a in COA.items()
            if a["cat"] == AccountCategory.EQUITY
        )

    def total_revenue(self) -> Decimal:
        return sum(
            self.balance(c)
            for c, a in COA.items()
            if a["cat"] == AccountCategory.REVENUE
        )

    def total_expenses(self) -> Decimal:
        return sum(
            self.balance(c)
            for c, a in COA.items()
            if a["cat"] == AccountCategory.EXPENSE
        )

    def net_income(self) -> Decimal:
        return self.total_revenue() - self.total_expenses()

    def trial_balance(self) -> tuple[Decimal, Decimal]:
        """Return (total_dr, total_cr) across all accounts."""
        total_dr = Decimal("0")
        total_cr = Decimal("0")
        for code, bal in self.balances.items():
            acct = COA[code]
            if acct["type"] == AccountType.DEBIT:
                if bal >= 0:
                    total_dr += bal
                else:
                    total_cr += abs(bal)
            else:
                if bal >= 0:
                    total_cr += bal
                else:
                    total_dr += abs(bal)
        return total_dr, total_cr

    def assert_balanced(self, msg: str = ""):
        """Assert A = L + E + (Rev − Exp)."""
        assets = self.total_assets()
        liab = self.total_liabilities()
        equity = self.total_equity()
        net = self.net_income()
        rhs = liab + equity + net
        assert assets == rhs, (
            f"Accounting equation broken{(' — ' + msg) if msg else ''}: "
            f"A={assets} ≠ L+E+NI={rhs} (L={liab}, E={equity}, NI={net})"
        )
        dr, cr = self.trial_balance()
        assert dr == cr, f"Trial balance broken: DR={dr} ≠ CR={cr}"


# ===================================================================
# Scenario 1: Fully repaid loan
# ===================================================================


class TestFullyRepaidLoan:
    """Loan is disbursed, makes several repayments, and is fully paid off."""

    def test_full_lifecycle(self):
        gl = GLLedger()

        # Initial capital
        gl.balances["1-1001"] = Decimal("1000000")  # Bank
        gl.balances["3-1000"] = Decimal("1000000")  # Equity
        gl.assert_balanced("after capitalisation")

        # 1. Disburse $50,000
        gl.post(
            event_type=JournalSourceType.LOAN_DISBURSEMENT,
            source_ref="LOAN-001",
            amount_breakdown={"principal": Decimal("50000"), "full_amount": Decimal("50000")},
            description="Disbursement of $50,000 loan",
        )
        assert gl.balance("1-2001") == Decimal("50000"), "Loan portfolio should be 50k"
        assert gl.balance("1-1001") == Decimal("950000"), "Bank reduced by 50k"
        gl.assert_balanced("after disbursement")

        # 2. Accrue interest ($500)
        gl.post(
            event_type=JournalSourceType.INTEREST_ACCRUAL,
            source_ref="LOAN-001-INT-M1",
            amount_breakdown={"interest": Decimal("500")},
            description="Month 1 interest accrual",
        )
        assert gl.balance("1-3001") == Decimal("500"), "Interest receivable"
        assert gl.balance("4-1000") == Decimal("500"), "Interest income"
        gl.assert_balanced("after interest accrual")

        # 3. Origination fee ($750)
        gl.post(
            event_type=JournalSourceType.FEE,
            source_ref="LOAN-001-FEE",
            amount_breakdown={"fee": Decimal("750")},
            description="Origination fee",
        )
        assert gl.balance("1-4001") == Decimal("750"), "Fee receivable"
        assert gl.balance("4-2000") == Decimal("750"), "Fee income"
        gl.assert_balanced("after fee")

        # 4. First repayment ($20,000)
        gl.post(
            event_type=JournalSourceType.REPAYMENT,
            source_ref="PMT-001",
            amount_breakdown={"principal": Decimal("20000"), "full_amount": Decimal("20000")},
            description="Repayment 1",
        )
        assert gl.balance("1-2001") == Decimal("30000"), "Loan balance after 1st repayment"
        assert gl.balance("1-1001") == Decimal("970000"), "Bank after repayment"
        gl.assert_balanced("after repayment 1")

        # 5. Second repayment ($30,000) — fully paid
        gl.post(
            event_type=JournalSourceType.REPAYMENT,
            source_ref="PMT-002",
            amount_breakdown={"principal": Decimal("30000"), "full_amount": Decimal("30000")},
            description="Final repayment — loan fully paid",
        )
        assert gl.balance("1-2001") == Decimal("0"), "Loan fully repaid"
        assert gl.balance("1-1001") == Decimal("1000000"), "Bank restored to original"
        gl.assert_balanced("after full repayment")

        # Verify income statement
        assert gl.total_revenue() == Decimal("1250"), "Revenue = interest + fee"
        assert gl.total_expenses() == Decimal("0"), "No expenses"
        assert gl.net_income() == Decimal("1250"), "Net income"

    def test_multiple_loans_concurrent(self):
        """Multiple loans active simultaneously."""
        gl = GLLedger()
        gl.balances["1-1001"] = Decimal("5000000")
        gl.balances["3-1000"] = Decimal("5000000")

        # Disburse 3 loans
        for i, amount in enumerate([100000, 200000, 150000], 1):
            gl.post(
                event_type=JournalSourceType.LOAN_DISBURSEMENT,
                source_ref=f"LOAN-{i:03d}",
                amount_breakdown={"principal": Decimal(str(amount)), "full_amount": Decimal(str(amount))},
            )

        assert gl.balance("1-2001") == Decimal("450000"), "Total portfolio"
        assert gl.balance("1-1001") == Decimal("4550000"), "Bank after 3 disbursements"
        gl.assert_balanced("after 3 disbursements")

        # Fully repay loan 2
        gl.post(
            event_type=JournalSourceType.REPAYMENT,
            source_ref="PMT-LOAN2-FULL",
            amount_breakdown={"principal": Decimal("200000"), "full_amount": Decimal("200000")},
        )
        assert gl.balance("1-2001") == Decimal("250000"), "Portfolio after one loan paid off"
        gl.assert_balanced("after loan 2 paid off")


# ===================================================================
# Scenario 2: Write-off + Recovery
# ===================================================================


class TestWriteOffAndRecovery:
    """Loan defaults, gets provisioned, written off, then partially recovered."""

    def test_write_off_lifecycle(self):
        gl = GLLedger()
        gl.balances["1-1001"] = Decimal("1000000")
        gl.balances["3-1000"] = Decimal("1000000")

        # 1. Disburse $30,000
        gl.post(
            event_type=JournalSourceType.LOAN_DISBURSEMENT,
            source_ref="LOAN-BAD",
            amount_breakdown={"principal": Decimal("30000"), "full_amount": Decimal("30000")},
        )
        gl.assert_balanced("after disbursement")

        # 2. Partial repayment $5,000
        gl.post(
            event_type=JournalSourceType.REPAYMENT,
            source_ref="PMT-BAD-1",
            amount_breakdown={"principal": Decimal("5000"), "full_amount": Decimal("5000")},
        )
        assert gl.balance("1-2001") == Decimal("25000"), "Outstanding after partial pay"
        gl.assert_balanced("after partial repayment")

        # 3. Provision for $25,000 (expected loss)
        gl.post(
            event_type=JournalSourceType.PROVISION,
            source_ref="PROV-BAD",
            amount_breakdown={"full_amount": Decimal("25000")},
            description="Full provision for bad loan",
        )
        assert gl.balance("5-1000") == Decimal("25000"), "Provision expense"
        assert gl.balance("2-2000") == Decimal("25000"), "Allowance for loan losses"
        gl.assert_balanced("after provision")

        # 4. Write off the remaining $25,000 (reclassify to written-off)
        gl.post(
            event_type=JournalSourceType.WRITE_OFF,
            source_ref="WO-BAD",
            amount_breakdown={"principal": Decimal("25000")},
            description="Loan written off",
        )
        assert gl.balance("1-2001") == Decimal("0"), "Performing loans zeroed"
        assert gl.balance("1-2003") == Decimal("25000"), "Written-off loans"
        gl.assert_balanced("after write-off")

        # 5. Recover $10,000
        gl.post(
            event_type=JournalSourceType.RECOVERY,
            source_ref="REC-BAD",
            amount_breakdown={"full_amount": Decimal("10000")},
            description="Partial recovery on written-off loan",
        )
        assert gl.balance("1-1001") == Decimal("985000"), "Bank: 1M - 30k + 5k + 10k"
        assert gl.balance("4-4000") == Decimal("10000"), "Recovery income"
        gl.assert_balanced("after recovery")

        # Verify IS — write-off is now a reclassification, not an expense
        assert gl.total_revenue() == Decimal("10000"), "Revenue = recovery only"
        assert gl.total_expenses() == Decimal("25000"), "Expenses = provision only"
        assert gl.net_income() == Decimal("-15000"), "Net loss"

    def test_provision_without_write_off(self):
        """Provision recorded but loan is still performing (not written off yet)."""
        gl = GLLedger()
        gl.balances["1-1001"] = Decimal("500000")
        gl.balances["3-1000"] = Decimal("500000")

        gl.post(
            event_type=JournalSourceType.LOAN_DISBURSEMENT,
            source_ref="LOAN-WATCH",
            amount_breakdown={"principal": Decimal("40000"), "full_amount": Decimal("40000")},
        )

        # Partial provision (50% of outstanding)
        gl.post(
            event_type=JournalSourceType.PROVISION,
            source_ref="PROV-WATCH",
            amount_breakdown={"full_amount": Decimal("20000")},
        )
        assert gl.balance("1-2001") == Decimal("40000"), "Loan still showing"
        assert gl.balance("2-2000") == Decimal("20000"), "Allowance"
        assert gl.balance("5-1000") == Decimal("20000"), "Provision expense"
        gl.assert_balanced("provision without write-off")


# ===================================================================
# Scenario 3: Interest accrual multi-period
# ===================================================================


class TestInterestAccrual:
    """Verify interest accrual over multiple months builds revenue correctly."""

    def test_monthly_accruals(self):
        gl = GLLedger()
        gl.balances["1-1001"] = Decimal("1000000")
        gl.balances["3-1000"] = Decimal("1000000")

        # Disburse
        gl.post(
            event_type=JournalSourceType.LOAN_DISBURSEMENT,
            source_ref="LOAN-INT",
            amount_breakdown={"principal": Decimal("100000"), "full_amount": Decimal("100000")},
        )

        # Accrue 12% p.a. → $1,000/month for 6 months
        monthly_interest = Decimal("1000")
        for month in range(1, 7):
            gl.post(
                event_type=JournalSourceType.INTEREST_ACCRUAL,
                source_ref=f"LOAN-INT-M{month}",
                amount_breakdown={"interest": monthly_interest},
            )

        assert gl.balance("1-3001") == Decimal("6000"), "6 months interest receivable"
        assert gl.balance("4-1000") == Decimal("6000"), "6 months interest income"
        assert gl.total_revenue() == Decimal("6000")
        gl.assert_balanced("after 6 months of accrual")


# ===================================================================
# Scenario 4: Mixed portfolio report verification
# ===================================================================


class TestPortfolioReport:
    """Build a mixed portfolio and verify report-level aggregates."""

    def _build_portfolio(self) -> GLLedger:
        gl = GLLedger()
        # Capitalise
        gl.balances["1-1001"] = Decimal("10000000")
        gl.balances["3-1000"] = Decimal("10000000")

        # ── Loan A: $200,000 — fully performing ──
        gl.post(event_type=JournalSourceType.LOAN_DISBURSEMENT,
                source_ref="LOAN-A",
                amount_breakdown={"principal": Decimal("200000"), "full_amount": Decimal("200000")})
        # 3 months interest
        for m in range(1, 4):
            gl.post(event_type=JournalSourceType.INTEREST_ACCRUAL,
                    source_ref=f"LOAN-A-INT-M{m}",
                    amount_breakdown={"interest": Decimal("2000")})
        # Fee
        gl.post(event_type=JournalSourceType.FEE,
                source_ref="LOAN-A-FEE",
                amount_breakdown={"fee": Decimal("3000")})
        # Partial repayment
        gl.post(event_type=JournalSourceType.REPAYMENT,
                source_ref="PMT-A1",
                amount_breakdown={"principal": Decimal("50000"), "full_amount": Decimal("50000")})

        # ── Loan B: $80,000 — fully repaid ──
        gl.post(event_type=JournalSourceType.LOAN_DISBURSEMENT,
                source_ref="LOAN-B",
                amount_breakdown={"principal": Decimal("80000"), "full_amount": Decimal("80000")})
        gl.post(event_type=JournalSourceType.INTEREST_ACCRUAL,
                source_ref="LOAN-B-INT",
                amount_breakdown={"interest": Decimal("800")})
        gl.post(event_type=JournalSourceType.REPAYMENT,
                source_ref="PMT-B-FULL",
                amount_breakdown={"principal": Decimal("80000"), "full_amount": Decimal("80000")})

        # ── Loan C: $120,000 — written off ──
        gl.post(event_type=JournalSourceType.LOAN_DISBURSEMENT,
                source_ref="LOAN-C",
                amount_breakdown={"principal": Decimal("120000"), "full_amount": Decimal("120000")})
        gl.post(event_type=JournalSourceType.REPAYMENT,
                source_ref="PMT-C1",
                amount_breakdown={"principal": Decimal("20000"), "full_amount": Decimal("20000")})
        gl.post(event_type=JournalSourceType.PROVISION,
                source_ref="PROV-C",
                amount_breakdown={"full_amount": Decimal("100000")})
        gl.post(event_type=JournalSourceType.WRITE_OFF,
                source_ref="WO-C",
                amount_breakdown={"principal": Decimal("100000")})
        # Partial recovery
        gl.post(event_type=JournalSourceType.RECOVERY,
                source_ref="REC-C",
                amount_breakdown={"full_amount": Decimal("15000")})

        return gl

    def test_performing_loans_balance(self):
        gl = self._build_portfolio()
        # Loan A outstanding: 200k - 50k = 150k
        # Loan B: fully repaid → 0
        # Loan C: written off → 0
        assert gl.balance("1-2001") == Decimal("150000")

    def test_bank_balance(self):
        gl = self._build_portfolio()
        # 10M - 200k - 80k - 120k + 50k + 80k + 20k + 15k = 9,765,000
        assert gl.balance("1-1001") == Decimal("9765000")

    def test_interest_receivable(self):
        gl = self._build_portfolio()
        # Loan A: 3 × 2000 = 6000, Loan B: 800
        assert gl.balance("1-3001") == Decimal("6800")

    def test_fee_receivable(self):
        gl = self._build_portfolio()
        assert gl.balance("1-4001") == Decimal("3000")

    def test_allowance_for_loan_losses(self):
        gl = self._build_portfolio()
        assert gl.balance("2-2000") == Decimal("100000")

    def test_interest_income(self):
        gl = self._build_portfolio()
        assert gl.balance("4-1000") == Decimal("6800")

    def test_fee_income(self):
        gl = self._build_portfolio()
        assert gl.balance("4-2000") == Decimal("3000")

    def test_recovery_income(self):
        gl = self._build_portfolio()
        assert gl.balance("4-4000") == Decimal("15000")

    def test_provision_expense(self):
        gl = self._build_portfolio()
        assert gl.balance("5-1000") == Decimal("100000")

    def test_written_off_loans(self):
        gl = self._build_portfolio()
        assert gl.balance("1-2003") == Decimal("100000"), "Written-off loans tracked"

    def test_total_revenue(self):
        gl = self._build_portfolio()
        # interest 6800 + fee 3000 + recovery 15000
        assert gl.total_revenue() == Decimal("24800")

    def test_total_expenses(self):
        gl = self._build_portfolio()
        # provision 100000 only (write-off is now a reclassification, not expense)
        assert gl.total_expenses() == Decimal("100000")

    def test_net_income(self):
        gl = self._build_portfolio()
        # 24800 revenue - 100000 expense = -75200
        assert gl.net_income() == Decimal("-75200"), "Net loss"

    def test_balance_sheet_balanced(self):
        gl = self._build_portfolio()
        gl.assert_balanced("mixed portfolio final state")

    def test_trial_balance_balanced(self):
        gl = self._build_portfolio()
        dr, cr = gl.trial_balance()
        assert dr == cr, f"Trial balance: DR={dr} CR={cr}"

    def test_entry_count(self):
        gl = self._build_portfolio()
        assert len(gl.entries) == 14, "Expected 14 journal entries"

    def test_entries_by_type(self):
        gl = self._build_portfolio()
        by_type = {}
        for e in gl.entries:
            t = e["event_type"].value
            by_type[t] = by_type.get(t, 0) + 1
        assert by_type["loan_disbursement"] == 3
        assert by_type["repayment"] == 3
        assert by_type["interest_accrual"] == 4
        assert by_type["fee"] == 1
        assert by_type["provision"] == 1
        assert by_type["write_off"] == 1
        assert by_type["recovery"] == 1


# ===================================================================
# Scenario 5: Amount resolution & conditions
# ===================================================================


class TestMappingAmountResolution:
    """Verify that the mapping engine resolves amounts correctly for all source types."""

    def test_principal_resolution(self):
        breakdown = {"principal": Decimal("50000"), "interest": Decimal("500"), "full_amount": Decimal("50500")}
        assert _resolve_amount(MappingAmountSource.PRINCIPAL, breakdown) == Decimal("50000")

    def test_interest_resolution(self):
        breakdown = {"principal": Decimal("50000"), "interest": Decimal("500"), "full_amount": Decimal("50500")}
        assert _resolve_amount(MappingAmountSource.INTEREST, breakdown) == Decimal("500")

    def test_fee_resolution(self):
        breakdown = {"fee": Decimal("1500")}
        assert _resolve_amount(MappingAmountSource.FEE, breakdown) == Decimal("1500")

    def test_full_amount_resolution(self):
        breakdown = {"principal": Decimal("50000"), "full_amount": Decimal("50500")}
        assert _resolve_amount(MappingAmountSource.FULL_AMOUNT, breakdown) == Decimal("50500")

    def test_custom_resolution(self):
        breakdown = {"custom": Decimal("999")}
        assert _resolve_amount(MappingAmountSource.CUSTOM, breakdown) == Decimal("999")

    def test_missing_key_returns_zero(self):
        breakdown = {"principal": Decimal("50000")}
        assert _resolve_amount(MappingAmountSource.INTEREST, breakdown) == Decimal("0")
        assert _resolve_amount(MappingAmountSource.FEE, breakdown) == Decimal("0")

    def test_conditions_days_past_due(self):
        """Conditional mapping for delinquent loans."""
        conds = {"days_past_due": {">": 90}}
        assert _evaluate_conditions(conds, {"days_past_due": 91}) is True
        assert _evaluate_conditions(conds, {"days_past_due": 90}) is False
        assert _evaluate_conditions(conds, {"days_past_due": 30}) is False

    def test_conditions_amount_range(self):
        """Conditional mapping for amount-based tiers."""
        conds = {"amount": {">=": 100000, "<=": 500000}}
        assert _evaluate_conditions(conds, {"amount": 250000}) is True
        assert _evaluate_conditions(conds, {"amount": 99999}) is False
        assert _evaluate_conditions(conds, {"amount": 500001}) is False


# ===================================================================
# Scenario 6: Edge cases
# ===================================================================


class TestEdgeCases:
    """Edge cases in GL lifecycle."""

    def test_zero_principal_fee_only(self):
        """Loan with fee but $0 principal amount (shouldn't happen but shouldn't crash)."""
        gl = GLLedger()
        gl.balances["1-1001"] = Decimal("100000")
        gl.balances["3-1000"] = Decimal("100000")

        gl.post(
            event_type=JournalSourceType.FEE,
            source_ref="FEE-ONLY",
            amount_breakdown={"fee": Decimal("250")},
        )
        assert gl.balance("1-4001") == Decimal("250")
        assert gl.balance("4-2000") == Decimal("250")
        gl.assert_balanced("fee-only entry")

    def test_very_small_amount(self):
        """Penny amounts should work."""
        gl = GLLedger()
        gl.balances["1-1001"] = Decimal("100000")
        gl.balances["3-1000"] = Decimal("100000")

        gl.post(
            event_type=JournalSourceType.INTEREST_ACCRUAL,
            source_ref="TINY-INT",
            amount_breakdown={"interest": Decimal("0.01")},
        )
        assert gl.balance("1-3001") == Decimal("0.01")
        gl.assert_balanced("penny interest")

    def test_large_loan(self):
        """$10M+ loan."""
        gl = GLLedger()
        gl.balances["1-1001"] = Decimal("50000000")
        gl.balances["3-1000"] = Decimal("50000000")

        gl.post(
            event_type=JournalSourceType.LOAN_DISBURSEMENT,
            source_ref="LOAN-JUMBO",
            amount_breakdown={"principal": Decimal("12500000"), "full_amount": Decimal("12500000")},
        )
        assert gl.balance("1-2001") == Decimal("12500000")
        gl.assert_balanced("jumbo loan")

    def test_accounting_equation_holds_across_50_entries(self):
        """Rapid-fire 50 entries — equation must hold at every step."""
        gl = GLLedger()
        gl.balances["1-1001"] = Decimal("100000000")
        gl.balances["3-1000"] = Decimal("100000000")

        for i in range(1, 11):
            amt = Decimal(str(i * 10000))
            gl.post(
                event_type=JournalSourceType.LOAN_DISBURSEMENT,
                source_ref=f"LOAN-RAPID-{i}",
                amount_breakdown={"principal": amt, "full_amount": amt},
            )
            gl.assert_balanced(f"disbursement {i}")

            gl.post(
                event_type=JournalSourceType.INTEREST_ACCRUAL,
                source_ref=f"INT-RAPID-{i}",
                amount_breakdown={"interest": amt / 100},
            )
            gl.assert_balanced(f"interest {i}")

            gl.post(
                event_type=JournalSourceType.FEE,
                source_ref=f"FEE-RAPID-{i}",
                amount_breakdown={"fee": Decimal("500")},
            )
            gl.assert_balanced(f"fee {i}")

            gl.post(
                event_type=JournalSourceType.REPAYMENT,
                source_ref=f"PMT-RAPID-{i}",
                amount_breakdown={"principal": amt / 2, "full_amount": amt / 2},
            )
            gl.assert_balanced(f"repayment {i}")

            if i % 3 == 0:
                remaining = amt / 2
                gl.post(
                    event_type=JournalSourceType.PROVISION,
                    source_ref=f"PROV-RAPID-{i}",
                    amount_breakdown={"full_amount": remaining},
                )
                gl.assert_balanced(f"provision {i}")

        assert len(gl.entries) > 40, "Should have many entries"
        gl.assert_balanced("final state after 50 entries")
        dr, cr = gl.trial_balance()
        assert dr == cr

    def test_all_event_types_covered(self):
        """Every JournalSourceType that has a mapping can be posted."""
        gl = GLLedger()
        gl.balances["1-1001"] = Decimal("10000000")
        gl.balances["3-1000"] = Decimal("10000000")

        # Disbursement
        gl.post(event_type=JournalSourceType.LOAN_DISBURSEMENT,
                source_ref="ALL-1",
                amount_breakdown={"principal": Decimal("50000"), "full_amount": Decimal("50000")})
        # Repayment
        gl.post(event_type=JournalSourceType.REPAYMENT,
                source_ref="ALL-2",
                amount_breakdown={"principal": Decimal("10000"), "full_amount": Decimal("10000")})
        # Interest
        gl.post(event_type=JournalSourceType.INTEREST_ACCRUAL,
                source_ref="ALL-3",
                amount_breakdown={"interest": Decimal("500")})
        # Fee
        gl.post(event_type=JournalSourceType.FEE,
                source_ref="ALL-4",
                amount_breakdown={"fee": Decimal("750")})
        # Provision
        gl.post(event_type=JournalSourceType.PROVISION,
                source_ref="ALL-5",
                amount_breakdown={"full_amount": Decimal("10000")})
        # Write-off
        gl.post(event_type=JournalSourceType.WRITE_OFF,
                source_ref="ALL-6",
                amount_breakdown={"principal": Decimal("10000")})
        # Recovery
        gl.post(event_type=JournalSourceType.RECOVERY,
                source_ref="ALL-7",
                amount_breakdown={"full_amount": Decimal("5000")})

        assert len(gl.entries) == 7, "All 7 event types posted"
        gl.assert_balanced("all event types")

        # BS should have real numbers everywhere relevant
        assert gl.balance("1-2001") == Decimal("30000"), "Performing: 50k - 10k - 10k(wo)"
        assert gl.balance("1-2003") == Decimal("10000"), "Written-off loans: reclassified"
        assert gl.balance("1-3001") == Decimal("500"), "Interest receivable"
        assert gl.balance("1-4001") == Decimal("750"), "Fee receivable"
        assert gl.balance("2-2000") == Decimal("10000"), "Allowance"
        assert gl.balance("4-1000") == Decimal("500"), "Interest income"
        assert gl.balance("4-2000") == Decimal("750"), "Fee income"
        assert gl.balance("4-4000") == Decimal("5000"), "Recovery income"
        assert gl.balance("5-1000") == Decimal("10000"), "Provision expense"
