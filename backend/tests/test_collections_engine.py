"""Tests for the collections engine service layer."""

import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.collections_ext import (
    CollectionCase,
    CaseStatus,
    DelinquencyStage,
    PromiseToPay,
    PTPStatus,
    SettlementOffer,
    SettlementOfferType,
    SettlementOfferStatus,
    ComplianceRule,
    SLAConfig,
    CollectionsDashboardSnapshot,
    dpd_to_stage,
)
from app.services.collections_engine import (
    _compute_priority,
    compute_next_best_action,
    calculate_settlement,
    check_ptp_status,
    PTP_GRACE_DAYS,
)


# ── dpd_to_stage ──────────────────────────────────

class TestDpdToStage:
    def test_early(self):
        assert dpd_to_stage(1) == DelinquencyStage.EARLY_1_30
        assert dpd_to_stage(30) == DelinquencyStage.EARLY_1_30

    def test_mid(self):
        assert dpd_to_stage(31) == DelinquencyStage.MID_31_60
        assert dpd_to_stage(60) == DelinquencyStage.MID_31_60

    def test_late(self):
        assert dpd_to_stage(61) == DelinquencyStage.LATE_61_90
        assert dpd_to_stage(90) == DelinquencyStage.LATE_61_90

    def test_severe(self):
        assert dpd_to_stage(91) == DelinquencyStage.SEVERE_90_PLUS
        assert dpd_to_stage(180) == DelinquencyStage.SEVERE_90_PLUS
        assert dpd_to_stage(365) == DelinquencyStage.SEVERE_90_PLUS

    def test_edge_cases(self):
        assert dpd_to_stage(0) == DelinquencyStage.EARLY_1_30
        assert dpd_to_stage(-1) == DelinquencyStage.EARLY_1_30


# ── _compute_priority ─────────────────────────────

class TestComputePriority:
    def test_low_dpd_low_amount(self):
        result = _compute_priority(5, 500)
        assert 0 <= result <= 1

    def test_high_dpd_high_amount(self):
        result = _compute_priority(90, 10000)
        assert result == pytest.approx(1.0, abs=0.01)

    def test_zero_values(self):
        result = _compute_priority(0, 0)
        assert result == 0.0

    def test_capped_at_boundaries(self):
        # DPD > 90 and amount > 10k should still be capped at 1
        result = _compute_priority(200, 50000)
        assert result == pytest.approx(1.0, abs=0.01)

    def test_mid_range(self):
        result = _compute_priority(45, 5000)
        assert 0.2 < result < 0.8


# ── compute_next_best_action ──────────────────────

