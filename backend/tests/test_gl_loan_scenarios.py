"""End-to-end GL loan-scenario tests.

Exercises the real mapping engine and journal engine with mocked DB to
simulate:
  1. Fully-repaid loan  (disburse → interest × N → fee → repayments → payoff)
  2. Written-off loan   (disburse → partial pay → provision → write-off)
  3. Recovery after write-off
  4. Verifies every JE is balanced (DR == CR) and accounts are correct.

Each scenario calls ``generate_journal_entry(dry_run=True)`` to capture
the exact lines the mapping engine produces, then also calls the real
``create_journal_entry`` with a mocked DB to verify the full code path.
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
    GLMappingTemplate,
    GLMappingTemplateLine,
    GLAccount,
    AccountCategory,
    AccountType,
    AccountStatus,
    Currency,
    AccountingPeriod,
    PeriodStatus,
    MappingLineType,
    MappingAmountSource,
)
from app.services.gl.mapping_engine import (
    generate_journal_entry,
    MappingError,
    _resolve_amount,
)
from app.services.gl.journal_engine import (
    create_journal_entry,
    _validate_balance,
    BalanceError,
)


# ===================================================================
# Fixtures: build mock mapping templates that mirror the real seed
# ===================================================================

# Account ID constants (matching seed_gl.py COA)
ACCT_BANK        = 26   # 1-1001 Operating Bank Account
ACCT_PERF_LOANS  = 28   # 1-2001 Performing Loans
ACCT_NPL         = 29   # 1-2002 Non-Performing Loans
ACCT_WO_LOANS    = 30   # 1-2003 Written-Off Loans
ACCT_INT_RECV    = 31   # 1-3001 Interest Receivable - Performing
ACCT_FEE_RECV    = 33   # 1-4001 Origination Fee Receivable
ACCT_ALLOWANCE   = 12   # 2-2000 Allowance for Loan Losses
ACCT_INT_INCOME  = 18   # 4-1000 Interest Income
ACCT_FEE_INCOME  = 19   # 4-2000 Fee Income
ACCT_REC_INCOME  = 21   # 4-4000 Recovery Income
ACCT_PROV_EXP    = 23   # 5-1000 Provision Expense
ACCT_WO_EXP      = 25   # 5-3000 Write-Off Expense
ACCT_EQUITY      = 16   # 3-1000 Share Capital


def _make_template_line(*, line_type, gl_account_id, amount_source, desc=""):
    ln = MagicMock(spec=GLMappingTemplateLine)
    ln.line_type = line_type
    ln.gl_account_id = gl_account_id
    ln.amount_source = amount_source
    ln.description_template = desc or None
    return ln


def _make_template(event_type: JournalSourceType, lines_spec: list) -> GLMappingTemplate:
    tpl = MagicMock(spec=GLMappingTemplate)
    tpl.name = f"Template-{event_type.value}"
    tpl.event_type = event_type
    tpl.conditions = None
    tpl.lines = [
        _make_template_line(
            line_type=lt,
            gl_account_id=acct,
            amount_source=src,
            desc=desc,
        )
        for lt, acct, src, desc in lines_spec
    ]
    return tpl


TEMPLATES = {
    JournalSourceType.LOAN_DISBURSEMENT: _make_template(
        JournalSourceType.LOAN_DISBURSEMENT,
        [
            (MappingLineType.DEBIT,  ACCT_PERF_LOANS, MappingAmountSource.PRINCIPAL,
             "Loan disbursement — {source_reference}"),
            (MappingLineType.CREDIT, ACCT_BANK,       MappingAmountSource.PRINCIPAL,
             "Bank outflow — {source_reference}"),
        ],
    ),
    JournalSourceType.REPAYMENT: _make_template(
        JournalSourceType.REPAYMENT,
        [
            (MappingLineType.DEBIT,  ACCT_BANK,       MappingAmountSource.FULL_AMOUNT,
             "Bank inflow — {source_reference}"),
            (MappingLineType.CREDIT, ACCT_PERF_LOANS, MappingAmountSource.FULL_AMOUNT,
             "Repayment applied — {source_reference}"),
        ],
    ),
    JournalSourceType.INTEREST_ACCRUAL: _make_template(
        JournalSourceType.INTEREST_ACCRUAL,
        [
            (MappingLineType.DEBIT,  ACCT_INT_RECV,   MappingAmountSource.INTEREST,
             "Interest receivable — {source_reference}"),
            (MappingLineType.CREDIT, ACCT_INT_INCOME,  MappingAmountSource.INTEREST,
             "Interest income — {source_reference}"),
        ],
    ),
    JournalSourceType.FEE: _make_template(
        JournalSourceType.FEE,
        [
            (MappingLineType.DEBIT,  ACCT_FEE_RECV,   MappingAmountSource.FEE,
             "Fee receivable — {source_reference}"),
            (MappingLineType.CREDIT, ACCT_FEE_INCOME,  MappingAmountSource.FEE,
             "Fee income — {source_reference}"),
        ],
    ),
    JournalSourceType.PROVISION: _make_template(
        JournalSourceType.PROVISION,
        [
            (MappingLineType.DEBIT,  ACCT_PROV_EXP,   MappingAmountSource.FULL_AMOUNT,
             "Provision expense — {source_reference}"),
            (MappingLineType.CREDIT, ACCT_ALLOWANCE,   MappingAmountSource.FULL_AMOUNT,
             "Allowance increase — {source_reference}"),
        ],
    ),
    JournalSourceType.WRITE_OFF: _make_template(
        JournalSourceType.WRITE_OFF,
        [
            (MappingLineType.DEBIT,  ACCT_WO_LOANS,    MappingAmountSource.PRINCIPAL,
             "Reclassify to written-off loans — {source_reference}"),
            (MappingLineType.CREDIT, ACCT_PERF_LOANS,  MappingAmountSource.PRINCIPAL,
             "Remove from performing loans — {source_reference}"),
        ],
    ),
    JournalSourceType.RECOVERY: _make_template(
        JournalSourceType.RECOVERY,
        [
            (MappingLineType.DEBIT,  ACCT_BANK,        MappingAmountSource.FULL_AMOUNT,
             "Recovery inflow — {source_reference}"),
            (MappingLineType.CREDIT, ACCT_REC_INCOME,   MappingAmountSource.FULL_AMOUNT,
             "Recovery income — {source_reference}"),
        ],
    ),
}


def _mock_get_mapping(event_type, product_id=None, context=None):
    """Return the template for a given event type."""
    return TEMPLATES.get(event_type)


# ===================================================================
# Helper: run dry-run and validate
# ===================================================================

async def _dry_run_entry(event_type, source_ref, amount_breakdown, **kw):
    """Call generate_journal_entry(dry_run=True) with mocked template lookup."""
    db = AsyncMock()
    with patch(
        "app.services.gl.mapping_engine.get_mapping_for_event",
        side_effect=lambda db, et, **k: _mock_get_mapping(et, **k),
    ):
        result = await generate_journal_entry(
            db,
            event_type=event_type,
            source_reference=source_ref,
            amount_breakdown=amount_breakdown,
            dry_run=True,
            **kw,
        )
    return result


def _assert_je_balanced(result: dict):
    """Assert a dry-run result is balanced."""
    assert "error" not in result, f"Dry-run error: {result.get('error')}"
    assert result["is_balanced"], (
        f"JE unbalanced: DR={result['total_debit']} CR={result['total_credit']}"
    )
    assert result["total_debit"] > 0, "JE has zero amounts"


def _find_line(result: dict, account_id: int) -> dict | None:
    """Find a line targeting a specific account ID."""
    for ln in result["lines"]:
        if ln["gl_account_id"] == account_id:
            return ln
    return None


# ===================================================================
# Scenario 1: Fully-repaid loan (dry-run through mapping engine)
# ===================================================================


class TestFullyRepaidLoanMapping:
    """Simulate a $100,000 loan through full lifecycle via mapping engine."""

    PRINCIPAL = Decimal("100000")
    MONTHLY_INTEREST = Decimal("1500")  # 18% p.a. ÷ 12
    ORIGINATION_FEE = Decimal("2000")   # 2% flat

    @pytest.mark.asyncio
    async def test_disbursement_je(self):
        result = await _dry_run_entry(
            JournalSourceType.LOAN_DISBURSEMENT,
            "LOAN-REPAID-001",
            {"principal": self.PRINCIPAL, "full_amount": self.PRINCIPAL},
        )
        _assert_je_balanced(result)
        assert result["total_debit"] == float(self.PRINCIPAL)

        # DR Performing Loans
        dr = _find_line(result, ACCT_PERF_LOANS)
        assert dr and dr["debit_amount"] == float(self.PRINCIPAL)

        # CR Bank
        cr = _find_line(result, ACCT_BANK)
        assert cr and cr["credit_amount"] == float(self.PRINCIPAL)

    @pytest.mark.asyncio
    async def test_interest_accrual_je(self):
        result = await _dry_run_entry(
            JournalSourceType.INTEREST_ACCRUAL,
            "LOAN-REPAID-001-INT-M1",
            {"interest": self.MONTHLY_INTEREST},
        )
        _assert_je_balanced(result)

        # DR Interest Receivable
        dr = _find_line(result, ACCT_INT_RECV)
        assert dr and dr["debit_amount"] == float(self.MONTHLY_INTEREST)

        # CR Interest Income (revenue!)
        cr = _find_line(result, ACCT_INT_INCOME)
        assert cr and cr["credit_amount"] == float(self.MONTHLY_INTEREST)

    @pytest.mark.asyncio
    async def test_origination_fee_je(self):
        result = await _dry_run_entry(
            JournalSourceType.FEE,
            "LOAN-REPAID-001-FEE",
            {"fee": self.ORIGINATION_FEE},
        )
        _assert_je_balanced(result)

        # DR Fee Receivable
        dr = _find_line(result, ACCT_FEE_RECV)
        assert dr and dr["debit_amount"] == float(self.ORIGINATION_FEE)

        # CR Fee Income (revenue!)
        cr = _find_line(result, ACCT_FEE_INCOME)
        assert cr and cr["credit_amount"] == float(self.ORIGINATION_FEE)

    @pytest.mark.asyncio
    async def test_partial_repayment_je(self):
        pay_amount = Decimal("25000")
        result = await _dry_run_entry(
            JournalSourceType.REPAYMENT,
            "PMT-REPAID-001",
            {"principal": pay_amount, "full_amount": pay_amount},
        )
        _assert_je_balanced(result)

        # DR Bank
        dr = _find_line(result, ACCT_BANK)
        assert dr and dr["debit_amount"] == float(pay_amount)

        # CR Performing Loans
        cr = _find_line(result, ACCT_PERF_LOANS)
        assert cr and cr["credit_amount"] == float(pay_amount)

    @pytest.mark.asyncio
    async def test_final_repayment_je(self):
        """Last repayment that zeroes out the loan."""
        final_amount = Decimal("75000")
        result = await _dry_run_entry(
            JournalSourceType.REPAYMENT,
            "PMT-REPAID-002-FINAL",
            {"principal": final_amount, "full_amount": final_amount},
        )
        _assert_je_balanced(result)
        assert result["total_debit"] == float(final_amount)

    @pytest.mark.asyncio
    async def test_full_lifecycle_all_jes_balanced(self):
        """Run every event in sequence and verify all are balanced."""
        events = [
            (JournalSourceType.LOAN_DISBURSEMENT, "LOAN-FULL-CYCLE",
             {"principal": Decimal("100000"), "full_amount": Decimal("100000")}),
            (JournalSourceType.FEE, "LOAN-FULL-CYCLE-FEE",
             {"fee": Decimal("2000")}),
            (JournalSourceType.INTEREST_ACCRUAL, "LOAN-FULL-CYCLE-INT-M1",
             {"interest": Decimal("1500")}),
            (JournalSourceType.INTEREST_ACCRUAL, "LOAN-FULL-CYCLE-INT-M2",
             {"interest": Decimal("1500")}),
            (JournalSourceType.INTEREST_ACCRUAL, "LOAN-FULL-CYCLE-INT-M3",
             {"interest": Decimal("1500")}),
            (JournalSourceType.REPAYMENT, "PMT-FULL-1",
             {"principal": Decimal("30000"), "full_amount": Decimal("30000")}),
            (JournalSourceType.REPAYMENT, "PMT-FULL-2",
             {"principal": Decimal("30000"), "full_amount": Decimal("30000")}),
            (JournalSourceType.REPAYMENT, "PMT-FULL-3",
             {"principal": Decimal("40000"), "full_amount": Decimal("40000")}),
        ]

        # Track net position across all entries
        account_debits: dict[int, float] = {}
        account_credits: dict[int, float] = {}

        for event_type, ref, breakdown in events:
            result = await _dry_run_entry(event_type, ref, breakdown)
            _assert_je_balanced(result)
            for ln in result["lines"]:
                aid = ln["gl_account_id"]
                account_debits[aid] = account_debits.get(aid, 0) + ln["debit_amount"]
                account_credits[aid] = account_credits.get(aid, 0) + ln["credit_amount"]

        # After full repayment, performing loans should net to zero
        loan_net = account_debits.get(ACCT_PERF_LOANS, 0) - account_credits.get(ACCT_PERF_LOANS, 0)
        assert loan_net == 0, f"Loan not zeroed out: net = {loan_net}"

        # Bank should net to zero (100k out, 100k back)
        bank_net = account_debits.get(ACCT_BANK, 0) - account_credits.get(ACCT_BANK, 0)
        assert bank_net == 0, f"Bank not back to original: net = {bank_net}"

        # Revenue accounts should have credits only
        assert account_credits.get(ACCT_INT_INCOME, 0) == 4500, "Interest income should be 3 × 1500"
        assert account_credits.get(ACCT_FEE_INCOME, 0) == 2000, "Fee income should be 2000"


# ===================================================================
# Scenario 2: Written-off loan (dry-run through mapping engine)
# ===================================================================


class TestWrittenOffLoanMapping:
    """Simulate a $50,000 loan that defaults and is written off."""

    PRINCIPAL = Decimal("50000")

    @pytest.mark.asyncio
    async def test_disbursement(self):
        result = await _dry_run_entry(
            JournalSourceType.LOAN_DISBURSEMENT,
            "LOAN-WO-001",
            {"principal": self.PRINCIPAL, "full_amount": self.PRINCIPAL},
        )
        _assert_je_balanced(result)
        assert result["total_debit"] == float(self.PRINCIPAL)

    @pytest.mark.asyncio
    async def test_partial_repayment(self):
        result = await _dry_run_entry(
            JournalSourceType.REPAYMENT,
            "PMT-WO-001",
            {"principal": Decimal("10000"), "full_amount": Decimal("10000")},
        )
        _assert_je_balanced(result)

    @pytest.mark.asyncio
    async def test_provision_for_expected_loss(self):
        """Provision covers remaining $40,000 outstanding."""
        result = await _dry_run_entry(
            JournalSourceType.PROVISION,
            "PROV-WO-001",
            {"full_amount": Decimal("40000")},
        )
        _assert_je_balanced(result)

        # DR Provision Expense (expense!)
        dr = _find_line(result, ACCT_PROV_EXP)
        assert dr and dr["debit_amount"] == 40000.0

        # CR Allowance for Loan Losses
        cr = _find_line(result, ACCT_ALLOWANCE)
        assert cr and cr["credit_amount"] == 40000.0

    @pytest.mark.asyncio
    async def test_write_off(self):
        """Write off the $40,000 remaining principal."""
        result = await _dry_run_entry(
            JournalSourceType.WRITE_OFF,
            "WO-001",
            {"principal": Decimal("40000")},
        )
        _assert_je_balanced(result)

        # DR Written-Off Loans (reclassify)
        dr = _find_line(result, ACCT_WO_LOANS)
        assert dr and dr["debit_amount"] == 40000.0

        # CR Performing Loans (removes from books)
        cr = _find_line(result, ACCT_PERF_LOANS)
        assert cr and cr["credit_amount"] == 40000.0

    @pytest.mark.asyncio
    async def test_recovery_after_write_off(self):
        """Recover $12,000 on the previously written-off loan."""
        result = await _dry_run_entry(
            JournalSourceType.RECOVERY,
            "REC-WO-001",
            {"full_amount": Decimal("12000")},
        )
        _assert_je_balanced(result)

        # DR Bank
        dr = _find_line(result, ACCT_BANK)
        assert dr and dr["debit_amount"] == 12000.0

        # CR Recovery Income (revenue!)
        cr = _find_line(result, ACCT_REC_INCOME)
        assert cr and cr["credit_amount"] == 12000.0

    @pytest.mark.asyncio
    async def test_write_off_full_lifecycle_all_jes_balanced(self):
        """Run every event from disbursement through recovery."""
        events = [
            (JournalSourceType.LOAN_DISBURSEMENT, "LOAN-WO-FULL",
             {"principal": Decimal("50000"), "full_amount": Decimal("50000")}),
            (JournalSourceType.INTEREST_ACCRUAL, "LOAN-WO-FULL-INT-M1",
             {"interest": Decimal("750")}),
            (JournalSourceType.REPAYMENT, "PMT-WO-FULL-1",
             {"principal": Decimal("10000"), "full_amount": Decimal("10000")}),
            (JournalSourceType.PROVISION, "PROV-WO-FULL",
             {"full_amount": Decimal("40000")}),
            (JournalSourceType.WRITE_OFF, "WO-FULL",
             {"principal": Decimal("40000")}),
            (JournalSourceType.RECOVERY, "REC-WO-FULL",
             {"full_amount": Decimal("12000")}),
        ]

        account_debits: dict[int, float] = {}
        account_credits: dict[int, float] = {}

        for event_type, ref, breakdown in events:
            result = await _dry_run_entry(event_type, ref, breakdown)
            _assert_je_balanced(result)
            for ln in result["lines"]:
                aid = ln["gl_account_id"]
                account_debits[aid] = account_debits.get(aid, 0) + ln["debit_amount"]
                account_credits[aid] = account_credits.get(aid, 0) + ln["credit_amount"]

        # Performing loans: 50k DR (disburse) − 10k CR (repay) − 40k CR (write-off) = 0
        loan_net = account_debits.get(ACCT_PERF_LOANS, 0) - account_credits.get(ACCT_PERF_LOANS, 0)
        assert loan_net == 0, f"Performing loans not zeroed: {loan_net}"

        # Bank: −50k (disburse) + 10k (repay) + 12k (recovery) = −28k
        bank_net = account_debits.get(ACCT_BANK, 0) - account_credits.get(ACCT_BANK, 0)
        assert bank_net == -28000, f"Bank net wrong: {bank_net}"

        # Revenue: interest 750 + recovery 12,000 = 12,750
        total_revenue = (
            account_credits.get(ACCT_INT_INCOME, 0)
            + account_credits.get(ACCT_REC_INCOME, 0)
        )
        assert total_revenue == 12750, f"Total revenue: {total_revenue}"

        # Expenses: provision 40,000 only (write-off is now reclassification)
        total_expenses = account_debits.get(ACCT_PROV_EXP, 0)
        assert total_expenses == 40000, f"Total expenses: {total_expenses}"

        # Written-off loans: 40,000 (reclassified from performing)
        wo_net = account_debits.get(ACCT_WO_LOANS, 0) - account_credits.get(ACCT_WO_LOANS, 0)
        assert wo_net == 40000, f"Written-off loans: {wo_net}"

        # Net income: 12,750 − 40,000 = −27,250 (loss)
        net_income = total_revenue - total_expenses
        assert net_income == -27250, f"Net income: {net_income}"


# ===================================================================
# Scenario 3: create_journal_entry with mocked DB
# ===================================================================


class TestCreateJournalEntryRepaidLoan:
    """Test the actual create_journal_entry function for a repaid loan."""

    def _make_account(self, acct_id, code, status=AccountStatus.ACTIVE):
        a = MagicMock(spec=GLAccount)
        a.id = acct_id
        a.account_code = code
        a.name = f"Account {code}"
        a.status = status
        return a

    def _make_currency(self, code="JMD"):
        c = MagicMock(spec=Currency)
        c.id = 1
        c.code = code
        return c

    def _make_period(self, status=PeriodStatus.OPEN):
        p = MagicMock(spec=AccountingPeriod)
        p.id = 1
        p.name = "Feb 2026"
        p.status = status
        return p

    def _mock_db(self, accounts, currency, period):
        """Create a mock async DB that returns the right objects for lookups."""
        db = AsyncMock()

        async def mock_execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)

            # Account lookup (by IDs)
            if "gl_accounts" in stmt_str and "IN" in stmt_str.upper():
                result.scalars.return_value.all.return_value = accounts
                return result
            # Currency lookup
            if "gl_currencies" in stmt_str:
                result.scalar_one_or_none.return_value = currency
                return result
            # Period lookup
            if "gl_accounting_periods" in stmt_str:
                result.scalar_one_or_none.return_value = period
                return result
            # Entry number lookup
            if "max" in stmt_str.lower():
                result.scalar_one_or_none.return_value = None
                return result
            return result

        db.execute = mock_execute
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_disbursement_creates_posted_entry(self):
        """create_journal_entry with auto_post=True produces POSTED entry."""
        accounts = [
            self._make_account(ACCT_PERF_LOANS, "1-2001"),
            self._make_account(ACCT_BANK, "1-1001"),
        ]
        db = self._mock_db(accounts, self._make_currency(), self._make_period())

        entry = await create_journal_entry(
            db,
            lines=[
                {"gl_account_id": ACCT_PERF_LOANS, "debit_amount": 100000, "credit_amount": 0,
                 "description": "Loan disbursement"},
                {"gl_account_id": ACCT_BANK, "debit_amount": 0, "credit_amount": 100000,
                 "description": "Bank outflow"},
            ],
            source_type=JournalSourceType.LOAN_DISBURSEMENT,
            source_reference="LOAN-TEST-001",
            description="Test loan disbursement",
            auto_post=True,
        )
        assert entry.status == JournalEntryStatus.POSTED

    @pytest.mark.asyncio
    async def test_repayment_creates_posted_entry(self):
        accounts = [
            self._make_account(ACCT_BANK, "1-1001"),
            self._make_account(ACCT_PERF_LOANS, "1-2001"),
        ]
        db = self._mock_db(accounts, self._make_currency(), self._make_period())

        entry = await create_journal_entry(
            db,
            lines=[
                {"gl_account_id": ACCT_BANK, "debit_amount": 100000, "credit_amount": 0,
                 "description": "Final repayment"},
                {"gl_account_id": ACCT_PERF_LOANS, "debit_amount": 0, "credit_amount": 100000,
                 "description": "Loan paid off"},
            ],
            source_type=JournalSourceType.REPAYMENT,
            source_reference="PMT-TEST-FULL",
            description="Full repayment — loan closed",
            auto_post=True,
        )
        assert entry.status == JournalEntryStatus.POSTED

    @pytest.mark.asyncio
    async def test_interest_accrual_creates_revenue(self):
        accounts = [
            self._make_account(ACCT_INT_RECV, "1-3001"),
            self._make_account(ACCT_INT_INCOME, "4-1000"),
        ]
        db = self._mock_db(accounts, self._make_currency(), self._make_period())

        entry = await create_journal_entry(
            db,
            lines=[
                {"gl_account_id": ACCT_INT_RECV, "debit_amount": 1500, "credit_amount": 0,
                 "description": "Interest receivable"},
                {"gl_account_id": ACCT_INT_INCOME, "debit_amount": 0, "credit_amount": 1500,
                 "description": "Interest income"},
            ],
            source_type=JournalSourceType.INTEREST_ACCRUAL,
            source_reference="INT-TEST-M1",
            description="Month 1 interest accrual",
            auto_post=True,
        )
        assert entry.status == JournalEntryStatus.POSTED
        assert entry.source_type == JournalSourceType.INTEREST_ACCRUAL

    @pytest.mark.asyncio
    async def test_unbalanced_disbursement_rejected(self):
        """If DR ≠ CR, entry must be rejected."""
        db = AsyncMock()
        with pytest.raises(BalanceError, match="not balanced"):
            await create_journal_entry(
                db,
                lines=[
                    {"gl_account_id": ACCT_PERF_LOANS, "debit_amount": 100000, "credit_amount": 0},
                    {"gl_account_id": ACCT_BANK, "debit_amount": 0, "credit_amount": 99999},
                ],
                source_type=JournalSourceType.LOAN_DISBURSEMENT,
                source_reference="LOAN-BAD",
                description="This should fail",
            )


class TestCreateJournalEntryWrittenOff:
    """Test create_journal_entry for write-off and recovery."""

    def _make_account(self, acct_id, code):
        a = MagicMock(spec=GLAccount)
        a.id = acct_id
        a.account_code = code
        a.name = f"Account {code}"
        a.status = AccountStatus.ACTIVE
        return a

    def _mock_db(self, accounts):
        db = AsyncMock()

        async def mock_execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "gl_accounts" in stmt_str and "IN" in stmt_str.upper():
                result.scalars.return_value.all.return_value = accounts
                return result
            if "gl_currencies" in stmt_str:
                c = MagicMock(spec=Currency)
                c.id = 1
                c.code = "JMD"
                result.scalar_one_or_none.return_value = c
                return result
            if "gl_accounting_periods" in stmt_str:
                p = MagicMock(spec=AccountingPeriod)
                p.id = 1
                p.name = "Feb 2026"
                p.status = PeriodStatus.OPEN
                result.scalar_one_or_none.return_value = p
                return result
            if "max" in stmt_str.lower():
                result.scalar_one_or_none.return_value = None
                return result
            return result

        db.execute = mock_execute
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_provision_entry(self):
        accounts = [
            self._make_account(ACCT_PROV_EXP, "5-1000"),
            self._make_account(ACCT_ALLOWANCE, "2-2000"),
        ]
        db = self._mock_db(accounts)

        entry = await create_journal_entry(
            db,
            lines=[
                {"gl_account_id": ACCT_PROV_EXP, "debit_amount": 40000, "credit_amount": 0,
                 "description": "Provision for expected loss"},
                {"gl_account_id": ACCT_ALLOWANCE, "debit_amount": 0, "credit_amount": 40000,
                 "description": "Increase allowance"},
            ],
            source_type=JournalSourceType.PROVISION,
            source_reference="PROV-TEST",
            description="Provision for delinquent loan",
            auto_post=True,
        )
        assert entry.status == JournalEntryStatus.POSTED
        assert entry.source_type == JournalSourceType.PROVISION

    @pytest.mark.asyncio
    async def test_write_off_entry(self):
        accounts = [
            self._make_account(ACCT_WO_LOANS, "1-2003"),
            self._make_account(ACCT_PERF_LOANS, "1-2001"),
        ]
        db = self._mock_db(accounts)

        entry = await create_journal_entry(
            db,
            lines=[
                {"gl_account_id": ACCT_WO_LOANS, "debit_amount": 40000, "credit_amount": 0,
                 "description": "Reclassify to written-off loans"},
                {"gl_account_id": ACCT_PERF_LOANS, "debit_amount": 0, "credit_amount": 40000,
                 "description": "Remove from performing loans"},
            ],
            source_type=JournalSourceType.WRITE_OFF,
            source_reference="WO-TEST",
            description="Loan written off",
            auto_post=True,
        )
        assert entry.status == JournalEntryStatus.POSTED
        assert entry.source_type == JournalSourceType.WRITE_OFF

    @pytest.mark.asyncio
    async def test_recovery_entry(self):
        accounts = [
            self._make_account(ACCT_BANK, "1-1001"),
            self._make_account(ACCT_REC_INCOME, "4-4000"),
        ]
        db = self._mock_db(accounts)

        entry = await create_journal_entry(
            db,
            lines=[
                {"gl_account_id": ACCT_BANK, "debit_amount": 12000, "credit_amount": 0,
                 "description": "Recovery received"},
                {"gl_account_id": ACCT_REC_INCOME, "debit_amount": 0, "credit_amount": 12000,
                 "description": "Recovery income"},
            ],
            source_type=JournalSourceType.RECOVERY,
            source_reference="REC-TEST",
            description="Recovery on written-off loan",
            auto_post=True,
        )
        assert entry.status == JournalEntryStatus.POSTED
        assert entry.source_type == JournalSourceType.RECOVERY

    @pytest.mark.asyncio
    async def test_write_off_to_closed_period_fails(self):
        """Cannot write off into a closed period."""
        accounts = [
            self._make_account(ACCT_WO_LOANS, "1-2003"),
            self._make_account(ACCT_PERF_LOANS, "1-2001"),
        ]
        db = AsyncMock()

        async def mock_execute(stmt):
            result = MagicMock()
            stmt_str = str(stmt)
            if "gl_accounts" in stmt_str and "IN" in stmt_str.upper():
                result.scalars.return_value.all.return_value = accounts
                return result
            if "gl_currencies" in stmt_str:
                c = MagicMock(spec=Currency)
                c.id = 1
                c.code = "JMD"
                result.scalar_one_or_none.return_value = c
                return result
            if "gl_accounting_periods" in stmt_str:
                p = MagicMock(spec=AccountingPeriod)
                p.id = 1
                p.name = "Jan 2026"
                p.status = PeriodStatus.CLOSED
                result.scalar_one_or_none.return_value = p
                return result
            if "max" in stmt_str.lower():
                result.scalar_one_or_none.return_value = None
                return result
            return result

        db.execute = mock_execute
        db.add = MagicMock()
        db.flush = AsyncMock()

        from app.services.gl.journal_engine import PeriodClosedError

        with pytest.raises(PeriodClosedError, match="Cannot auto-post"):
            await create_journal_entry(
                db,
                lines=[
                    {"gl_account_id": ACCT_WO_LOANS, "debit_amount": 40000, "credit_amount": 0},
                    {"gl_account_id": ACCT_PERF_LOANS, "debit_amount": 0, "credit_amount": 40000},
                ],
                source_type=JournalSourceType.WRITE_OFF,
                source_reference="WO-CLOSED-PERIOD",
                description="This should fail",
                auto_post=True,
            )


# ===================================================================
# Scenario 4: No template → MappingError
# ===================================================================


class TestMissingTemplate:
    """generate_journal_entry must raise MappingError when no template exists."""

    @pytest.mark.asyncio
    async def test_missing_template_raises(self):
        db = AsyncMock()
        with patch(
            "app.services.gl.mapping_engine.get_mapping_for_event",
            return_value=None,
        ):
            with pytest.raises(MappingError, match="No mapping template found"):
                await generate_journal_entry(
                    db,
                    event_type=JournalSourceType.LOAN_DISBURSEMENT,
                    source_reference="LOAN-ORPHAN",
                    amount_breakdown={"principal": 50000, "full_amount": 50000},
                )

    @pytest.mark.asyncio
    async def test_missing_template_dry_run_returns_error(self):
        db = AsyncMock()
        with patch(
            "app.services.gl.mapping_engine.get_mapping_for_event",
            return_value=None,
        ):
            result = await generate_journal_entry(
                db,
                event_type=JournalSourceType.LOAN_DISBURSEMENT,
                source_reference="LOAN-ORPHAN",
                amount_breakdown={"principal": 50000},
                dry_run=True,
            )
            assert "error" in result


# ===================================================================
# Scenario 5: Income statement aggregation from combined scenarios
# ===================================================================


class TestIncomeStatementAggregation:
    """Run a mix of repaid and written-off loans and verify the IS totals."""

    @pytest.mark.asyncio
    async def test_mixed_portfolio_is_totals(self):
        """2 repaid loans + 1 written-off loan → verify revenue & expense totals."""
        events = [
            # --- Loan A: $80,000, fully repaid ---
            (JournalSourceType.LOAN_DISBURSEMENT, "LOAN-A",
             {"principal": Decimal("80000"), "full_amount": Decimal("80000")}),
            (JournalSourceType.INTEREST_ACCRUAL, "LOAN-A-INT-M1",
             {"interest": Decimal("1200")}),
            (JournalSourceType.INTEREST_ACCRUAL, "LOAN-A-INT-M2",
             {"interest": Decimal("1200")}),
            (JournalSourceType.FEE, "LOAN-A-FEE",
             {"fee": Decimal("1600")}),
            (JournalSourceType.REPAYMENT, "PMT-A-FULL",
             {"principal": Decimal("80000"), "full_amount": Decimal("80000")}),

            # --- Loan B: $60,000, fully repaid ---
            (JournalSourceType.LOAN_DISBURSEMENT, "LOAN-B",
             {"principal": Decimal("60000"), "full_amount": Decimal("60000")}),
            (JournalSourceType.INTEREST_ACCRUAL, "LOAN-B-INT-M1",
             {"interest": Decimal("900")}),
            (JournalSourceType.FEE, "LOAN-B-FEE",
             {"fee": Decimal("1200")}),
            (JournalSourceType.REPAYMENT, "PMT-B-FULL",
             {"principal": Decimal("60000"), "full_amount": Decimal("60000")}),

            # --- Loan C: $45,000, written off ---
            (JournalSourceType.LOAN_DISBURSEMENT, "LOAN-C",
             {"principal": Decimal("45000"), "full_amount": Decimal("45000")}),
            (JournalSourceType.INTEREST_ACCRUAL, "LOAN-C-INT-M1",
             {"interest": Decimal("675")}),
            (JournalSourceType.REPAYMENT, "PMT-C-1",
             {"principal": Decimal("5000"), "full_amount": Decimal("5000")}),
            (JournalSourceType.PROVISION, "PROV-C",
             {"full_amount": Decimal("40000")}),
            (JournalSourceType.WRITE_OFF, "WO-C",
             {"principal": Decimal("40000")}),
            (JournalSourceType.RECOVERY, "REC-C",
             {"full_amount": Decimal("8000")}),
        ]

        revenue = {ACCT_INT_INCOME: 0.0, ACCT_FEE_INCOME: 0.0, ACCT_REC_INCOME: 0.0}
        expenses = {ACCT_PROV_EXP: 0.0}
        wo_balance = {ACCT_WO_LOANS: 0.0}

        for event_type, ref, breakdown in events:
            result = await _dry_run_entry(event_type, ref, breakdown)
            _assert_je_balanced(result)
            for ln in result["lines"]:
                aid = ln["gl_account_id"]
                if aid in revenue:
                    revenue[aid] += ln["credit_amount"]
                if aid in expenses:
                    expenses[aid] += ln["debit_amount"]
                if aid in wo_balance:
                    wo_balance[aid] += ln["debit_amount"] - ln["credit_amount"]

        # Interest income: 1200 + 1200 + 900 + 675 = 3975
        assert revenue[ACCT_INT_INCOME] == 3975.0
        # Fee income: 1600 + 1200 = 2800
        assert revenue[ACCT_FEE_INCOME] == 2800.0
        # Recovery income: 8000
        assert revenue[ACCT_REC_INCOME] == 8000.0
        # Total revenue: 14,775
        total_rev = sum(revenue.values())
        assert total_rev == 14775.0

        # Provision expense: 40,000
        assert expenses[ACCT_PROV_EXP] == 40000.0
        # Total expenses: 40,000 (write-off is reclassification, not expense)
        total_exp = sum(expenses.values())
        assert total_exp == 40000.0

        # Written-off loans: 40,000
        assert wo_balance[ACCT_WO_LOANS] == 40000.0

        # Net income: 14,775 − 40,000 = −25,225 (net loss)
        net = total_rev - total_exp
        assert net == -25225.0
