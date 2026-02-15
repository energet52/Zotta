"""Comprehensive tests for the Sectorial Analysis module.

Covers:
  - Helper functions (pure, no DB)
  - SECTOR_TAXONOMY completeness
  - Portfolio dashboard (mocked DB)
  - Sector detail with delinquency/DPD bucketing
  - Roll-rate computation
  - Concentration enforcement (allowed / blocked / paused)
  - Alert rule evaluation (fires when threshold breached)
  - Stress-test calculations
  - Snapshot generation
  - Heatmap assembly
"""

import pytest
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.loan import LoanApplication, LoanStatus, ApplicantProfile
from app.models.payment import PaymentSchedule, ScheduleStatus
from app.models.sector_analysis import (
    SectorPolicy,
    SectorPolicyStatus,
    SectorRiskRating,
    SectorAlertRule,
    SectorAlertSeverity,
    SectorAlert,
    SectorAlertStatus,
    SectorSnapshot,
    SectorMacroIndicator,
    SECTOR_TAXONOMY,
)
from app.services.sector_analysis import (
    _pct,
    _safe_div,
    _compute_roll_rates,
    _evaluate_condition,
    _get_metric_value,
    get_portfolio_dashboard,
    get_sector_detail,
    get_sector_heatmap,
    run_stress_test,
    check_sector_origination,
    generate_monthly_snapshot,
    evaluate_alert_rules,
    ACTIVE_STATUSES,
)


# ═══════════════════════════════════════════════════════════════
# 1. Taxonomy validation
# ═══════════════════════════════════════════════════════════════

class TestSectorTaxonomy:
    def test_taxonomy_has_23_sectors(self):
        assert len(SECTOR_TAXONOMY) == 23

    def test_taxonomy_contains_required_sectors(self):
        required = [
            "Banking & Financial Services",
            "Hospitality & Tourism",
            "Agriculture & Agro-processing",
            "Oil, Gas & Energy",
            "Retail & Distribution",
            "Government & Public Sector",
            "Information Technology",
            "Other",
            "Not Applicable",
            "MISSING",
        ]
        for sector in required:
            assert sector in SECTOR_TAXONOMY, f"Missing required sector: {sector}"

    def test_taxonomy_has_no_duplicates(self):
        assert len(SECTOR_TAXONOMY) == len(set(SECTOR_TAXONOMY))

    def test_taxonomy_entries_are_non_empty_strings(self):
        for sector in SECTOR_TAXONOMY:
            assert isinstance(sector, str)
            assert len(sector.strip()) > 0


# ═══════════════════════════════════════════════════════════════
# 2. Pure helper functions
# ═══════════════════════════════════════════════════════════════

