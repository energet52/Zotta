"""General Ledger module — all GL tables, seed currencies and default COA.

Revision ID: 012
Revises: 011
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Enums -----------------------------------------------------------------
    account_category = postgresql.ENUM(
        "asset", "liability", "equity", "revenue", "expense",
        name="accountcategory", create_type=True,
    )
    account_type = postgresql.ENUM("debit", "credit", name="accounttype", create_type=True)
    account_status = postgresql.ENUM("active", "frozen", "closed", name="accountstatus", create_type=True)
    period_status = postgresql.ENUM("open", "soft_close", "closed", "locked", name="periodstatus", create_type=True)
    je_status = postgresql.ENUM(
        "draft", "pending_approval", "approved", "posted", "reversed", "rejected",
        name="journalentrystatus", create_type=True,
    )
    je_source = postgresql.ENUM(
        "manual", "loan_disbursement", "repayment", "interest_accrual", "fee",
        "provision", "write_off", "recovery", "reversal", "adjustment", "system",
        name="journalsourcetype", create_type=True,
    )
    accrual_batch_type = postgresql.ENUM(
        "interest_accrual", "provision", "fee",
        name="accrualbatchtype", create_type=True,
    )
    accrual_batch_status = postgresql.ENUM(
        "pending", "processing", "completed", "failed",
        name="accrualbatchstatus", create_type=True,
    )
    mapping_line_type = postgresql.ENUM("debit", "credit", name="mappinglinetype", create_type=True)
    mapping_amount_source = postgresql.ENUM(
        "principal", "interest", "fee", "full_amount", "custom",
        name="mappingamountsource", create_type=True,
    )
    anomaly_type = postgresql.ENUM(
        "amount", "pattern", "sequence", "balance", "velocity",
        name="anomalytype", create_type=True,
    )
    anomaly_status = postgresql.ENUM("open", "reviewed", "dismissed", name="anomalystatus", create_type=True)

    # Create enums
    for e in [account_category, account_type, account_status, period_status,
              je_status, je_source, accrual_batch_type, accrual_batch_status,
              mapping_line_type, mapping_amount_source, anomaly_type, anomaly_status]:
        e.create(op.get_bind(), checkfirst=True)

    # -- Tables ----------------------------------------------------------------

    op.create_table(
        "gl_currencies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(3), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("decimal_places", sa.Integer, default=2, nullable=False),
        sa.Column("is_base", sa.Boolean, default=False, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "gl_accounts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("account_code", sa.String(30), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("account_category", account_category, nullable=False),
        sa.Column("account_type", account_type, nullable=False),
        sa.Column("currency_id", sa.Integer, sa.ForeignKey("gl_currencies.id"), nullable=False),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("gl_accounts.id"), nullable=True),
        sa.Column("level", sa.Integer, default=1, nullable=False),
        sa.Column("is_control_account", sa.Boolean, default=False),
        sa.Column("is_system_account", sa.Boolean, default=False),
        sa.Column("status", account_status, default="active", nullable=False),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_gl_accounts_code", "gl_accounts", ["account_code"])
    op.create_index("ix_gl_accounts_category", "gl_accounts", ["account_category"])
    op.create_index("ix_gl_accounts_parent", "gl_accounts", ["parent_id"])

    op.create_table(
        "gl_account_audit",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("gl_account_id", sa.Integer, sa.ForeignKey("gl_accounts.id"), nullable=False, index=True),
        sa.Column("field_changed", sa.String(100), nullable=False),
        sa.Column("old_value", sa.Text, nullable=True),
        sa.Column("new_value", sa.Text, nullable=True),
        sa.Column("changed_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "gl_accounting_periods",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fiscal_year", sa.Integer, nullable=False, index=True),
        sa.Column("period_number", sa.Integer, nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("status", period_status, default="open", nullable=False),
        sa.Column("closed_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("fiscal_year", "period_number", name="uq_fiscal_period"),
    )

    op.create_table(
        "gl_journal_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("entry_number", sa.String(20), unique=True, nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("posting_date", sa.Date, nullable=True),
        sa.Column("accounting_period_id", sa.Integer, sa.ForeignKey("gl_accounting_periods.id"), nullable=True),
        sa.Column("source_type", je_source, nullable=False),
        sa.Column("source_reference", sa.String(100), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("currency_id", sa.Integer, sa.ForeignKey("gl_currencies.id"), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(10, 6), default=1.0, nullable=False),
        sa.Column("status", je_status, default="draft", nullable=False),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("posted_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_of_id", sa.Integer, sa.ForeignKey("gl_journal_entries.id"), nullable=True),
        sa.Column("reversed_by_id", sa.Integer, sa.ForeignKey("gl_journal_entries.id"), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("narrative", sa.Text, nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
    )
    op.create_index("ix_gl_je_entry_number", "gl_journal_entries", ["entry_number"])
    op.create_index("ix_gl_je_transaction_date", "gl_journal_entries", ["transaction_date"])
    op.create_index("ix_gl_je_source", "gl_journal_entries", ["source_type", "source_reference"])
    op.create_index("ix_gl_je_status", "gl_journal_entries", ["status"])

    op.create_table(
        "gl_journal_entry_lines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("journal_entry_id", sa.Integer, sa.ForeignKey("gl_journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer, nullable=False),
        sa.Column("gl_account_id", sa.Integer, sa.ForeignKey("gl_accounts.id"), nullable=False),
        sa.Column("debit_amount", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("credit_amount", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("base_currency_amount", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("branch", sa.String(100), nullable=True),
        sa.Column("loan_reference", sa.String(100), nullable=True),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.CheckConstraint(
            "(debit_amount = 0 AND credit_amount > 0) OR "
            "(debit_amount > 0 AND credit_amount = 0) OR "
            "(debit_amount = 0 AND credit_amount = 0)",
            name="ck_je_line_debit_or_credit",
        ),
    )
    op.create_index("ix_gl_jel_account", "gl_journal_entry_lines", ["gl_account_id"])
    op.create_index("ix_gl_jel_entry", "gl_journal_entry_lines", ["journal_entry_id"])

    # -- Mapping templates (Phase 2) ------------------------------------------
    op.create_table(
        "gl_mapping_templates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("event_type", je_source, nullable=False),
        sa.Column("credit_product_id", sa.Integer, sa.ForeignKey("credit_products.id"), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("conditions", sa.JSON, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "gl_mapping_template_lines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("gl_mapping_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_type", mapping_line_type, nullable=False),
        sa.Column("gl_account_id", sa.Integer, sa.ForeignKey("gl_accounts.id"), nullable=False),
        sa.Column("amount_source", mapping_amount_source, nullable=False),
        sa.Column("description_template", sa.Text, nullable=True),
    )

    op.create_table(
        "gl_accrual_batches",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("batch_type", accrual_batch_type, nullable=False),
        sa.Column("period_id", sa.Integer, sa.ForeignKey("gl_accounting_periods.id"), nullable=False),
        sa.Column("status", accrual_batch_status, default="pending", nullable=False),
        sa.Column("loan_count", sa.Integer, default=0, nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 2), default=0, nullable=False),
        sa.Column("journal_entry_id", sa.Integer, sa.ForeignKey("gl_journal_entries.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_log", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # -- Filter presets / Export / Anomalies (Phases 3-5) ----------------------
    op.create_table(
        "gl_filter_presets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("filters", sa.JSON, nullable=False),
        sa.Column("is_shared", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "gl_export_schedules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("filters", sa.JSON, nullable=True),
        sa.Column("columns", sa.JSON, nullable=True),
        sa.Column("schedule_cron", sa.String(100), nullable=False),
        sa.Column("recipients", sa.JSON, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "gl_export_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("export_type", sa.String(50), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("filters", sa.JSON, nullable=True),
        sa.Column("row_count", sa.Integer, default=0, nullable=False),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "gl_anomalies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("journal_entry_id", sa.Integer, sa.ForeignKey("gl_journal_entries.id"), nullable=False, index=True),
        sa.Column("anomaly_type", anomaly_type, nullable=False),
        sa.Column("risk_score", sa.Integer, nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column("status", anomaly_status, default="open", nullable=False),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # -- Seed currencies -------------------------------------------------------
    op.execute("""
        INSERT INTO gl_currencies (code, name, symbol, decimal_places, is_base, is_active)
        VALUES
            ('JMD', 'Jamaican Dollar',            '$',  2, TRUE,  TRUE),
            ('USD', 'United States Dollar',        '$',  2, FALSE, TRUE),
            ('TTD', 'Trinidad and Tobago Dollar',  '$',  2, FALSE, TRUE),
            ('BBD', 'Barbados Dollar',             '$',  2, FALSE, TRUE)
        ON CONFLICT (code) DO NOTHING;
    """)

    # -- Seed default Chart of Accounts ----------------------------------------
    # Level 1 categories, Level 2 groups, Level 3 detail accounts
    op.execute("""
        -- Level 1: Asset accounts
        INSERT INTO gl_accounts (account_code, name, account_category, account_type, currency_id, level, is_system_account, status)
        VALUES
            ('1-0000', 'Assets',                     'asset',     'debit', 1, 1, TRUE, 'active'),
            ('2-0000', 'Liabilities',                'liability', 'credit', 1, 1, TRUE, 'active'),
            ('3-0000', 'Equity',                     'equity',    'credit', 1, 1, TRUE, 'active'),
            ('4-0000', 'Revenue',                    'revenue',   'credit', 1, 1, TRUE, 'active'),
            ('5-0000', 'Expenses',                   'expense',   'debit', 1, 1, TRUE, 'active')
        ON CONFLICT (account_code) DO NOTHING;

        -- Level 2: Asset sub-groups
        INSERT INTO gl_accounts (account_code, name, account_category, account_type, currency_id, parent_id, level, is_system_account, is_control_account, status)
        VALUES
            ('1-1000', 'Cash and Bank',              'asset',  'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-0000'), 2, TRUE, FALSE, 'active'),
            ('1-2000', 'Loan Portfolio',             'asset',  'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-0000'), 2, TRUE, TRUE,  'active'),
            ('1-3000', 'Interest Receivable',        'asset',  'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-0000'), 2, TRUE, FALSE, 'active'),
            ('1-4000', 'Fee Receivable',             'asset',  'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-0000'), 2, TRUE, FALSE, 'active'),
            ('1-5000', 'Other Assets',               'asset',  'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-0000'), 2, TRUE, FALSE, 'active'),
            ('1-9000', 'Suspense - Assets',          'asset',  'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-0000'), 2, TRUE, FALSE, 'active')
        ON CONFLICT (account_code) DO NOTHING;

        -- Level 2: Liability sub-groups
        INSERT INTO gl_accounts (account_code, name, account_category, account_type, currency_id, parent_id, level, is_system_account, status)
        VALUES
            ('2-1000', 'Customer Deposits',          'liability', 'credit', 1, (SELECT id FROM gl_accounts WHERE account_code='2-0000'), 2, TRUE, 'active'),
            ('2-2000', 'Allowance for Loan Losses',  'liability', 'credit', 1, (SELECT id FROM gl_accounts WHERE account_code='2-0000'), 2, TRUE, 'active'),
            ('2-3000', 'Other Liabilities',          'liability', 'credit', 1, (SELECT id FROM gl_accounts WHERE account_code='2-0000'), 2, TRUE, 'active'),
            ('2-4000', 'Insurance Payable',          'liability', 'credit', 1, (SELECT id FROM gl_accounts WHERE account_code='2-0000'), 2, TRUE, 'active')
        ON CONFLICT (account_code) DO NOTHING;

        -- Level 2: Equity sub-groups
        INSERT INTO gl_accounts (account_code, name, account_category, account_type, currency_id, parent_id, level, is_system_account, status)
        VALUES
            ('3-1000', 'Share Capital',              'equity', 'credit', 1, (SELECT id FROM gl_accounts WHERE account_code='3-0000'), 2, TRUE, 'active'),
            ('3-2000', 'Retained Earnings',          'equity', 'credit', 1, (SELECT id FROM gl_accounts WHERE account_code='3-0000'), 2, TRUE, 'active')
        ON CONFLICT (account_code) DO NOTHING;

        -- Level 2: Revenue sub-groups
        INSERT INTO gl_accounts (account_code, name, account_category, account_type, currency_id, parent_id, level, is_system_account, status)
        VALUES
            ('4-1000', 'Interest Income',            'revenue', 'credit', 1, (SELECT id FROM gl_accounts WHERE account_code='4-0000'), 2, TRUE, 'active'),
            ('4-2000', 'Fee Income',                 'revenue', 'credit', 1, (SELECT id FROM gl_accounts WHERE account_code='4-0000'), 2, TRUE, 'active'),
            ('4-3000', 'Late Fee Income',            'revenue', 'credit', 1, (SELECT id FROM gl_accounts WHERE account_code='4-0000'), 2, TRUE, 'active'),
            ('4-4000', 'Recovery Income',            'revenue', 'credit', 1, (SELECT id FROM gl_accounts WHERE account_code='4-0000'), 2, TRUE, 'active'),
            ('4-5000', 'Prepayment Penalty Income',  'revenue', 'credit', 1, (SELECT id FROM gl_accounts WHERE account_code='4-0000'), 2, TRUE, 'active')
        ON CONFLICT (account_code) DO NOTHING;

        -- Level 2: Expense sub-groups
        INSERT INTO gl_accounts (account_code, name, account_category, account_type, currency_id, parent_id, level, is_system_account, status)
        VALUES
            ('5-1000', 'Provision Expense',          'expense', 'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='5-0000'), 2, TRUE, 'active'),
            ('5-2000', 'Operating Expenses',         'expense', 'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='5-0000'), 2, TRUE, 'active'),
            ('5-3000', 'Write-Off Expense',          'expense', 'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='5-0000'), 2, TRUE, 'active')
        ON CONFLICT (account_code) DO NOTHING;

        -- Level 3: Detail accounts
        INSERT INTO gl_accounts (account_code, name, account_category, account_type, currency_id, parent_id, level, is_system_account, status)
        VALUES
            ('1-1001', 'Operating Bank Account',     'asset',  'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-1000'), 3, TRUE, 'active'),
            ('1-1002', 'Disbursement Clearing',      'asset',  'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-1000'), 3, TRUE, 'active'),
            ('1-2001', 'Performing Loans',           'asset',  'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-2000'), 3, TRUE, 'active'),
            ('1-2002', 'Non-Performing Loans',       'asset',  'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-2000'), 3, TRUE, 'active'),
            ('1-2003', 'Written-Off Loans',          'asset',  'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-2000'), 3, TRUE, 'active'),
            ('1-3001', 'Interest Receivable - Performing',   'asset', 'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-3000'), 3, TRUE, 'active'),
            ('1-3002', 'Interest Receivable - Non-Performing','asset','debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-3000'), 3, TRUE, 'active'),
            ('1-4001', 'Origination Fee Receivable', 'asset',  'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-4000'), 3, TRUE, 'active'),
            ('1-4002', 'Late Fee Receivable',        'asset',  'debit', 1, (SELECT id FROM gl_accounts WHERE account_code='1-4000'), 3, TRUE, 'active')
        ON CONFLICT (account_code) DO NOTHING;
    """)


def downgrade() -> None:
    tables = [
        "gl_anomalies", "gl_export_log", "gl_export_schedules",
        "gl_filter_presets", "gl_accrual_batches",
        "gl_mapping_template_lines", "gl_mapping_templates",
        "gl_journal_entry_lines", "gl_journal_entries",
        "gl_accounting_periods", "gl_account_audit", "gl_accounts", "gl_currencies",
    ]
    for t in tables:
        op.drop_table(t)

    enums = [
        "anomalystatus", "anomalytype", "mappingamountsource", "mappinglinetype",
        "accrualbatchstatus", "accrualbatchtype", "journalsourcetype",
        "journalentrystatus", "periodstatus", "accountstatus", "accounttype", "accountcategory",
    ]
    for e in enums:
        op.execute(f"DROP TYPE IF EXISTS {e}")
