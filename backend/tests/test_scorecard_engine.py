"""Tests for the Scorecard Scoring Engine — score calculation, CSV import,
script generation, champion-challenger, and performance metrics."""

import pytest
from unittest.mock import MagicMock

from app.models.scorecard import (
    Scorecard, ScorecardStatus, ScorecardCharacteristic, ScorecardBin,
    BinType, ScoreResult,
)
from app.services.scorecard_engine import (
    score_application, _match_bin, _determine_decision, _generate_reason_codes,
    generate_scoring_script, parse_scorecard_csv, build_scorecard_from_parsed,
    select_decisioning_model, extract_applicant_data, what_if_analysis,
    batch_score_csv,
)
from app.services.scorecard_performance import (
    calculate_gini, calculate_ks, calculate_psi,
    build_score_distribution_pcts, calculate_iv,
)


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────

def _make_scorecard() -> Scorecard:
    """Build a test scorecard matching Scorecard1.csv structure."""
    sc = Scorecard(
        id=1, name="Test Scorecard", version=1, status=ScorecardStatus.CHAMPION,
        base_score=536, min_score=100, max_score=850,
        auto_approve_threshold=650, manual_review_threshold=480,
        auto_decline_threshold=480, traffic_pct=100, is_decisioning=True,
    )

    # C01: Age (range bins)
    c01 = ScorecardCharacteristic(
        id=1, scorecard_id=1, code="C01", name="Age",
        data_field="age", sort_order=0, is_active=True, weight_multiplier=1.0,
    )
    c01.bins = [
        ScorecardBin(id=1, characteristic_id=1, bin_type=BinType.RANGE,
                     min_value=18, max_value=35, label="18-34 years", points=-16, sort_order=0),
        ScorecardBin(id=2, characteristic_id=1, bin_type=BinType.RANGE,
                     min_value=35, max_value=45, label="35-44 years", points=-8, sort_order=1),
        ScorecardBin(id=3, characteristic_id=1, bin_type=BinType.RANGE,
                     min_value=45, max_value=55, label="45-54 years", points=8, sort_order=2),
        ScorecardBin(id=4, characteristic_id=1, bin_type=BinType.RANGE,
                     min_value=55, max_value=None, label="55+ years", points=24, sort_order=3),
    ]

    # C02: Occupation (category bins)
    c02 = ScorecardCharacteristic(
        id=2, scorecard_id=1, code="C02", name="Occupation",
        data_field="occupation", sort_order=1, is_active=True, weight_multiplier=1.0,
    )
    c02.bins = [
        ScorecardBin(id=10, characteristic_id=2, bin_type=BinType.CATEGORY,
                     category_value="Professional", label="Professional", points=47, sort_order=0),
        ScorecardBin(id=11, characteristic_id=2, bin_type=BinType.CATEGORY,
                     category_value="Managerial", label="Managerial", points=16, sort_order=1),
        ScorecardBin(id=12, characteristic_id=2, bin_type=BinType.CATEGORY,
                     category_value="Clerical", label="Clerical", points=0, sort_order=2),
        ScorecardBin(id=13, characteristic_id=2, bin_type=BinType.CATEGORY,
                     category_value="Manual/Laborer", label="Manual/Laborer", points=-55, sort_order=3),
        ScorecardBin(id=14, characteristic_id=2, bin_type=BinType.DEFAULT,
                     category_value="Other", label="Other", points=-31, sort_order=4),
    ]

    # C03: Payment Channel (category)
    c03 = ScorecardCharacteristic(
        id=3, scorecard_id=1, code="C03", name="Payment Channel",
        data_field="payment_channel", sort_order=2, is_active=True, weight_multiplier=1.0,
    )
    c03.bins = [
        ScorecardBin(id=20, characteristic_id=3, bin_type=BinType.CATEGORY,
                     category_value="Payroll", label="Payroll", points=39, sort_order=0),
        ScorecardBin(id=21, characteristic_id=3, bin_type=BinType.CATEGORY,
                     category_value="Cash", label="Cash", points=16, sort_order=1),
        ScorecardBin(id=22, characteristic_id=3, bin_type=BinType.DEFAULT,
                     label="Other/Missing", points=0, sort_order=2),
    ]

    sc.characteristics = [c01, c02, c03]
    return sc