class TestHelpers:
    # ── _pct ──────────────────────────────────────────────
    def test_pct_normal(self):
        assert _pct(25, 100) == 25.0

    def test_pct_fraction(self):
        assert _pct(1, 3) == pytest.approx(33.33, rel=1e-2)

    def test_pct_zero_total(self):
        assert _pct(50, 0) == 0.0

    def test_pct_zero_part(self):
        assert _pct(0, 100) == 0.0

    def test_pct_returns_float(self):
        result = _pct(10, 50)
        assert isinstance(result, float)
        assert result == 20.0

    # ── _safe_div ─────────────────────────────────────────
    def test_safe_div_normal(self):
        assert _safe_div(100, 4) == 25.0

    def test_safe_div_zero_denominator(self):
        assert _safe_div(100, 0) == 0.0

    def test_safe_div_zero_numerator(self):
        assert _safe_div(0, 10) == 0.0

    def test_safe_div_returns_float(self):
        result = _safe_div(7, 3)
        assert isinstance(result, float)
        assert result == pytest.approx(2.33, rel=1e-2)

    # ── _evaluate_condition ───────────────────────────────
    def test_evaluate_gt_true(self):
        assert _evaluate_condition(10, ">", 5) is True

    def test_evaluate_gt_false(self):
        assert _evaluate_condition(3, ">", 5) is False

    def test_evaluate_gt_equal(self):
        assert _evaluate_condition(5, ">", 5) is False

    def test_evaluate_gte_true(self):
        assert _evaluate_condition(5, ">=", 5) is True

    def test_evaluate_gte_false(self):
        assert _evaluate_condition(4, ">=", 5) is False

    def test_evaluate_lt_true(self):
        assert _evaluate_condition(3, "<", 5) is True

    def test_evaluate_lt_false(self):
        assert _evaluate_condition(7, "<", 5) is False

    def test_evaluate_lte_true(self):
        assert _evaluate_condition(5, "<=", 5) is True

    def test_evaluate_eq_true(self):
        assert _evaluate_condition(5, "==", 5) is True

    def test_evaluate_eq_close_values(self):
        assert _evaluate_condition(5.0001, "==", 5.0005) is True

    def test_evaluate_eq_far_values(self):
        assert _evaluate_condition(5.0, "==", 6.0) is False

    def test_evaluate_unknown_operator(self):
        assert _evaluate_condition(5, "!=", 3) is False

    # ── _get_metric_value ─────────────────────────────────
    def test_get_metric_exposure_pct(self):
        sector = {"exposure_pct": 12.5, "loan_count": 50, "total_outstanding": 500000}
        detail = {"delinquency_rate": 3.0, "npl_ratio": 1.2, "avg_loan_size": 10000}
        assert _get_metric_value("exposure_pct", sector, detail) == 12.5

    def test_get_metric_delinquency_rate(self):
        sector = {"exposure_pct": 10}
        detail = {"delinquency_rate": 7.5, "npl_ratio": 2.0}
        assert _get_metric_value("delinquency_rate", sector, detail) == 7.5

    def test_get_metric_npl_ratio(self):
        sector = {}
        detail = {"npl_ratio": 4.2, "delinquency_rate": 8.0}
        assert _get_metric_value("npl_ratio", sector, detail) == 4.2

    def test_get_metric_loan_count(self):
        sector = {"loan_count": 120}
        detail = {}
        assert _get_metric_value("loan_count", sector, detail) == 120

    def test_get_metric_roll_rate(self):
        sector = {}
        detail = {"roll_rates": {"dpd30_to_60": 0.15, "dpd60_to_90": 0.08}}
        assert _get_metric_value("roll_rate_30_60", sector, detail) == 0.15
        assert _get_metric_value("roll_rate_60_90", sector, detail) == 0.08

    def test_get_metric_unknown(self):
        assert _get_metric_value("unknown_metric", {}, {}) is None

    # ── _compute_roll_rates ───────────────────────────────
    def test_roll_rates_with_two_snapshots(self):
        snapshots = [
            {"loan_count": 100, "dpd_30_count": 10, "dpd_60_count": 5, "dpd_90_count": 2},
            {"loan_count": 105, "dpd_30_count": 12, "dpd_60_count": 4, "dpd_90_count": 3},
        ]
        result = _compute_roll_rates(snapshots)
        assert "current_to_30" in result
        assert "dpd30_to_60" in result
        assert "dpd60_to_90" in result
        # current_to_30 = curr.dpd_30 / (prev.total - prev.dpd_30 - prev.dpd_60 - prev.dpd_90)
        expected_c30 = _safe_div(12, 100 - 10 - 5 - 2)
        assert result["current_to_30"] == expected_c30
        # dpd30_to_60 = curr.dpd_60 / prev.dpd_30
        expected_3060 = _safe_div(4, 10)
        assert result["dpd30_to_60"] == expected_3060
        # dpd60_to_90 = curr.dpd_90 / prev.dpd_60
        expected_6090 = _safe_div(3, 5)
        assert result["dpd60_to_90"] == expected_6090

    def test_roll_rates_single_snapshot_returns_zeros(self):
        result = _compute_roll_rates([{"loan_count": 50}])
        assert result == {"current_to_30": 0, "dpd30_to_60": 0, "dpd60_to_90": 0}

    def test_roll_rates_empty_returns_zeros(self):
        result = _compute_roll_rates([])
        assert result == {"current_to_30": 0, "dpd30_to_60": 0, "dpd60_to_90": 0}


# ═══════════════════════════════════════════════════════════════
# 3. Mocked-DB service tests
# ═══════════════════════════════════════════════════════════════

def _make_loan(id_: int, applicant_id: int, amount: float, status=LoanStatus.DISBURSED, disbursed_at=None):
    loan = MagicMock(spec=LoanApplication)
    loan.id = id_
    loan.applicant_id = applicant_id
    loan.amount_requested = Decimal(str(amount))
    loan.amount_approved = Decimal(str(amount))
    loan.status = status
    loan.reference_number = f"ZT-{id_:04d}"
    loan.disbursed_at = disbursed_at or datetime(2025, 6, 1, tzinfo=timezone.utc)
    loan.interest_rate = Decimal("12.00")
    loan.term_months = 12
    return loan


def _make_profile(user_id: int, sector: str):
    prof = MagicMock(spec=ApplicantProfile)
    prof.user_id = user_id
    prof.employer_sector = sector
    return prof


def _make_schedule(loan_id: int, due_date: date, amount_due: float, amount_paid: float, status=ScheduleStatus.OVERDUE):
    sched = MagicMock(spec=PaymentSchedule)
    sched.loan_application_id = loan_id
    sched.due_date = due_date
    sched.amount_due = Decimal(str(amount_due))
    sched.amount_paid = Decimal(str(amount_paid))
    sched.status = status
    return sched