class TestNBA:
    """Test the rule-based NBA engine."""

    def _make_case(self, **overrides):
        defaults = dict(
            id=1,
            loan_application_id=1,
            dpd=10,
            do_not_contact=False,
            dispute_active=False,
            vulnerability_flag=False,
            hardship_flag=False,
            first_contact_at=None,
            total_overdue=Decimal("1000"),
        )
        defaults.update(overrides)
        case = MagicMock(spec=CollectionCase)
        for k, v in defaults.items():
            setattr(case, k, v)
        return case

    def _mock_db(self, broken_count=0):
        db = AsyncMock()
        result = MagicMock()
        result.scalar.return_value = broken_count
        db.execute.return_value = result
        return db

    @pytest.mark.asyncio
    async def test_do_not_contact(self):
        case = self._make_case(do_not_contact=True)
        result = await compute_next_best_action(case, self._mock_db())
        assert result["action"] == "hold_do_not_contact"
        assert result["confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_dispute_active(self):
        case = self._make_case(dispute_active=True)
        result = await compute_next_best_action(case, self._mock_db())
        assert result["action"] == "hold_dispute"

    @pytest.mark.asyncio
    async def test_vulnerability_flag(self):
        case = self._make_case(vulnerability_flag=True)
        result = await compute_next_best_action(case, self._mock_db())
        assert result["action"] == "hold_vulnerability_review"

    @pytest.mark.asyncio
    async def test_hardship_flag(self):
        case = self._make_case(hardship_flag=True)
        result = await compute_next_best_action(case, self._mock_db())
        assert result["action"] == "offer_hardship_plan"

    @pytest.mark.asyncio
    async def test_early_dpd_no_contact(self):
        case = self._make_case(dpd=3, first_contact_at=None)
        result = await compute_next_best_action(case, self._mock_db())
        assert result["action"] == "send_whatsapp_reminder"

    @pytest.mark.asyncio
    async def test_early_dpd_with_contact(self):
        case = self._make_case(dpd=3, first_contact_at=datetime.now(timezone.utc))
        result = await compute_next_best_action(case, self._mock_db())
        assert result["action"] == "send_sms_reminder"

    @pytest.mark.asyncio
    async def test_mid_dpd_call(self):
        case = self._make_case(dpd=20, first_contact_at=datetime.now(timezone.utc))
        result = await compute_next_best_action(case, self._mock_db(broken_count=0))
        assert result["action"] == "call_now"

    @pytest.mark.asyncio
    async def test_mid_dpd_broken_promises_escalate(self):
        case = self._make_case(dpd=20, first_contact_at=datetime.now(timezone.utc))
        result = await compute_next_best_action(case, self._mock_db(broken_count=3))
        assert result["action"] == "escalate_supervisor"

    @pytest.mark.asyncio
    async def test_late_dpd_demand_letter(self):
        case = self._make_case(dpd=75, first_contact_at=datetime.now(timezone.utc))
        result = await compute_next_best_action(case, self._mock_db(broken_count=0))
        assert result["action"] == "send_demand_letter"

    @pytest.mark.asyncio
    async def test_severe_dpd_legal(self):
        case = self._make_case(dpd=100, first_contact_at=datetime.now(timezone.utc))
        result = await compute_next_best_action(case, self._mock_db(broken_count=0))
        assert result["action"] == "escalate_legal"

    @pytest.mark.asyncio
    async def test_mid_60_dpd_broken_field(self):
        case = self._make_case(dpd=45, first_contact_at=datetime.now(timezone.utc))
        result = await compute_next_best_action(case, self._mock_db(broken_count=3))
        assert result["action"] == "escalate_field"

    @pytest.mark.asyncio
    async def test_flags_priority_dnc_over_dispute(self):
        """DNC takes highest priority, even over dispute."""
        case = self._make_case(do_not_contact=True, dispute_active=True)
        result = await compute_next_best_action(case, self._mock_db())
        assert result["action"] == "hold_do_not_contact"

    @pytest.mark.asyncio
    async def test_nba_returns_required_keys(self):
        case = self._make_case(dpd=50, first_contact_at=datetime.now(timezone.utc))
        result = await compute_next_best_action(case, self._mock_db())
        assert "action" in result
        assert "confidence" in result
        assert "reasoning" in result
        assert isinstance(result["confidence"], float)
        assert 0 <= result["confidence"] <= 1


# ── calculate_settlement ──────────────────────────

class TestCalculateSettlement:
    def test_zero_overdue(self):
        options = calculate_settlement(Decimal("0"), 30)
        assert options == []

    def test_negative_overdue(self):
        options = calculate_settlement(Decimal("-100"), 30)
        assert options == []

    def test_early_dpd_no_discount(self):
        options = calculate_settlement(Decimal("5000"), 15)
        # Should have: full payment, 3-month plan, 6-month plan
        assert len(options) >= 3
        types = [o["offer_type"] for o in options]
        assert "full_payment" in types
        assert "short_plan" in types
        # No partial settlement (0% discount)
        assert "partial_settlement" not in types

    def test_mid_dpd_5pct_discount(self):
        options = calculate_settlement(Decimal("5000"), 45)
        partial = [o for o in options if o["offer_type"] == "partial_settlement"]
        assert len(partial) == 1
        assert partial[0]["discount_pct"] == 5.0
        assert partial[0]["settlement_amount"] == 4750.0

    def test_late_dpd_10pct_discount(self):
        options = calculate_settlement(Decimal("5000"), 75)
        partial = [o for o in options if o["offer_type"] == "partial_settlement"]
        assert len(partial) == 1
        assert partial[0]["discount_pct"] == 10.0
        assert partial[0]["settlement_amount"] == 4500.0

    def test_severe_dpd_20pct_discount(self):
        options = calculate_settlement(Decimal("5000"), 120)
        partial = [o for o in options if o["offer_type"] == "partial_settlement"]
        assert len(partial) == 1
        assert partial[0]["discount_pct"] == 20.0
        assert partial[0]["settlement_amount"] == 4000.0
        assert partial[0]["approval_required"] is True

    def test_full_payment_always_present(self):
        for dpd in [5, 35, 65, 95]:
            options = calculate_settlement(Decimal("1000"), dpd)
            full = [o for o in options if o["offer_type"] == "full_payment"]
            assert len(full) == 1
            assert full[0]["settlement_amount"] == 1000.0
            assert full[0]["discount_pct"] == 0.0

    def test_short_plans(self):
        options = calculate_settlement(Decimal("6000"), 30)
        short_plans = [o for o in options if o["offer_type"] == "short_plan"]
        assert len(short_plans) == 2  # 3-month and 6-month
        for sp in short_plans:
            assert sp["plan_months"] in [3, 6]
            assert sp["plan_monthly_amount"] > 0

    def test_long_plan_only_for_large_amounts(self):
        options_small = calculate_settlement(Decimal("500"), 30)
        long_small = [o for o in options_small if o["offer_type"] == "long_plan"]
        assert len(long_small) == 0

        options_large = calculate_settlement(Decimal("5000"), 30)
        long_large = [o for o in options_large if o["offer_type"] == "long_plan"]
        assert len(long_large) == 1
        assert long_large[0]["plan_months"] == 12
        assert long_large[0]["approval_required"] is True

    def test_discount_not_applied_to_plans(self):
        """Short/long plans should use full amount, not discounted."""
        options = calculate_settlement(Decimal("5000"), 95)  # 20% discount available
        plans = [o for o in options if o["offer_type"] in ("short_plan", "long_plan")]
        for p in plans:
            assert p["settlement_amount"] == 5000.0
            assert p["discount_pct"] == 0.0


# ── check_compliance (partial — uses check_compliance function indirectly) ──

class TestComplianceRule:
    def test_compliance_rule_model(self):
        rule = ComplianceRule(
            jurisdiction="TT",
            contact_start_hour=8,
            contact_end_hour=20,
            max_contacts_per_day=3,
            max_contacts_per_week=10,
            cooling_off_hours=4,
            is_active=True,
        )
        assert rule.jurisdiction == "TT"
        assert rule.contact_start_hour == 8
        assert rule.contact_end_hour == 20


# ── SLA Config ──

class TestSLAConfig:
    def test_sla_model(self):
        sla = SLAConfig(
            name="First Contact — Early",
            delinquency_stage="early_1_30",
            hours_allowed=24,
            escalation_action="auto_whatsapp_reminder",
            is_active=True,
        )
        assert sla.hours_allowed == 24

    def test_sla_stages(self):
        stages = ["early_1_30", "mid_31_60", "late_61_90", "severe_90_plus"]
        for s in stages:
            sla = SLAConfig(name=f"Test {s}", delinquency_stage=s, hours_allowed=12, escalation_action="test")
            assert sla.delinquency_stage == s


# ── CollectionCase model ──

class TestCollectionCaseModel:
    def test_case_statuses(self):
        for status in CaseStatus:
            assert isinstance(status.value, str)

    def test_delinquency_stages(self):
        assert len(DelinquencyStage) == 6

    def test_case_defaults(self):
        case = CollectionCase(loan_application_id=1)
        assert case.dispute_active is False or case.dispute_active is None
        assert case.dpd == 0 or case.dpd is None


# ── PTP Status ──

class TestPTPModel:
    def test_ptp_statuses(self):
        statuses = [PTPStatus.PENDING, PTPStatus.KEPT, PTPStatus.BROKEN,
                     PTPStatus.PARTIALLY_KEPT, PTPStatus.CANCELLED]
        assert len(statuses) == 5

    def test_grace_period_constant(self):
        assert PTP_GRACE_DAYS == 3


# ── Settlement Offer ──

class TestSettlementOfferModel:
    def test_offer_types(self):
        types = [SettlementOfferType.FULL_PAYMENT, SettlementOfferType.SHORT_PLAN,
                 SettlementOfferType.LONG_PLAN, SettlementOfferType.PARTIAL_SETTLEMENT,
                 SettlementOfferType.COMBINATION]
        assert len(types) == 5

    def test_offer_statuses(self):
        statuses = [SettlementOfferStatus.DRAFT, SettlementOfferStatus.OFFERED,
                     SettlementOfferStatus.ACCEPTED, SettlementOfferStatus.REJECTED,
                     SettlementOfferStatus.EXPIRED, SettlementOfferStatus.APPROVED,
                     SettlementOfferStatus.NEEDS_APPROVAL]
        assert len(statuses) == 7


# ── Dashboard Snapshot ──

class TestDashboardSnapshot:
    def test_snapshot_model(self):
        snap = CollectionsDashboardSnapshot(
            snapshot_date=date.today(),
            total_delinquent_accounts=10,
            total_overdue_amount=Decimal("50000"),
        )
        assert snap.total_delinquent_accounts == 10
        assert snap.total_overdue_amount == Decimal("50000")