# ────────────────────────────────────────────────────────────────────
# Score Calculation Tests
# ────────────────────────────────────────────────────────────────────

class TestScoreApplication:
    """Test core score_application function."""

    def test_basic_scoring(self):
        """Test scoring with known values."""
        sc = _make_scorecard()
        data = {"age": 30, "occupation": "Professional", "payment_channel": "Payroll"}
        result = score_application(sc, data)

        # base=536, age 30 in 18-34 -> -16, Professional -> +47, Payroll -> +39
        expected = 536 - 16 + 47 + 39
        assert result["total_score"] == expected  # 606

    def test_score_clamping_max(self):
        """Score above max_score should be clamped."""
        sc = _make_scorecard()
        sc.max_score = 600
        data = {"age": 55, "occupation": "Professional", "payment_channel": "Payroll"}
        result = score_application(sc, data)
        assert result["total_score"] == 600

    def test_score_clamping_min(self):
        """Score below min_score should be clamped."""
        sc = _make_scorecard()
        sc.min_score = 500
        sc.base_score = 200
        data = {"age": 30, "occupation": "Manual/Laborer", "payment_channel": None}
        result = score_application(sc, data)
        assert result["total_score"] == 500

    def test_missing_values_use_default(self):
        """Missing values should fall to default bin."""
        sc = _make_scorecard()
        data = {"age": 30, "occupation": None, "payment_channel": None}
        result = score_application(sc, data)
        # age=30: -16, occupation=None -> Other default -> -31, payment=None -> Other default -> 0
        expected = 536 - 16 - 31 + 0
        assert result["total_score"] == expected  # 489

    def test_characteristic_scores_structure(self):
        """Verify characteristic_scores array structure."""
        sc = _make_scorecard()
        data = {"age": 50, "occupation": "Managerial", "payment_channel": "Cash"}
        result = score_application(sc, data)

        assert len(result["characteristic_scores"]) == 3
        cs = result["characteristic_scores"][0]
        assert cs["code"] == "C01"
        assert cs["name"] == "Age"
        assert cs["value"] == "50"
        assert cs["bin_label"] == "45-54 years"
        assert cs["weighted_points"] == 8

    def test_top_factors(self):
        """Verify top positive and negative factors."""
        sc = _make_scorecard()
        data = {"age": 25, "occupation": "Professional", "payment_channel": "Payroll"}
        result = score_application(sc, data)

        # Positive: Professional (+47), Payroll (+39)
        assert len(result["top_positive_factors"]) >= 2
        assert result["top_positive_factors"][0]["points"] == 47

        # Negative: Age (-16)
        assert len(result["top_negative_factors"]) >= 1
        assert result["top_negative_factors"][0]["points"] == -16

    def test_weight_multiplier(self):
        """Verify weight multiplier affects points."""
        sc = _make_scorecard()
        sc.characteristics[0].weight_multiplier = 2.0  # double Age weight
        data = {"age": 30, "occupation": "Clerical", "payment_channel": None}
        result = score_application(sc, data)

        # base=536, age 30: -16*2=-32, Clerical: 0, default: 0
        expected = 536 - 32 + 0 + 0
        assert result["total_score"] == expected


class TestDecisionThresholds:
    """Test decision threshold logic."""

    def test_auto_approve(self):
        """Score >= auto_approve should be AUTO_APPROVE."""
        sc = _make_scorecard()
        assert _determine_decision(700, sc) == "AUTO_APPROVE"
        assert _determine_decision(650, sc) == "AUTO_APPROVE"

    def test_manual_review(self):
        """Score between review and approve should be MANUAL_REVIEW."""
        sc = _make_scorecard()
        assert _determine_decision(500, sc) == "MANUAL_REVIEW"
        assert _determine_decision(480, sc) == "MANUAL_REVIEW"

    def test_auto_decline(self):
        """Score < auto_decline should be AUTO_DECLINE."""
        sc = _make_scorecard()
        assert _determine_decision(479, sc) == "AUTO_DECLINE"
        assert _determine_decision(300, sc) == "AUTO_DECLINE"

    def test_boundary_values(self):
        """Boundary values at exact thresholds."""
        sc = _make_scorecard()
        assert _determine_decision(650, sc) == "AUTO_APPROVE"  # exact threshold
        assert _determine_decision(649.99, sc) == "MANUAL_REVIEW"