def _make_policy(sector: str, **kwargs):
    policy = MagicMock(spec=SectorPolicy)
    policy.id = kwargs.get("id", 1)
    policy.sector = sector
    policy.exposure_cap_pct = kwargs.get("exposure_cap_pct", None)
    policy.exposure_cap_amount = kwargs.get("exposure_cap_amount", None)
    policy.origination_paused = kwargs.get("origination_paused", False)
    policy.pause_effective_date = kwargs.get("pause_effective_date", None)
    policy.pause_expiry_date = kwargs.get("pause_expiry_date", None)
    policy.pause_reason = kwargs.get("pause_reason", None)
    policy.max_loan_amount_override = kwargs.get("max_loan_amount_override", None)
    policy.min_credit_score_override = kwargs.get("min_credit_score_override", None)
    policy.max_term_months_override = kwargs.get("max_term_months_override", None)
    policy.require_collateral = kwargs.get("require_collateral", False)
    policy.require_guarantor = kwargs.get("require_guarantor", False)
    policy.risk_rating = kwargs.get("risk_rating", SectorRiskRating.MEDIUM)
    policy.on_watchlist = kwargs.get("on_watchlist", False)
    policy.watchlist_review_frequency = kwargs.get("watchlist_review_frequency", None)
    policy.status = kwargs.get("status", SectorPolicyStatus.ACTIVE)
    policy.justification = kwargs.get("justification", None)
    policy.created_by = kwargs.get("created_by", 1)
    policy.approved_by = kwargs.get("approved_by", 1)
    return policy


def _make_snapshot(sector: str, snap_date: date, **kwargs):
    snap = MagicMock(spec=SectorSnapshot)
    snap.snapshot_date = snap_date
    snap.sector = sector
    snap.loan_count = kwargs.get("loan_count", 20)
    snap.total_outstanding = Decimal(str(kwargs.get("total_outstanding", 100000)))
    snap.total_disbursed = Decimal(str(kwargs.get("total_disbursed", 110000)))
    snap.avg_loan_size = Decimal(str(kwargs.get("avg_loan_size", 5000)))
    snap.exposure_pct = kwargs.get("exposure_pct", 10.0)
    snap.current_count = kwargs.get("current_count", 15)
    snap.dpd_30_count = kwargs.get("dpd_30_count", 3)
    snap.dpd_60_count = kwargs.get("dpd_60_count", 1)
    snap.dpd_90_count = kwargs.get("dpd_90_count", 1)
    snap.dpd_30_amount = Decimal(str(kwargs.get("dpd_30_amount", 15000)))
    snap.dpd_60_amount = Decimal(str(kwargs.get("dpd_60_amount", 5000)))
    snap.dpd_90_amount = Decimal(str(kwargs.get("dpd_90_amount", 8000)))
    snap.delinquency_rate = kwargs.get("delinquency_rate", 5.0)
    snap.npl_ratio = kwargs.get("npl_ratio", 2.0)
    snap.default_rate = kwargs.get("default_rate", 1.0)
    snap.write_off_amount = Decimal(str(kwargs.get("write_off_amount", 0)))
    snap.risk_rating = kwargs.get("risk_rating", "medium")
    snap.avg_credit_score = kwargs.get("avg_credit_score", 680)
    snap.created_at = datetime.now(timezone.utc)
    return snap


def _make_alert_rule(id_: int, **kwargs):
    rule = MagicMock(spec=SectorAlertRule)
    rule.id = id_
    rule.name = kwargs.get("name", "Test Rule")
    rule.description = kwargs.get("description", None)
    rule.sector = kwargs.get("sector", None)
    rule.metric = kwargs.get("metric", "exposure_pct")
    rule.operator = kwargs.get("operator", ">")
    rule.threshold = kwargs.get("threshold", 20.0)
    rule.consecutive_months = kwargs.get("consecutive_months", 1)
    rule.severity = kwargs.get("severity", SectorAlertSeverity.WARNING)
    rule.recommended_action = kwargs.get("recommended_action", "Review exposure")
    rule.is_active = kwargs.get("is_active", True)
    rule.created_by = 1
    return rule


# ═══════════════════════════════════════════════════════════════
# 4. Concentration enforcement tests
# ═══════════════════════════════════════════════════════════════

