"""Seed data for the General Ledger module.

Creates (all idempotent):
- Currencies (JMD, USD, TTD, BBD)
- Default Chart of Accounts (levels 1-3)
- Accounting periods for fiscal years 2025 and 2026
- Default GL mapping templates for all core loan lifecycle events
"""

import calendar
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gl import (
    AccountingPeriod,
    Currency,
    GLAccount,
    GLMappingTemplate,
    GLMappingTemplateLine,
    AccountCategory,
    AccountType,
    AccountStatus,
    JournalSourceType,
    MappingLineType,
    MappingAmountSource,
    PeriodStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: get-or-create
# ---------------------------------------------------------------------------

async def _get_or_create_currency(
    db: AsyncSession, code: str, name: str, symbol: str, is_base: bool = False
) -> Currency:
    result = await db.execute(
        select(Currency).where(Currency.code == code)
    )
    cur = result.scalar_one_or_none()
    if cur:
        return cur
    cur = Currency(
        code=code, name=name, symbol=symbol,
        decimal_places=2, is_base=is_base, is_active=True,
    )
    db.add(cur)
    await db.flush()
    return cur


async def _get_or_create_account(
    db: AsyncSession,
    *,
    code: str,
    name: str,
    category: AccountCategory,
    account_type: AccountType,
    currency_id: int,
    parent_id: int | None = None,
    level: int = 1,
    is_control: bool = False,
    is_system: bool = True,
) -> GLAccount:
    result = await db.execute(
        select(GLAccount).where(GLAccount.account_code == code)
    )
    acct = result.scalar_one_or_none()
    if acct:
        return acct
    acct = GLAccount(
        account_code=code,
        name=name,
        account_category=category,
        account_type=account_type,
        currency_id=currency_id,
        parent_id=parent_id,
        level=level,
        is_control_account=is_control,
        is_system_account=is_system,
        status=AccountStatus.ACTIVE,
    )
    db.add(acct)
    await db.flush()
    return acct


# ---------------------------------------------------------------------------
# Currencies
# ---------------------------------------------------------------------------

async def _seed_currencies(db: AsyncSession) -> Currency:
    """Seed the four supported currencies and return the base (JMD)."""
    jmd = await _get_or_create_currency(db, "JMD", "Jamaican Dollar", "$", is_base=True)
    await _get_or_create_currency(db, "USD", "United States Dollar", "$")
    await _get_or_create_currency(db, "TTD", "Trinidad and Tobago Dollar", "$")
    await _get_or_create_currency(db, "BBD", "Barbados Dollar", "$")
    return jmd


# ---------------------------------------------------------------------------
# Chart of Accounts
# ---------------------------------------------------------------------------

async def _seed_coa(db: AsyncSession, base_currency_id: int) -> None:
    """Seed the default Chart of Accounts (3 levels)."""
    A = AccountCategory.ASSET
    L = AccountCategory.LIABILITY
    E = AccountCategory.EQUITY
    R = AccountCategory.REVENUE
    X = AccountCategory.EXPENSE
    DR = AccountType.DEBIT
    CR = AccountType.CREDIT
    cid = base_currency_id

    # Level 1 — top categories
    assets = await _get_or_create_account(db, code="1-0000", name="Assets",       category=A, account_type=DR, currency_id=cid, level=1)
    liabs  = await _get_or_create_account(db, code="2-0000", name="Liabilities",  category=L, account_type=CR, currency_id=cid, level=1)
    equity = await _get_or_create_account(db, code="3-0000", name="Equity",       category=E, account_type=CR, currency_id=cid, level=1)
    rev    = await _get_or_create_account(db, code="4-0000", name="Revenue",      category=R, account_type=CR, currency_id=cid, level=1)
    exp    = await _get_or_create_account(db, code="5-0000", name="Expenses",     category=X, account_type=DR, currency_id=cid, level=1)

    # Level 2 — sub-groups (Assets)
    cash   = await _get_or_create_account(db, code="1-1000", name="Cash and Bank",         category=A, account_type=DR, currency_id=cid, parent_id=assets.id, level=2)
    lport  = await _get_or_create_account(db, code="1-2000", name="Loan Portfolio",        category=A, account_type=DR, currency_id=cid, parent_id=assets.id, level=2, is_control=True)
    intrcv = await _get_or_create_account(db, code="1-3000", name="Interest Receivable",   category=A, account_type=DR, currency_id=cid, parent_id=assets.id, level=2)
    feercv = await _get_or_create_account(db, code="1-4000", name="Fee Receivable",        category=A, account_type=DR, currency_id=cid, parent_id=assets.id, level=2)
    await _get_or_create_account(db, code="1-5000", name="Other Assets",          category=A, account_type=DR, currency_id=cid, parent_id=assets.id, level=2)
    await _get_or_create_account(db, code="1-9000", name="Suspense - Assets",     category=A, account_type=DR, currency_id=cid, parent_id=assets.id, level=2)

    # Level 2 — sub-groups (Liabilities)
    await _get_or_create_account(db, code="2-1000", name="Customer Deposits",         category=L, account_type=CR, currency_id=cid, parent_id=liabs.id, level=2)
    await _get_or_create_account(db, code="2-2000", name="Allowance for Loan Losses", category=L, account_type=CR, currency_id=cid, parent_id=liabs.id, level=2)
    await _get_or_create_account(db, code="2-3000", name="Other Liabilities",         category=L, account_type=CR, currency_id=cid, parent_id=liabs.id, level=2)
    await _get_or_create_account(db, code="2-4000", name="Insurance Payable",         category=L, account_type=CR, currency_id=cid, parent_id=liabs.id, level=2)

    # Level 2 — sub-groups (Equity)
    await _get_or_create_account(db, code="3-1000", name="Share Capital",      category=E, account_type=CR, currency_id=cid, parent_id=equity.id, level=2)
    await _get_or_create_account(db, code="3-2000", name="Retained Earnings",  category=E, account_type=CR, currency_id=cid, parent_id=equity.id, level=2)

    # Level 2 — sub-groups (Revenue)
    await _get_or_create_account(db, code="4-1000", name="Interest Income",           category=R, account_type=CR, currency_id=cid, parent_id=rev.id, level=2)
    await _get_or_create_account(db, code="4-2000", name="Fee Income",                category=R, account_type=CR, currency_id=cid, parent_id=rev.id, level=2)
    await _get_or_create_account(db, code="4-3000", name="Late Fee Income",           category=R, account_type=CR, currency_id=cid, parent_id=rev.id, level=2)
    await _get_or_create_account(db, code="4-4000", name="Recovery Income",           category=R, account_type=CR, currency_id=cid, parent_id=rev.id, level=2)
    await _get_or_create_account(db, code="4-5000", name="Prepayment Penalty Income", category=R, account_type=CR, currency_id=cid, parent_id=rev.id, level=2)

    # Level 2 — sub-groups (Expenses)
    await _get_or_create_account(db, code="5-1000", name="Provision Expense",  category=X, account_type=DR, currency_id=cid, parent_id=exp.id, level=2)
    await _get_or_create_account(db, code="5-2000", name="Operating Expenses", category=X, account_type=DR, currency_id=cid, parent_id=exp.id, level=2)
    await _get_or_create_account(db, code="5-3000", name="Write-Off Expense",  category=X, account_type=DR, currency_id=cid, parent_id=exp.id, level=2)

    # Level 3 — detail / posting accounts
    await _get_or_create_account(db, code="1-1001", name="Operating Bank Account",              category=A, account_type=DR, currency_id=cid, parent_id=cash.id,   level=3)
    await _get_or_create_account(db, code="1-1002", name="Disbursement Clearing",               category=A, account_type=DR, currency_id=cid, parent_id=cash.id,   level=3)
    await _get_or_create_account(db, code="1-2001", name="Performing Loans",                    category=A, account_type=DR, currency_id=cid, parent_id=lport.id,  level=3)
    await _get_or_create_account(db, code="1-2002", name="Non-Performing Loans",                category=A, account_type=DR, currency_id=cid, parent_id=lport.id,  level=3)
    await _get_or_create_account(db, code="1-2003", name="Written-Off Loans",                   category=A, account_type=DR, currency_id=cid, parent_id=lport.id,  level=3)
    await _get_or_create_account(db, code="1-3001", name="Interest Receivable - Performing",    category=A, account_type=DR, currency_id=cid, parent_id=intrcv.id, level=3)
    await _get_or_create_account(db, code="1-3002", name="Interest Receivable - Non-Performing",category=A, account_type=DR, currency_id=cid, parent_id=intrcv.id, level=3)
    await _get_or_create_account(db, code="1-4001", name="Origination Fee Receivable",          category=A, account_type=DR, currency_id=cid, parent_id=feercv.id, level=3)
    await _get_or_create_account(db, code="1-4002", name="Late Fee Receivable",                 category=A, account_type=DR, currency_id=cid, parent_id=feercv.id, level=3)


# ---------------------------------------------------------------------------
# Accounting periods
# ---------------------------------------------------------------------------

async def _seed_periods(db: AsyncSession) -> None:
    """Create monthly accounting periods for FY 2025 and 2026 if missing."""
    for year in (2025, 2026):
        existing = await db.execute(
            select(AccountingPeriod.id)
            .where(AccountingPeriod.fiscal_year == year)
            .limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            continue

        for month in range(1, 13):
            last_day = calendar.monthrange(year, month)[1]
            period = AccountingPeriod(
                fiscal_year=year,
                period_number=month,
                name=f"{calendar.month_abbr[month]} {year}",
                start_date=date(year, month, 1),
                end_date=date(year, month, last_day),
                status=PeriodStatus.OPEN,
            )
            db.add(period)
    await db.flush()


# ---------------------------------------------------------------------------
# Mapping templates
# ---------------------------------------------------------------------------

# Each tuple: (template_name, event_type, description, lines)
# Lines: list of (line_type, account_code, amount_source, description_template)
MAPPING_TEMPLATES = [
    (
        "Loan Disbursement",
        JournalSourceType.LOAN_DISBURSEMENT,
        "Debit the loan portfolio, credit the bank account when a loan is disbursed.",
        [
            (MappingLineType.DEBIT,  "1-2001", MappingAmountSource.PRINCIPAL,
             "Loan disbursement principal — {source_reference}"),
            (MappingLineType.CREDIT, "1-1001", MappingAmountSource.PRINCIPAL,
             "Bank outflow for disbursement — {source_reference}"),
        ],
    ),
    (
        "Loan Repayment",
        JournalSourceType.REPAYMENT,
        "Debit the bank account, credit the loan portfolio when a repayment is received.",
        [
            (MappingLineType.DEBIT,  "1-1001", MappingAmountSource.FULL_AMOUNT,
             "Bank inflow for repayment — {source_reference}"),
            (MappingLineType.CREDIT, "1-2001", MappingAmountSource.FULL_AMOUNT,
             "Loan repayment applied — {source_reference}"),
        ],
    ),
    (
        "Interest Accrual",
        JournalSourceType.INTEREST_ACCRUAL,
        "Recognise interest income and receivable at period end.",
        [
            (MappingLineType.DEBIT,  "1-3001", MappingAmountSource.INTEREST,
             "Interest receivable accrual — {source_reference}"),
            (MappingLineType.CREDIT, "4-1000", MappingAmountSource.INTEREST,
             "Interest income recognised — {source_reference}"),
        ],
    ),
    (
        "Origination Fee",
        JournalSourceType.FEE,
        "Recognise origination fee income.",
        [
            (MappingLineType.DEBIT,  "1-4001", MappingAmountSource.FEE,
             "Fee receivable — {source_reference}"),
            (MappingLineType.CREDIT, "4-2000", MappingAmountSource.FEE,
             "Fee income recognised — {source_reference}"),
        ],
    ),
    (
        "Loan Loss Provision",
        JournalSourceType.PROVISION,
        "Record provision expense and increase the allowance for loan losses.",
        [
            (MappingLineType.DEBIT,  "5-1000", MappingAmountSource.FULL_AMOUNT,
             "Provision expense — {source_reference}"),
            (MappingLineType.CREDIT, "2-2000", MappingAmountSource.FULL_AMOUNT,
             "Increase allowance for loan losses — {source_reference}"),
        ],
    ),
    (
        "Loan Write-Off",
        JournalSourceType.WRITE_OFF,
        "Reclassify a defaulted loan from performing to written-off.",
        [
            (MappingLineType.DEBIT,  "1-2003", MappingAmountSource.PRINCIPAL,
             "Reclassify to written-off loans — {source_reference}"),
            (MappingLineType.CREDIT, "1-2001", MappingAmountSource.PRINCIPAL,
             "Remove from performing loans — {source_reference}"),
        ],
    ),
    (
        "Loan Recovery",
        JournalSourceType.RECOVERY,
        "Record cash recovered on a previously written-off loan.",
        [
            (MappingLineType.DEBIT,  "1-1001", MappingAmountSource.FULL_AMOUNT,
             "Bank inflow — recovery — {source_reference}"),
            (MappingLineType.CREDIT, "4-4000", MappingAmountSource.FULL_AMOUNT,
             "Recovery income — {source_reference}"),
        ],
    ),
]


async def _seed_mapping_templates(db: AsyncSession) -> None:
    """Create default global mapping templates if none exist."""
    existing = await db.execute(select(GLMappingTemplate.id).limit(1))
    if existing.scalar_one_or_none() is not None:
        return

    for name, event_type, description, lines in MAPPING_TEMPLATES:
        template = GLMappingTemplate(
            name=name,
            event_type=event_type,
            credit_product_id=None,
            is_active=True,
            conditions=None,
            description=description,
        )
        db.add(template)
        await db.flush()

        for line_type, account_code, amount_source, desc_template in lines:
            result = await db.execute(
                select(GLAccount.id).where(GLAccount.account_code == account_code)
            )
            account_id = result.scalar_one()
            tpl_line = GLMappingTemplateLine(
                template_id=template.id,
                line_type=line_type,
                gl_account_id=account_id,
                amount_source=amount_source,
                description_template=desc_template,
            )
            db.add(tpl_line)

    await db.flush()


# ---------------------------------------------------------------------------
# Backfill: create JEs for existing disbursements / payments
# ---------------------------------------------------------------------------

async def _backfill_existing_transactions(db: AsyncSession) -> None:
    """Create GL journal entries for historical disbursements and payments
    that were recorded before mapping templates existed.  Idempotent —
    checks source_reference to avoid duplicates."""
    from app.models.disbursement import Disbursement, DisbursementStatus
    from app.models.payment import Payment, PaymentStatus
    from app.models.gl import JournalEntry, JournalSourceType
    from app.services.gl.journal_engine import create_journal_entry
    from app.services.gl.mapping_engine import generate_journal_entry, MappingError
    from decimal import Decimal
    from sqlalchemy import func as sa_func

    created = 0

    # ── Initial capitalisation ─────────────────────────
    # Every lending company needs starting capital.  If no SYSTEM JE
    # with ref "OPENING-BALANCE" exists yet, calculate total completed
    # disbursements and create: DR Operating Bank Account, CR Share Capital
    # for 120 % of that total (realistic headroom).
    existing_ob = await db.execute(
        select(JournalEntry.id).where(
            JournalEntry.source_type == JournalSourceType.SYSTEM,
            JournalEntry.source_reference == "OPENING-BALANCE",
        ).limit(1)
    )
    if existing_ob.scalar_one_or_none() is None:
        total_disb = await db.execute(
            select(sa_func.coalesce(sa_func.sum(Disbursement.amount), 0))
            .where(Disbursement.status == DisbursementStatus.COMPLETED)
        )
        disb_sum = Decimal(str(total_disb.scalar() or 0))
        if disb_sum > 0:
            capital = (disb_sum * Decimal("1.2")).quantize(Decimal("1.00"))
            bank_acct = await db.execute(
                select(GLAccount.id).where(GLAccount.account_code == "1-1001")
            )
            equity_acct = await db.execute(
                select(GLAccount.id).where(GLAccount.account_code == "3-1000")
            )
            bank_id = bank_acct.scalar_one()
            equity_id = equity_acct.scalar_one()

            # Find earliest disbursement date for the opening entry
            earliest = await db.execute(
                select(sa_func.min(Disbursement.disbursed_at))
                .where(Disbursement.status == DisbursementStatus.COMPLETED)
            )
            earliest_dt = earliest.scalar()
            eff = earliest_dt.date() if earliest_dt else date(2025, 1, 1)

            await create_journal_entry(
                db,
                lines=[
                    {
                        "gl_account_id": bank_id,
                        "debit_amount": float(capital),
                        "credit_amount": 0.0,
                        "description": "Initial capitalisation — opening bank balance",
                    },
                    {
                        "gl_account_id": equity_id,
                        "debit_amount": 0.0,
                        "credit_amount": float(capital),
                        "description": "Initial capitalisation — share capital",
                    },
                ],
                source_type=JournalSourceType.SYSTEM,
                source_reference="OPENING-BALANCE",
                description="Company capitalisation — opening balance",
                effective_date=eff,
                currency_code="JMD",
                auto_post=True,
            )
            created += 1
            logger.info("GL backfill: created opening balance JE for $%s JMD", capital)

    # ── Disbursements ──────────────────────────────────
    disb_result = await db.execute(
        select(Disbursement)
        .where(Disbursement.status == DisbursementStatus.COMPLETED)
        .order_by(Disbursement.disbursed_at)
    )
    for disb in disb_result.scalars().all():
        source_ref = f"LOAN-{disb.loan_application_id}"
        existing = await db.execute(
            select(JournalEntry.id).where(
                JournalEntry.source_type == JournalSourceType.LOAN_DISBURSEMENT,
                JournalEntry.source_reference == source_ref,
            ).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            continue
        try:
            eff_date = disb.disbursed_at.date() if disb.disbursed_at else None
            await generate_journal_entry(
                db,
                event_type=JournalSourceType.LOAN_DISBURSEMENT,
                source_reference=source_ref,
                amount_breakdown={
                    "principal": Decimal(str(disb.amount)),
                    "full_amount": Decimal(str(disb.amount)),
                },
                description=f"Loan disbursement — {source_ref}",
                effective_date=eff_date,
                currency_code="JMD",
                created_by=disb.disbursed_by,
                auto_post=True,
            )
            created += 1
        except (MappingError, Exception) as exc:
            logger.warning("Backfill: skipping disbursement %s — %s", source_ref, exc)

    # ── Payments ───────────────────────────────────────
    pay_result = await db.execute(
        select(Payment)
        .where(Payment.status == PaymentStatus.COMPLETED)
        .order_by(Payment.payment_date)
    )
    for pay in pay_result.scalars().all():
        source_ref = f"PMT-{pay.id}"
        existing = await db.execute(
            select(JournalEntry.id).where(
                JournalEntry.source_type == JournalSourceType.REPAYMENT,
                JournalEntry.source_reference == source_ref,
            ).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            continue
        try:
            await generate_journal_entry(
                db,
                event_type=JournalSourceType.REPAYMENT,
                source_reference=source_ref,
                amount_breakdown={
                    "principal": Decimal(str(pay.amount)),
                    "full_amount": Decimal(str(pay.amount)),
                },
                description=f"Loan repayment — {source_ref} for LOAN-{pay.loan_application_id}",
                effective_date=pay.payment_date,
                currency_code="JMD",
                created_by=pay.recorded_by,
                loan_reference=f"LOAN-{pay.loan_application_id}",
                auto_post=True,
            )
            created += 1
        except (MappingError, Exception) as exc:
            logger.warning("Backfill: skipping payment %s — %s", source_ref, exc)

    # ── Interest Accruals (from paid / overdue schedule rows) ─────
    from app.models.payment import PaymentSchedule, ScheduleStatus

    schedules = await db.execute(
        select(PaymentSchedule)
        .where(
            PaymentSchedule.interest > 0,
            PaymentSchedule.status.in_([
                ScheduleStatus.PAID,
                ScheduleStatus.OVERDUE,
                ScheduleStatus.DUE,
                ScheduleStatus.PARTIAL,
            ]),
        )
        .order_by(PaymentSchedule.due_date)
    )
    for sched in schedules.scalars().all():
        source_ref = f"INT-LOAN-{sched.loan_application_id}-S{sched.installment_number}"
        existing = await db.execute(
            select(JournalEntry.id).where(
                JournalEntry.source_type == JournalSourceType.INTEREST_ACCRUAL,
                JournalEntry.source_reference == source_ref,
            ).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            continue
        try:
            await generate_journal_entry(
                db,
                event_type=JournalSourceType.INTEREST_ACCRUAL,
                source_reference=source_ref,
                amount_breakdown={
                    "interest": Decimal(str(sched.interest)),
                },
                description=f"Interest accrual — installment {sched.installment_number} of LOAN-{sched.loan_application_id}",
                effective_date=sched.due_date,
                currency_code="JMD",
                loan_reference=f"LOAN-{sched.loan_application_id}",
                auto_post=True,
            )
            created += 1
        except (MappingError, Exception) as exc:
            logger.warning("Backfill: skipping interest accrual %s — %s", source_ref, exc)

    # ── Origination Fees ────────────────────────────────
    # If schedule rows have fees > 0 use those; otherwise generate
    # an origination fee for each disbursement (2 % of principal).
    fee_schedules = await db.execute(
        select(PaymentSchedule)
        .where(
            PaymentSchedule.fee > 0,
            PaymentSchedule.status.in_([
                ScheduleStatus.PAID,
                ScheduleStatus.OVERDUE,
                ScheduleStatus.DUE,
                ScheduleStatus.PARTIAL,
            ]),
        )
        .order_by(PaymentSchedule.due_date)
    )
    fee_rows = fee_schedules.scalars().all()
    if fee_rows:
        for sched in fee_rows:
            source_ref = f"FEE-LOAN-{sched.loan_application_id}-S{sched.installment_number}"
            existing = await db.execute(
                select(JournalEntry.id).where(
                    JournalEntry.source_type == JournalSourceType.FEE,
                    JournalEntry.source_reference == source_ref,
                ).limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                continue
            try:
                await generate_journal_entry(
                    db,
                    event_type=JournalSourceType.FEE,
                    source_reference=source_ref,
                    amount_breakdown={"fee": Decimal(str(sched.fee))},
                    description=f"Fee — installment {sched.installment_number} of LOAN-{sched.loan_application_id}",
                    effective_date=sched.due_date,
                    currency_code="JMD",
                    loan_reference=f"LOAN-{sched.loan_application_id}",
                    auto_post=True,
                )
                created += 1
            except (MappingError, Exception) as exc:
                logger.warning("Backfill: skipping fee %s — %s", source_ref, exc)
    else:
        # No schedule-level fees — generate a 2 % origination fee per disbursement
        disb_result2 = await db.execute(
            select(Disbursement)
            .where(Disbursement.status == DisbursementStatus.COMPLETED)
            .order_by(Disbursement.disbursed_at)
        )
        for disb in disb_result2.scalars().all():
            source_ref = f"FEE-LOAN-{disb.loan_application_id}"
            existing = await db.execute(
                select(JournalEntry.id).where(
                    JournalEntry.source_type == JournalSourceType.FEE,
                    JournalEntry.source_reference == source_ref,
                ).limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                continue
            fee_amount = (Decimal(str(disb.amount)) * Decimal("0.02")).quantize(Decimal("1.00"))
            if fee_amount <= 0:
                continue
            try:
                eff_date = disb.disbursed_at.date() if disb.disbursed_at else None
                await generate_journal_entry(
                    db,
                    event_type=JournalSourceType.FEE,
                    source_reference=source_ref,
                    amount_breakdown={"fee": fee_amount},
                    description=f"Origination fee (2%) — LOAN-{disb.loan_application_id}",
                    effective_date=eff_date,
                    currency_code="JMD",
                    loan_reference=f"LOAN-{disb.loan_application_id}",
                    auto_post=True,
                )
                created += 1
            except (MappingError, Exception) as exc:
                logger.warning("Backfill: skipping origination fee %s — %s", source_ref, exc)

    # ── Provisions for overdue installments ───────────────────────
    overdue_schedules = await db.execute(
        select(PaymentSchedule)
        .where(PaymentSchedule.status == ScheduleStatus.OVERDUE)
        .order_by(PaymentSchedule.due_date)
    )
    for sched in overdue_schedules.scalars().all():
        source_ref = f"PROV-LOAN-{sched.loan_application_id}-S{sched.installment_number}"
        existing = await db.execute(
            select(JournalEntry.id).where(
                JournalEntry.source_type == JournalSourceType.PROVISION,
                JournalEntry.source_reference == source_ref,
            ).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            continue
        # Provision = unpaid portion of the overdue installment
        unpaid = Decimal(str(sched.amount_due)) - Decimal(str(sched.amount_paid))
        if unpaid <= 0:
            continue
        try:
            await generate_journal_entry(
                db,
                event_type=JournalSourceType.PROVISION,
                source_reference=source_ref,
                amount_breakdown={
                    "full_amount": unpaid,
                },
                description=f"Provision for overdue installment {sched.installment_number} of LOAN-{sched.loan_application_id}",
                effective_date=sched.due_date,
                currency_code="JMD",
                loan_reference=f"LOAN-{sched.loan_application_id}",
                auto_post=True,
            )
            created += 1
        except (MappingError, Exception) as exc:
            logger.warning("Backfill: skipping provision %s — %s", source_ref, exc)

    # ── Simulated write-off + recovery for demo purposes ──────────
    # If there are no write-off JEs yet, pick the loan with the most
    # overdue installments and simulate a partial write-off + recovery.
    existing_wo = await db.execute(
        select(JournalEntry.id).where(
            JournalEntry.source_type == JournalSourceType.WRITE_OFF,
        ).limit(1)
    )
    if existing_wo.scalar_one_or_none() is None:
        # Find the loan with the highest unpaid overdue amount
        from sqlalchemy import desc as sa_desc
        worst_loan = await db.execute(
            select(
                PaymentSchedule.loan_application_id,
                sa_func.sum(PaymentSchedule.amount_due - PaymentSchedule.amount_paid).label("total_unpaid"),
            )
            .where(PaymentSchedule.status == ScheduleStatus.OVERDUE)
            .group_by(PaymentSchedule.loan_application_id)
            .order_by(sa_desc("total_unpaid"))
            .limit(1)
        )
        worst = worst_loan.first()
        if worst and worst.total_unpaid and float(worst.total_unpaid) > 0:
            loan_id = worst.loan_application_id
            write_off_amount = Decimal(str(worst.total_unpaid)).quantize(Decimal("1.00"))
            source_ref_wo = f"WO-LOAN-{loan_id}"
            try:
                await generate_journal_entry(
                    db,
                    event_type=JournalSourceType.WRITE_OFF,
                    source_reference=source_ref_wo,
                    amount_breakdown={
                        "principal": write_off_amount,
                    },
                    description=f"Write-off of delinquent LOAN-{loan_id}",
                    currency_code="JMD",
                    loan_reference=f"LOAN-{loan_id}",
                    auto_post=True,
                )
                created += 1
                logger.info("GL backfill: wrote off $%s for LOAN-%s", write_off_amount, loan_id)

                # Simulate partial recovery (30% of written-off amount)
                recovery_amount = (write_off_amount * Decimal("0.30")).quantize(Decimal("1.00"))
                if recovery_amount > 0:
                    source_ref_rec = f"REC-LOAN-{loan_id}"
                    await generate_journal_entry(
                        db,
                        event_type=JournalSourceType.RECOVERY,
                        source_reference=source_ref_rec,
                        amount_breakdown={
                            "full_amount": recovery_amount,
                        },
                        description=f"Partial recovery on written-off LOAN-{loan_id}",
                        currency_code="JMD",
                        loan_reference=f"LOAN-{loan_id}",
                        auto_post=True,
                    )
                    created += 1
                    logger.info("GL backfill: recovered $%s for LOAN-%s", recovery_amount, loan_id)
            except (MappingError, Exception) as exc:
                logger.warning("Backfill: skipping write-off for LOAN-%s — %s", loan_id, exc)

    if created:
        logger.info("GL backfill: created %d journal entries for existing transactions", created)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def seed_gl_data(db: AsyncSession) -> None:
    """Seed all GL reference data and backfill historical transactions (idempotent)."""
    jmd = await _seed_currencies(db)
    await _seed_coa(db, jmd.id)
    await _seed_periods(db)
    await _seed_mapping_templates(db)
    await db.commit()
    logger.info("GL seed data applied (currencies, COA, periods, mapping templates)")

    # Backfill in a fresh transaction so templates are visible
    await _backfill_existing_transactions(db)
    await db.commit()
    logger.info("GL backfill complete")