class TestBinMatching:
    """Test bin matching logic."""

    def test_range_bin_matching(self):
        """Test range bin matching with boundaries."""
        sc = _make_scorecard()
        char = sc.characteristics[0]  # Age
        assert _match_bin(char, 18).label == "18-34 years"
        assert _match_bin(char, 34).label == "18-34 years"
        assert _match_bin(char, 35).label == "35-44 years"
        assert _match_bin(char, 55).label == "55+ years"
        assert _match_bin(char, 80).label == "55+ years"

    def test_category_bin_matching(self):
        """Test category bin exact matching."""
        sc = _make_scorecard()
        char = sc.characteristics[1]  # Occupation
        assert _match_bin(char, "Professional").label == "Professional"
        assert _match_bin(char, "professional").label == "Professional"  # case-insensitive

    def test_default_bin_for_unknown(self):
        """Unknown values should match default bin."""
        sc = _make_scorecard()
        char = sc.characteristics[1]  # Occupation
        result = _match_bin(char, "Astronaut")
        assert result is not None
        assert result.label == "Other"

    def test_none_value_uses_default(self):
        """None values should use default bin."""
        sc = _make_scorecard()
        char = sc.characteristics[1]
        result = _match_bin(char, None)
        assert result is not None
        assert result.label == "Other"


# ────────────────────────────────────────────────────────────────────
# CSV Import Tests
# ────────────────────────────────────────────────────────────────────

class TestCSVImport:
    """Test CSV parsing and scorecard building."""

    SAMPLE_CSV = """\
Characteristic,Attribute,Points,Notes
BASE SCORE,Starting Score,536,Base score for all applicants
,,,
C01: Age,18-34 years,-16,Younger applicants
,35-44 years,-8,Mid-age
,45-54 years,8,Average risk
,55+ years,24,Lowest risk
,,,
C02: Occupation,Professional,47,Highest stability
,Clerical,0,Baseline
,Manual/Laborer,-55,Highest risk
,Other,-31,Default
"""

    def test_parse_csv(self):
        """Parse CSV and verify structure."""
        result = parse_scorecard_csv(self.SAMPLE_CSV)
        assert result["base_score"] == 536
        assert len(result["characteristics"]) == 2
        assert result["errors"] == []

    def test_parse_csv_characteristics(self):
        """Verify characteristic details."""
        result = parse_scorecard_csv(self.SAMPLE_CSV)
        c01 = result["characteristics"][0]
        assert c01["code"] == "C01"
        assert c01["name"] == "Age"
        assert len(c01["bins"]) == 4

    def test_parse_csv_bins(self):
        """Verify bin parsing."""
        result = parse_scorecard_csv(self.SAMPLE_CSV)
        c01_bins = result["characteristics"][0]["bins"]
        first_bin = c01_bins[0]
        assert first_bin["label"] == "18-34 years"
        assert first_bin["points"] == -16
        assert first_bin["bin_type"] == "range"
        assert first_bin["min_value"] == 18
        assert first_bin["max_value"] == 35

    def test_parse_csv_category_bins(self):
        """Verify category bin parsing."""
        result = parse_scorecard_csv(self.SAMPLE_CSV)
        c02_bins = result["characteristics"][1]["bins"]
        assert c02_bins[0]["bin_type"] == "category"
        assert c02_bins[0]["category_value"] == "Professional"

    def test_build_scorecard_from_parsed(self):
        """Build scorecard ORM object from parsed data."""
        parsed = parse_scorecard_csv(self.SAMPLE_CSV)
        sc = build_scorecard_from_parsed(
            parsed, name="Test", auto_approve=650, manual_review=480, auto_decline=480,
        )
        assert sc.name == "Test"
        assert sc.base_score == 536
        assert sc.auto_approve_threshold == 650
        assert len(sc.characteristics) == 2

    def test_built_scorecard_scores_correctly(self):
        """Built scorecard should produce correct scores."""
        parsed = parse_scorecard_csv(self.SAMPLE_CSV)
        sc = build_scorecard_from_parsed(
            parsed, name="Test", auto_approve=650, manual_review=480, auto_decline=480,
        )
        data = {"age": 30, "occupation": "Professional"}
        result = score_application(sc, data)
        # base=536, age 30 in 18-34 -> -16, Professional -> +47
        assert result["total_score"] == 536 - 16 + 47  # 567

    def test_parse_invalid_points(self):
        """Invalid points should generate errors."""
        bad_csv = "Characteristic,Attribute,Points,Notes\nC01: Age,18-34 years,abc,bad\n"
        result = parse_scorecard_csv(bad_csv)
        assert len(result["errors"]) > 0