class TestConcentrationEnforcement:
    """Test check_sector_origination: the real-time gate at loan approval."""

    @pytest.mark.asyncio
    async def test_no_policy_allows_origination(self):
        """When no policy exists for a sector, origination is always allowed."""
        db = AsyncMock()
        # Policy query returns None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        result = await check_sector_origination(db, "Education", 10000)
        assert result["allowed"] is True
        assert result["reasons"] == []
        assert result["policy"] is None

    @pytest.mark.asyncio
    async def test_paused_sector_blocks_origination(self):
        """A paused sector should block origination with a reason."""
        today = date.today()
        policy = _make_policy(
            "Mining & Extractives",
            origination_paused=True,
            pause_effective_date=today - timedelta(days=7),
            pause_expiry_date=today + timedelta(days=30),
            pause_reason="Commodity crash",
        )

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = policy
        db.execute = AsyncMock(return_value=mock_result)

        result = await check_sector_origination(db, "Mining & Extractives", 5000)
        assert result["allowed"] is False
        assert len(result["reasons"]) > 0
        assert "paused" in result["reasons"][0].lower() or "Paused" in result["reasons"][0]

    @pytest.mark.asyncio
    async def test_paused_expired_allows_origination(self):
        """A paused sector whose pause has expired should allow origination."""
        today = date.today()
        policy = _make_policy(
            "Mining & Extractives",
            origination_paused=True,
            pause_effective_date=today - timedelta(days=60),
            pause_expiry_date=today - timedelta(days=1),  # expired yesterday
            pause_reason="Old pause",
        )

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = policy
        db.execute = AsyncMock(return_value=mock_result)

        result = await check_sector_origination(db, "Mining & Extractives", 5000)
        # Pause has expired so the pause reason should not apply
        pause_reasons = [r for r in result["reasons"] if "paused" in r.lower() or "Paused" in r]
        assert len(pause_reasons) == 0

    @pytest.mark.asyncio
    async def test_exposure_cap_breach_blocks(self):
        """When adding a loan would breach exposure cap, it should be blocked."""
        policy = _make_policy(
            "Retail & Distribution",
            exposure_cap_pct=10.0,
        )

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # Policy lookup
                result.scalar_one_or_none.return_value = policy
            elif call_count == 2:
                # Total portfolio outstanding
                result.scalar.return_value = Decimal("1000000")
            elif call_count == 3:
                # Sector outstanding (already at 9.5% = 95000)
                result.scalar.return_value = Decimal("95000")
            return result

        db = AsyncMock()
        db.execute = mock_execute

        # Adding 20000 would make sector = 115000 / 1020000 = 11.27% > 10%
        result = await check_sector_origination(db, "Retail & Distribution", 20000)
        assert result["allowed"] is False
        assert any("cap" in r.lower() or "breached" in r.lower() for r in result["reasons"])

    @pytest.mark.asyncio
    async def test_within_exposure_cap_allows(self):
        """When loan stays within cap, origination is allowed."""
        policy = _make_policy(
            "Education",
            exposure_cap_pct=30.0,
        )

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = policy
            elif call_count == 2:
                result.scalar.return_value = Decimal("1000000")
            elif call_count == 3:
                result.scalar.return_value = Decimal("100000")  # 10%
            return result

        db = AsyncMock()
        db.execute = mock_execute

        # Adding 5000 would make sector = 105000 / 1005000 = 10.45% < 30%
        result = await check_sector_origination(db, "Education", 5000)
        assert result["allowed"] is True
        assert result["reasons"] == []


# ═══════════════════════════════════════════════════════════════
# 5. Alert rule evaluation tests
# ═══════════════════════════════════════════════════════════════

class TestAlertEvaluation:
    """Test evaluate_alert_rules fires alerts when thresholds are breached."""

    @pytest.mark.asyncio
    async def test_rule_fires_when_threshold_breached(self):
        """A rule with exposure_pct > 15 should fire when sector has 20%."""
        rule = _make_alert_rule(
            1,
            name="High Exposure",
            metric="exposure_pct",
            operator=">",
            threshold=15.0,
            severity=SectorAlertSeverity.WARNING,
        )

        # Mock the full call chain
        with patch("app.services.sector_analysis.get_portfolio_dashboard") as mock_dash, \
             patch("app.services.sector_analysis.get_sector_detail") as mock_detail:

            mock_dash.return_value = {
                "sectors": [
                    {"sector": "Hospitality & Tourism", "exposure_pct": 20.0,
                     "loan_count": 50, "total_outstanding": 200000,
                     "risk_rating": "high", "on_watchlist": True, "origination_paused": False},
                ],
                "total_outstanding": 1000000,
                "total_loan_count": 250,
            }
            mock_detail.return_value = {
                "delinquency_rate": 8.0, "npl_ratio": 3.5, "default_rate": 1.5,
                "avg_loan_size": 4000,
                "roll_rates": {"dpd30_to_60": 0.12, "dpd60_to_90": 0.05},
            }

            db = AsyncMock()
            rules_result = MagicMock()
            rules_result.scalars.return_value.all.return_value = [rule]
            db.execute = AsyncMock(return_value=rules_result)
            db.add = MagicMock()
            db.flush = AsyncMock()

            fired = await evaluate_alert_rules(db)
            assert len(fired) >= 1
            # The alert should be for Hospitality & Tourism
            alert = fired[0]
            assert alert.sector == "Hospitality & Tourism"
            assert alert.metric_value == 20.0
            assert alert.status == SectorAlertStatus.NEW

    @pytest.mark.asyncio
    async def test_rule_does_not_fire_below_threshold(self):
        """A rule should NOT fire when metric is below threshold."""
        rule = _make_alert_rule(
            2,
            name="High NPL",
            metric="npl_ratio",
            operator=">",
            threshold=10.0,
        )

        with patch("app.services.sector_analysis.get_portfolio_dashboard") as mock_dash, \
             patch("app.services.sector_analysis.get_sector_detail") as mock_detail:

            mock_dash.return_value = {
                "sectors": [
                    {"sector": "Education", "exposure_pct": 5.0,
                     "loan_count": 20, "total_outstanding": 50000},
                ],
            }
            mock_detail.return_value = {
                "delinquency_rate": 3.0, "npl_ratio": 2.0, "default_rate": 0.5,
                "avg_loan_size": 2500,
                "roll_rates": {"dpd30_to_60": 0.05, "dpd60_to_90": 0.02},
            }

            db = AsyncMock()
            rules_result = MagicMock()
            rules_result.scalars.return_value.all.return_value = [rule]
            db.execute = AsyncMock(return_value=rules_result)
            db.add = MagicMock()
            db.flush = AsyncMock()

            fired = await evaluate_alert_rules(db)
            assert len(fired) == 0

    @pytest.mark.asyncio
    async def test_sector_specific_rule_only_checks_that_sector(self):
        """A rule targeting a specific sector should not fire for other sectors."""
        rule = _make_alert_rule(
            3,
            name="Tourism Alert",
            sector="Hospitality & Tourism",
            metric="delinquency_rate",
            operator=">",
            threshold=5.0,
        )

        with patch("app.services.sector_analysis.get_portfolio_dashboard") as mock_dash, \
             patch("app.services.sector_analysis.get_sector_detail") as mock_detail:

            mock_dash.return_value = {
                "sectors": [
                    {"sector": "Hospitality & Tourism", "exposure_pct": 10.0,
                     "loan_count": 30, "total_outstanding": 100000},
                    {"sector": "Education", "exposure_pct": 5.0,
                     "loan_count": 20, "total_outstanding": 50000},
                ],
            }

            def detail_for_sector(db, sector_name):
                if sector_name == "Hospitality & Tourism":
                    return {
                        "delinquency_rate": 8.0, "npl_ratio": 3.0, "default_rate": 1.0,
                        "avg_loan_size": 3333,
                        "roll_rates": {"dpd30_to_60": 0.1, "dpd60_to_90": 0.05},
                    }
                return {
                    "delinquency_rate": 15.0, "npl_ratio": 6.0, "default_rate": 3.0,
                    "avg_loan_size": 2500,
                    "roll_rates": {"dpd30_to_60": 0.2, "dpd60_to_90": 0.1},
                }

            mock_detail.side_effect = detail_for_sector

            db = AsyncMock()
            rules_result = MagicMock()
            rules_result.scalars.return_value.all.return_value = [rule]
            db.execute = AsyncMock(return_value=rules_result)
            db.add = MagicMock()
            db.flush = AsyncMock()

            fired = await evaluate_alert_rules(db)
            # Should only fire for Hospitality, not for Education (even though Education is worse)
            assert len(fired) == 1
            assert fired[0].sector == "Hospitality & Tourism"


# ═══════════════════════════════════════════════════════════════
# 6. Stress test calculations
# ═══════════════════════════════════════════════════════════════

class TestStressTest:
    """Test run_stress_test produces correct, non-zero results."""

    @pytest.mark.asyncio
    async def test_stress_test_with_shocks(self):
        with patch("app.services.sector_analysis.get_portfolio_dashboard") as mock_dash, \
             patch("app.services.sector_analysis.get_sector_detail") as mock_detail:

            mock_dash.return_value = {
                "sectors": [
                    {"sector": "Hospitality & Tourism", "total_outstanding": 200000,
                     "exposure_pct": 20.0, "loan_count": 50},
                    {"sector": "Education", "total_outstanding": 100000,
                     "exposure_pct": 10.0, "loan_count": 25},
                ],
                "total_outstanding": 1000000,
            }
            mock_detail.return_value = {
                "default_rate": 3.0,
                "npl_ratio": 2.0,
            }

            db = AsyncMock()
            scenario = {
                "name": "Hurricane Test",
                "shocks": {
                    "Hospitality & Tourism": {
                        "default_rate_multiplier": 3.0,
                        "exposure_change_pct": -20,
                    },
                },
            }

            result = await run_stress_test(db, scenario)
            assert result["scenario_name"] == "Hurricane Test"
            assert result["total_portfolio"] == 1000000
            assert result["total_expected_loss"] >= 0
            assert result["impact_pct_of_portfolio"] >= 0

            # Find the hospitality sector result
            hosp = next(r for r in result["sector_results"] if r["sector"] == "Hospitality & Tourism")
            assert hosp["base_outstanding"] == 200000
            # Stressed outstanding = 200000 * (1 + (-20/100)) = 160000
            assert hosp["stressed_outstanding"] == 160000.0
            # Stressed default rate = 3.0 * 3.0 = 9.0
            assert hosp["stressed_default_rate"] == 9.0
            # Expected loss = 160000 * (9.0/100) * 0.4 (default LGD) = 5760
            assert hosp["expected_loss"] == 5760.0
            assert hosp["applied_shock"] is not None

    @pytest.mark.asyncio
    async def test_stress_test_no_shocks_returns_zero_impact(self):
        """Sectors without shocks should have multiplier=1 → no extra loss."""
        with patch("app.services.sector_analysis.get_portfolio_dashboard") as mock_dash, \
             patch("app.services.sector_analysis.get_sector_detail") as mock_detail:

            mock_dash.return_value = {
                "sectors": [
                    {"sector": "Education", "total_outstanding": 50000,
                     "exposure_pct": 5.0, "loan_count": 10},
                ],
                "total_outstanding": 1000000,
            }
            mock_detail.return_value = {
                "default_rate": 2.0,
                "npl_ratio": 1.0,
            }

            db = AsyncMock()
            scenario = {
                "name": "No-shock test",
                "shocks": {},  # no shocks applied
            }

            result = await run_stress_test(db, scenario)
            # With default multiplier=1.0 and no exposure change, EL = outstanding * (default/100) * 0.4
            edu = next(r for r in result["sector_results"] if r["sector"] == "Education")
            assert edu["stressed_default_rate"] == 2.0  # unchanged
            assert edu["stressed_outstanding"] == 50000.0  # unchanged
            expected_el = 50000 * (2.0 / 100) * 0.4
            assert edu["expected_loss"] == expected_el

    @pytest.mark.asyncio
    async def test_stress_test_custom_lgd(self):
        """Custom LGD in shock should override the default 40%."""
        with patch("app.services.sector_analysis.get_portfolio_dashboard") as mock_dash, \
             patch("app.services.sector_analysis.get_sector_detail") as mock_detail:

            mock_dash.return_value = {
                "sectors": [
                    {"sector": "Oil, Gas & Energy", "total_outstanding": 300000,
                     "exposure_pct": 30.0, "loan_count": 40},
                ],
                "total_outstanding": 1000000,
            }
            mock_detail.return_value = {
                "default_rate": 5.0,
                "npl_ratio": 3.0,
            }

            db = AsyncMock()
            scenario = {
                "name": "High LGD",
                "shocks": {
                    "Oil, Gas & Energy": {
                        "default_rate_multiplier": 2.0,
                        "exposure_change_pct": 0,
                        "lgd": 0.6,
                    },
                },
            }

            result = await run_stress_test(db, scenario)
            oil = next(r for r in result["sector_results"] if r["sector"] == "Oil, Gas & Energy")
            # EL = 300000 * (10.0/100) * 0.6 = 18000
            assert oil["expected_loss"] == 18000.0