# ────────────────────────────────────────────────────────────────────
# Script Generation Tests
# ────────────────────────────────────────────────────────────────────

class TestScriptGeneration:
    """Test raw scoring script generation."""

    def test_script_contains_base_score(self):
        sc = _make_scorecard()
        script = generate_scoring_script(sc)
        assert "score = 536" in script
        assert "base score" in script.lower()

    def test_script_contains_characteristics(self):
        sc = _make_scorecard()
        script = generate_scoring_script(sc)
        assert "Age" in script
        assert "Occupation" in script
        assert "Payment Channel" in script

    def test_script_contains_cutoffs(self):
        sc = _make_scorecard()
        script = generate_scoring_script(sc)
        assert "650" in script
        assert "AUTO_APPROVE" in script
        assert "AUTO_DECLINE" in script

    def test_script_contains_range_conditions(self):
        sc = _make_scorecard()
        script = generate_scoring_script(sc)
        assert "age >= 18" in script or "age >= 18.0" in script

    def test_script_contains_category_conditions(self):
        sc = _make_scorecard()
        script = generate_scoring_script(sc)
        assert '"Professional"' in script


# ────────────────────────────────────────────────────────────────────
# Champion-Challenger Tests
# ────────────────────────────────────────────────────────────────────

class TestChampionChallenger:
    """Test champion-challenger model selection."""

    def test_champion_only(self):
        """With only a champion, always returns champion."""
        champion = _make_scorecard()
        champion.status = ScorecardStatus.CHAMPION
        champion.traffic_pct = 100

        result = select_decisioning_model([champion])
        assert result.id == champion.id

    def test_champion_with_challenger(self):
        """With challenger, sometimes returns challenger."""
        champion = _make_scorecard()
        champion.id = 1
        champion.status = ScorecardStatus.CHAMPION
        champion.traffic_pct = 80

        challenger = _make_scorecard()
        challenger.id = 2
        challenger.status = ScorecardStatus.CHALLENGER
        challenger.traffic_pct = 20

        selections = {"champion": 0, "challenger": 0}
        for _ in range(1000):
            result = select_decisioning_model([champion, challenger])
            if result.id == champion.id:
                selections["champion"] += 1
            else:
                selections["challenger"] += 1

        # Challenger should get roughly 20% ± 5%
        challenger_pct = selections["challenger"] / 1000 * 100
        assert 10 < challenger_pct < 30, f"Challenger got {challenger_pct}%, expected ~20%"

    def test_shadow_never_decisions(self):
        """Shadow models should never be selected for decisioning."""
        champion = _make_scorecard()
        champion.id = 1
        champion.status = ScorecardStatus.CHAMPION
        champion.traffic_pct = 100

        shadow = _make_scorecard()
        shadow.id = 2
        shadow.status = ScorecardStatus.SHADOW
        shadow.traffic_pct = 0

        for _ in range(100):
            result = select_decisioning_model([champion, shadow])
            assert result.id == champion.id

    def test_no_scorecards_returns_none(self):
        """No scorecards should return None."""
        assert select_decisioning_model([]) is None


# ────────────────────────────────────────────────────────────────────
# What-If Analysis Tests
# ────────────────────────────────────────────────────────────────────

class TestWhatIfAnalysis:
    """Test what-if analysis functionality."""

    def test_what_if_basic(self):
        sc = _make_scorecard()
        base_data = {"age": 25, "occupation": "Clerical", "payment_channel": None}
        modifications = {"age": 50}

        result = what_if_analysis(sc, base_data, modifications)

        # age 25 -> -16, age 50 -> +8, diff = +24
        assert result["score_change"] == 24
        assert len(result["changes"]) >= 1
        age_change = [c for c in result["changes"] if c["code"] == "C01"][0]
        assert age_change["point_change"] == 24

    def test_what_if_decision_change(self):
        """What-if that changes the decision."""
        sc = _make_scorecard()
        # Score near threshold
        base_data = {"age": 30, "occupation": "Professional", "payment_channel": "Payroll"}
        # base=536-16+47+39 = 606 -> MANUAL_REVIEW
        modifications = {"occupation": "Manual/Laborer"}
        # base=536-16-55+39 = 504 -> MANUAL_REVIEW (still)

        result = what_if_analysis(sc, base_data, modifications)
        assert result["base_score"] == 606
        assert result["modified_score"] == 504