# ═══════════════════════════════════════════════════════════════
# 7. Portfolio dashboard tests
# ═══════════════════════════════════════════════════════════════

class TestPortfolioDashboard:
    """Test that the dashboard returns non-zero, well-structured data."""

    @pytest.mark.asyncio
    async def test_dashboard_returns_all_required_keys(self):
        # Build a DB mock that returns realistic-looking data
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()

            if call_count == 1:
                # Sector distribution query (grouped rows)
                row1 = MagicMock()
                row1.sector = "Banking & Financial Services"
                row1.loan_count = 30
                row1.total_outstanding = Decimal("450000")
                row1.avg_loan_size = Decimal("15000")

                row2 = MagicMock()
                row2.sector = "Hospitality & Tourism"
                row2.loan_count = 25
                row2.total_outstanding = Decimal("350000")
                row2.avg_loan_size = Decimal("14000")

                row3 = MagicMock()
                row3.sector = "Education"
                row3.loan_count = 15
                row3.total_outstanding = Decimal("200000")
                row3.avg_loan_size = Decimal("13333")

                result.all.return_value = [row1, row2, row3]
            elif call_count == 2:
                # Policies query
                result.scalars.return_value.all.return_value = []
            elif call_count == 3:
                # Recent alerts query
                result.scalars.return_value.all.return_value = []

            return result

        db = AsyncMock()
        db.execute = mock_execute

        data = await get_portfolio_dashboard(db)

        assert data["total_outstanding"] > 0, "total_outstanding must be non-zero"
        assert data["total_outstanding"] == 1000000  # 450k + 350k + 200k
        assert data["total_loan_count"] == 70  # 30 + 25 + 15
        assert data["sector_count"] == 3

        # Sectors should be sorted by exposure descending
        assert data["sectors"][0]["sector"] == "Banking & Financial Services"
        assert data["sectors"][0]["total_outstanding"] == 450000

        # Exposure percentages should sum to 100
        total_pct = sum(s["exposure_pct"] for s in data["sectors"])
        assert 99.9 < total_pct < 100.1, f"Exposure % should sum to ~100, got {total_pct}"

        # Each sector must have all required fields
        for s in data["sectors"]:
            assert s["sector"] != "", "sector name must not be empty"
            assert s["loan_count"] > 0, f"loan_count must be > 0 for {s['sector']}"
            assert s["total_outstanding"] > 0, f"total_outstanding must be > 0 for {s['sector']}"
            assert s["avg_loan_size"] > 0, f"avg_loan_size must be > 0 for {s['sector']}"
            assert s["exposure_pct"] > 0, f"exposure_pct must be > 0 for {s['sector']}"
            assert s["concentration_status"] in ("green", "amber", "red")

        # Top 5 / bottom 5
        assert len(data["top_5"]) > 0
        assert len(data["bottom_5"]) > 0

    @pytest.mark.asyncio
    async def test_dashboard_with_policies_shows_concentration_status(self):
        """When a policy exists with a cap, concentration_status should reflect it."""
        policy = _make_policy(
            "Banking & Financial Services",
            exposure_cap_pct=40.0,  # cap at 40%, actual will be 45%
        )

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()

            if call_count == 1:
                row = MagicMock()
                row.sector = "Banking & Financial Services"
                row.loan_count = 50
                row.total_outstanding = Decimal("450000")
                row.avg_loan_size = Decimal("9000")
                result.all.return_value = [row]
            elif call_count == 2:
                result.scalars.return_value.all.return_value = [policy]
            elif call_count == 3:
                result.scalars.return_value.all.return_value = []
            return result

        db = AsyncMock()
        db.execute = mock_execute

        data = await get_portfolio_dashboard(db)

        banking = data["sectors"][0]
        assert banking["exposure_pct"] == 100.0  # Only one sector → 100%
        assert banking["concentration_status"] == "red"  # 100% > 40%