# ────────────────────────────────────────────────────────────────────
# Performance Metrics Tests
# ────────────────────────────────────────────────────────────────────

class TestPerformanceMetrics:
    """Test statistical performance metrics."""

    def test_gini_perfect_separation(self):
        """Perfect separation should give Gini close to 1."""
        scores = [100, 200, 300, 400, 500, 600, 700, 800]
        defaults = [True, True, True, True, False, False, False, False]
        gini = calculate_gini(scores, defaults)
        assert gini == 1.0  # perfect separation

    def test_gini_no_discrimination(self):
        """Truly random/mixed scores should give Gini between 0 and 1."""
        # With tied scores, Gini depends on sort-order of ties, so it won't be exactly 0
        scores = [300, 400, 500, 300, 400, 500]
        defaults = [True, False, True, False, True, False]
        gini = calculate_gini(scores, defaults)
        assert 0 <= gini < 0.5  # weak discrimination

    def test_gini_empty(self):
        """Empty lists should return 0."""
        assert calculate_gini([], []) == 0.0

    def test_gini_no_defaults(self):
        """No defaults should return 0."""
        scores = [100, 200, 300]
        defaults = [False, False, False]
        assert calculate_gini(scores, defaults) == 0.0

    def test_ks_perfect_separation(self):
        """Perfect separation should give KS of 1."""
        scores = [100, 200, 300, 400, 500, 600, 700, 800]
        defaults = [True, True, True, True, False, False, False, False]
        ks = calculate_ks(scores, defaults)
        assert ks == 1.0

    def test_ks_no_discrimination(self):
        """KS should be low for weak discrimination."""
        scores = [300, 400, 500, 300, 400, 500]
        defaults = [True, False, True, False, True, False]
        ks = calculate_ks(scores, defaults)
        assert 0 <= ks < 0.5  # weak discrimination

    def test_psi_identical_distributions(self):
        """Identical distributions should give PSI close to 0."""
        pcts = [0.1, 0.2, 0.3, 0.2, 0.1, 0.1]
        psi = calculate_psi(pcts, pcts)
        assert psi < 0.01

    def test_psi_shifted_distribution(self):
        """Shifted distribution should give positive PSI."""
        expected = [0.2, 0.2, 0.2, 0.2, 0.2]
        actual = [0.05, 0.1, 0.2, 0.3, 0.35]
        psi = calculate_psi(expected, actual)
        assert psi > 0

    def test_iv_calculation(self):
        """Test IV calculation."""
        good_pcts = [0.3, 0.3, 0.2, 0.1, 0.1]
        bad_pcts = [0.1, 0.1, 0.2, 0.3, 0.3]
        iv = calculate_iv(good_pcts, bad_pcts)
        assert iv > 0  # Should have predictive power

    def test_score_distribution_pcts(self):
        """Test score distribution percentage calculation."""
        scores = [100, 200, 300, 400, 500]
        pcts = build_score_distribution_pcts(scores, 100, 850, n_bands=10)
        assert len(pcts) == 10
        assert abs(sum(pcts) - 1.0) < 0.01  # Should sum to ~1


# ────────────────────────────────────────────────────────────────────
# Batch Scoring Tests
# ────────────────────────────────────────────────────────────────────

class TestBatchScoring:
    """Test batch scoring from CSV."""

    def test_batch_score_basic(self):
        sc = _make_scorecard()
        csv_content = "age,occupation,payment_channel\n30,Professional,Payroll\n50,Clerical,Cash\n"
        results = batch_score_csv(sc, csv_content)
        assert len(results) == 2
        assert results[0]["total_score"] == 536 - 16 + 47 + 39  # 606
        assert results[1]["total_score"] == 536 + 8 + 0 + 16  # 560


# ────────────────────────────────────────────────────────────────────
# Scorecard1.csv Verification Tests
# ────────────────────────────────────────────────────────────────────