# ═══════════════════════════════════════════════════════════════
# 8. Sector detail tests
# ═══════════════════════════════════════════════════════════════

class TestSectorDetail:
    """Test sector detail returns proper delinquency and DPD data."""

    @pytest.mark.asyncio
    async def test_detail_computes_dpd_buckets(self):
        """Overdue schedules should be correctly bucketed into 30/60/90 DPD."""
        today = date.today()

        loans = [
            _make_loan(1, 101, 10000),
            _make_loan(2, 102, 15000),
            _make_loan(3, 103, 20000),
        ]

        schedules = [
            _make_schedule(1, today - timedelta(days=35), 1000, 0),  # 35 DPD → 30 bucket
            _make_schedule(2, today - timedelta(days=65), 1500, 0),  # 65 DPD → 60 bucket
            _make_schedule(3, today - timedelta(days=95), 2000, 500),  # 95 DPD → 90 bucket (remaining: 1500)
        ]

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()

            if call_count == 1:
                # Loans in sector
                result.scalars.return_value.all.return_value = loans
            elif call_count == 2:
                # Overdue schedules
                result.scalars.return_value.all.return_value = schedules
            elif call_count == 3:
                # Portfolio totals
                result.one.return_value = (Decimal("100000"), 10)
            elif call_count == 4:
                # Snapshots
                result.scalars.return_value.all.return_value = []
            elif call_count == 5:
                # Policy
                result.scalar_one_or_none.return_value = None
            return result

        db = AsyncMock()
        db.execute = mock_execute

        detail = await get_sector_detail(db, "Banking & Financial Services")

        assert detail["sector"] == "Banking & Financial Services"
        assert detail["loan_count"] == 3
        assert detail["total_outstanding"] == 45000  # 10k + 15k + 20k

        # DPD buckets
        assert detail["dpd_30"]["count"] == 1
        assert detail["dpd_30"]["amount"] == 1000.0  # remaining = 1000 - 0

        assert detail["dpd_60"]["count"] == 1
        assert detail["dpd_60"]["amount"] == 1500.0

        assert detail["dpd_90"]["count"] == 1
        assert detail["dpd_90"]["amount"] == 1500.0  # remaining = 2000 - 500

        # Delinquent count = unique loans with overdue schedules
        assert detail["delinquent_count"] == 3
        assert detail["delinquency_rate"] == 100.0  # 3/3 * 100

        # NPL ratio = dpd_90 amount / total outstanding
        expected_npl = _pct(1500.0, 45000)
        assert detail["npl_ratio"] == expected_npl

    @pytest.mark.asyncio
    async def test_detail_with_no_overdue_returns_zero_delinquency(self):
        """When no schedules are overdue, all DPD counts and rates should be zero."""
        loans = [_make_loan(1, 101, 10000)]

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()

            if call_count == 1:
                result.scalars.return_value.all.return_value = loans
            elif call_count == 2:
                result.scalars.return_value.all.return_value = []  # no overdue
            elif call_count == 3:
                result.one.return_value = (Decimal("50000"), 5)
            elif call_count == 4:
                result.scalars.return_value.all.return_value = []
            elif call_count == 5:
                result.scalar_one_or_none.return_value = None
            return result

        db = AsyncMock()
        db.execute = mock_execute

        detail = await get_sector_detail(db, "Education")

        assert detail["delinquent_count"] == 0
        assert detail["delinquency_rate"] == 0.0
        assert detail["npl_ratio"] == 0.0
        assert detail["dpd_30"]["count"] == 0
        assert detail["dpd_30"]["amount"] == 0.0
        assert detail["dpd_60"]["count"] == 0
        assert detail["dpd_60"]["amount"] == 0.0
        assert detail["dpd_90"]["count"] == 0
        assert detail["dpd_90"]["amount"] == 0.0

    @pytest.mark.asyncio
    async def test_detail_returns_loan_listings(self):
        """The drill-down loan list should include all loan fields."""
        loans = [
            _make_loan(1, 101, 10000),
            _make_loan(2, 102, 20000),
        ]

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()

            if call_count == 1:
                result.scalars.return_value.all.return_value = loans
            elif call_count == 2:
                result.scalars.return_value.all.return_value = []
            elif call_count == 3:
                result.one.return_value = (Decimal("100000"), 10)
            elif call_count == 4:
                result.scalars.return_value.all.return_value = []
            elif call_count == 5:
                result.scalar_one_or_none.return_value = None
            return result

        db = AsyncMock()
        db.execute = mock_execute

        detail = await get_sector_detail(db, "IT")

        assert len(detail["loans"]) == 2
        loan = detail["loans"][0]
        assert "id" in loan
        assert "reference_number" in loan
        assert "amount_approved" in loan
        assert "status" in loan
        assert loan["amount_approved"] > 0