class TestScorecard1CSV:
    """Verify Scorecard1.csv produces correct scores."""

    @pytest.fixture
    def scorecard1(self):
        """Load Scorecard1.csv."""
        import os
        csv_path = os.path.join(
            os.path.dirname(__file__), "..", "docs", "Scorecard1.csv"
        )
        if os.path.exists(csv_path):
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
        else:
            # Use inline CSV from seed
            from app.seed_scorecard import SCORECARD1_CSV
            content = SCORECARD1_CSV

        parsed = parse_scorecard_csv(content)
        return build_scorecard_from_parsed(
            parsed, name="Scorecard1", auto_approve=650, manual_review=480, auto_decline=480,
        )

    def test_base_score(self, scorecard1):
        assert scorecard1.base_score == 536

    def test_characteristic_count(self, scorecard1):
        assert len(scorecard1.characteristics) == 8  # C01-C09 (C08 missing)

    def test_young_professional_payroll(self, scorecard1):
        """Young professional with payroll: should score moderately."""
        data = {
            "age": 28,
            "occupation": "Professional",
            "payment_channel": "Payroll",
            "payment_frequency": "Monthly",
            "residence_tenure": 5,
            "employment_tenure_months": 36,
            "residential_status": "Renting",
            "geographic_location": "Tier 1 (Low Risk)",
        }
        result = score_application(scorecard1, data)
        # 536 + (-16) + 47 + 39 + 8 + 39 + 24 + 4 + 47 = 728
        assert result["total_score"] > 650  # Should auto-approve

    def test_high_risk_profile(self, scorecard1):
        """High risk profile should score low."""
        data = {
            "age": 22,
            "occupation": "Manual/Laborer",
            "payment_channel": "Other/Missing",
            "payment_frequency": "Every Two Weeks",
            "residence_tenure": 1,
            "employment_tenure_months": 6,
            "residential_status": "Other",
            "geographic_location": "Tier 3 (High Risk)",
        }
        result = score_application(scorecard1, data)
        # 536 + (-16) + (-55) + 0 + (-30) + (-8) + (-31) + 0 + (-31) = 365
        assert result["total_score"] < 480  # Should auto-decline

    def test_decision_consistency(self, scorecard1):
        """Same input should always produce same score."""
        data = {"age": 40, "occupation": "Civil Servant", "payment_channel": "Payroll"}
        r1 = score_application(scorecard1, data)
        r2 = score_application(scorecard1, data)
        assert r1["total_score"] == r2["total_score"]
        assert r1["decision"] == r2["decision"]

    def test_script_generation(self, scorecard1):
        """Script should be generated and contain key elements."""
        script = generate_scoring_script(scorecard1)
        assert "536" in script
        assert "Age" in script
        assert "Occupation" in script
        assert "Professional" in script

    def test_reason_codes_for_decline(self, scorecard1):
        """Declined applications should have reason codes."""
        data = {
            "age": 22,
            "occupation": "Manual/Laborer",
            "payment_channel": "Other/Missing",
            "payment_frequency": "Every Two Weeks",
            "residence_tenure": 1,
            "employment_tenure_months": 6,
            "residential_status": "Other",
            "geographic_location": "Tier 3 (High Risk)",
        }
        result = score_application(scorecard1, data)
        assert result["decision"] == "AUTO_DECLINE"
        assert len(result["reason_codes"]) > 0

    def test_all_characteristics_scored(self, scorecard1):
        """All active characteristics should appear in scores."""
        data = {
            "age": 40, "occupation": "Professional", "payment_channel": "Payroll",
            "payment_frequency": "Weekly", "residence_tenure": 5,
            "employment_tenure_months": 36, "residential_status": "Renting",
            "geographic_location": "Tier 1 (Low Risk)",
        }
        result = score_application(scorecard1, data)
        codes = {cs["code"] for cs in result["characteristic_scores"]}
        assert "C01" in codes
        assert "C02" in codes

    def test_monotonicity_age(self, scorecard1):
        """Older applicants should generally score higher (for this scorecard)."""
        data_base = {"occupation": "Clerical", "payment_channel": "Payroll"}
        score_25 = score_application(scorecard1, {**data_base, "age": 25})["total_score"]
        score_50 = score_application(scorecard1, {**data_base, "age": 50})["total_score"]
        score_60 = score_application(scorecard1, {**data_base, "age": 60})["total_score"]
        assert score_50 > score_25  # 45-54 > 18-34
        assert score_60 > score_25  # 55+ > 18-34