# ═══════════════════════════════════════════════════════════════
# 9. Snapshot generation tests
# ═══════════════════════════════════════════════════════════════

class TestSnapshotGeneration:
    @pytest.mark.asyncio
    async def test_generates_one_snapshot_per_sector(self):
        """generate_monthly_snapshot should create one row per active sector."""
        with patch("app.services.sector_analysis.get_portfolio_dashboard") as mock_dash, \
             patch("app.services.sector_analysis.get_sector_detail") as mock_detail:

            mock_dash.return_value = {
                "sectors": [
                    {"sector": "Banking & Financial Services", "loan_count": 30,
                     "total_outstanding": 300000, "avg_loan_size": 10000, "exposure_pct": 60.0,
                     "risk_rating": "medium"},
                    {"sector": "Education", "loan_count": 20,
                     "total_outstanding": 200000, "avg_loan_size": 10000, "exposure_pct": 40.0,
                     "risk_rating": "low"},
                ],
            }
            mock_detail.return_value = {
                "current_count": 18,
                "dpd_30": {"count": 2, "amount": 5000},
                "dpd_60": {"count": 1, "amount": 3000},
                "dpd_90": {"count": 1, "amount": 4000},
                "delinquency_rate": 5.0,
                "npl_ratio": 2.0,
            }

            db = AsyncMock()
            db.add = MagicMock()
            db.flush = AsyncMock()

            count = await generate_monthly_snapshot(db)
            assert count == 2  # Two sectors
            assert db.add.call_count == 2
            assert db.flush.called


# ═══════════════════════════════════════════════════════════════
# 10. Edge cases and robustness
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_pct_with_very_large_numbers(self):
        assert _pct(999999999, 1000000000) == pytest.approx(100.0, rel=1e-2)

    def test_pct_with_very_small_numbers(self):
        assert _pct(0.001, 1000000) == pytest.approx(0.0, abs=0.01)

    def test_safe_div_both_zero(self):
        assert _safe_div(0, 0) == 0.0

    def test_evaluate_all_operators(self):
        """Verify every operator works correctly."""
        assert _evaluate_condition(10, ">", 5) is True
        assert _evaluate_condition(5, ">", 10) is False
        assert _evaluate_condition(10, ">=", 10) is True
        assert _evaluate_condition(9, ">=", 10) is False
        assert _evaluate_condition(5, "<", 10) is True
        assert _evaluate_condition(10, "<", 5) is False
        assert _evaluate_condition(10, "<=", 10) is True
        assert _evaluate_condition(11, "<=", 10) is False
        assert _evaluate_condition(10, "==", 10) is True
        assert _evaluate_condition(10, "==", 11) is False

    def test_roll_rates_handles_zero_prev_counts(self):
        """Roll rates should not crash when previous snapshot has zero counts."""
        snapshots = [
            {"loan_count": 0, "dpd_30_count": 0, "dpd_60_count": 0, "dpd_90_count": 0},
            {"loan_count": 10, "dpd_30_count": 2, "dpd_60_count": 1, "dpd_90_count": 0},
        ]
        result = _compute_roll_rates(snapshots)
        # Should not raise, should return finite values
        assert isinstance(result["current_to_30"], float)
        assert isinstance(result["dpd30_to_60"], float)
        assert isinstance(result["dpd60_to_90"], float)

    def test_get_metric_with_missing_roll_rates(self):
        """Missing roll_rates keys in detail should return the default 0."""
        sector = {}
        detail = {"roll_rates": {}}
        # .get("dpd30_to_60", 0) returns 0 when key missing
        assert _get_metric_value("roll_rate_30_60", sector, detail) == 0

    def test_taxonomy_missing_sector_exists(self):
        """MISSING must be in taxonomy for legacy data handling."""
        assert "MISSING" in SECTOR_TAXONOMY

    def test_taxonomy_not_applicable_exists(self):
        assert "Not Applicable" in SECTOR_TAXONOMY

    @pytest.mark.asyncio
    async def test_concentration_check_with_missing_sector(self):
        """MISSING sector should work with concentration checks."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        result = await check_sector_origination(db, "MISSING", 5000)
        assert result["allowed"] is True  # No policy = allowed
