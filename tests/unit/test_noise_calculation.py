"""Comprehensive tests for Phase 2 - Calculation Core."""

import pytest

from src.domain.services.noise_calculation import (
    ExposureOrigin,
    PhaseExposure,
    SensitiveWorkerFactors,
    calculate_k_background,
    calculate_k_impulse,
    calculate_k_tone,
    calculate_lex_8h,
    calculate_lex_weekly,
    calculate_sensitive_adjustment,
    classify_risk_band,
)


class TestNoiseCalculation:
    """Test cases for ISO 9612 noise exposure calculations."""

    def test_lex_8h_metalmeccanico(self):
        """Test caso positivo: metalmeccanico with 3 phases."""
        exposures = [
            PhaseExposure(laeq_db_a=85, duration_hours=4.0, origin=ExposureOrigin.MEASURED),
            PhaseExposure(laeq_db_a=90, duration_hours=2.0, origin=ExposureOrigin.CALCULATED),
            PhaseExposure(laeq_db_a=60, duration_hours=2.0, origin=ExposureOrigin.MEASURED),
        ]
        result = calculate_lex_8h(exposures)

        assert 82.0 <= result.lex_8h <= 88.0
        assert result.risk_band in ["low", "medium"]

    def test_lex_8h_edilizia(self):
        """Test caso positivo: edilizia (high risk scenario)."""
        exposures = [
            PhaseExposure(
                laeq_db_a=105,
                duration_hours=2.0,
                origin=ExposureOrigin.MEASURED,
                lcpeak_db_c=138,
            ),
            PhaseExposure(laeq_db_a=95, duration_hours=3.0, origin=ExposureOrigin.MEASURED),
            PhaseExposure(laeq_db_a=70, duration_hours=3.0, origin=ExposureOrigin.MEASURED),
        ]
        result = calculate_lex_8h(exposures)

        assert 95.0 <= result.lex_8h <= 100.0
        assert result.risk_band == "high"
        assert result.lcpeak_aggregated == 138.0

    def test_lex_8h_single_exposure_8h(self):
        """Test edge case: single 8-hour exposure at 80 dB(A)."""
        exposures = [
            PhaseExposure(laeq_db_a=80, duration_hours=8.0, origin=ExposureOrigin.MEASURED),
        ]
        result = calculate_lex_8h(exposures)

        assert result.lex_8h == 80.0
        assert result.risk_band == "low"

    def test_lex_8h_empty_list_raises(self):
        """Test caso negativo: empty exposure list raises ValueError."""
        with pytest.raises(ValueError, match="Empty"):
            calculate_lex_8h([])

    def test_lex_8h_negative_laeq_raises(self):
        """Test caso negativo: negative LAeq raises ValueError."""
        with pytest.raises(ValueError, match="outside valid range"):
            calculate_lex_8h([PhaseExposure(laeq_db_a=-10, duration_hours=1.0)])

    def test_lex_8h_invalid_duration_raises(self):
        """Test caso negativo: zero duration raises ValueError."""
        with pytest.raises(ValueError, match="Duration.*invalid"):
            calculate_lex_8h([PhaseExposure(laeq_db_a=80, duration_hours=0)])

    def test_lex_8h_over_24h_raises(self):
        """Test caso negativo: duration > 24h raises ValueError."""
        with pytest.raises(ValueError, match="Duration.*invalid"):
            calculate_lex_8h([PhaseExposure(laeq_db_a=80, duration_hours=25)])


class TestRiskBandClassification:
    """Test risk band thresholds per Art. 188 D.Lgs. 81/2008."""

    def test_negligible_below_80(self):
        """LEX < 80 dB(A) = negligible."""
        assert classify_risk_band(75) == "negligible"
        assert classify_risk_band(79.9) == "negligible"

    def test_low_80_to_85(self):
        """80 <= LEX < 85 dB(A) = low."""
        assert classify_risk_band(80) == "low"
        assert classify_risk_band(82) == "low"
        assert classify_risk_band(84.9) == "low"

    def test_medium_85_to_87(self):
        """85 <= LEX < 87 dB(A) = medium."""
        assert classify_risk_band(85) == "medium"
        assert classify_risk_band(86) == "medium"

    def test_high_above_87(self):
        """LEX >= 87 dB(A) = high."""
        assert classify_risk_band(87) == "high"
        assert classify_risk_band(90) == "high"
        assert classify_risk_band(100) == "high"


class TestLexWeekly:
    """Test cases for weekly exposure calculation."""

    def test_lex_weekly_basic(self):
        """Test weekly LEX calculation."""
        daily_lex = [80, 82, 81, 83, 80]
        result = calculate_lex_weekly(daily_lex)

        assert 81.0 <= result <= 83.0

    def test_lex_weekly_single_day(self):
        """Test weekly with single day."""
        result = calculate_lex_weekly([85])
        assert result == 85.0

    def test_lex_weekly_empty_raises(self):
        """Test empty list raises ValueError."""
        with pytest.raises(ValueError, match="Empty"):
            calculate_lex_weekly([])


class TestKCorrections:
    """Test K corrections per ISO 1999."""

    def test_k_impulse_no_impulse(self):
        """No impulse correction when LAeq - Lpeak < 3 dB."""
        # LAeq=85, Lpeak=88 -> delta=-3 -> K=0
        assert calculate_k_impulse(85, 88) == 0.0

    def test_k_impulse_moderate(self):
        """Moderate impulse correction for 3 <= delta < 10."""
        # LAeq=90, Lpeak=85 -> delta=5 -> K=3
        assert calculate_k_impulse(90, 85) == 3.0

    def test_k_impulse_strong(self):
        """Strong impulse correction for delta >= 10."""
        # LAeq=100, Lpeak=88 -> delta=12 -> K=6
        assert calculate_k_impulse(100, 88) == 6.0

    def test_k_impulse_no_peak(self):
        """No impulse correction when peak is None."""
        assert calculate_k_impulse(90, None) == 0.0

    def test_k_tone_no_tone(self):
        """No tone correction when LAeq - Lbackground >= 10 dB."""
        assert calculate_k_tone(90, 78) == 0.0

    def test_k_tone_moderate(self):
        """Moderate tone correction for 5 <= delta < 10."""
        assert calculate_k_tone(90, 83) == 3.0

    def test_k_tone_strong(self):
        """Strong tone correction for delta < 5."""
        assert calculate_k_tone(90, 87) == 6.0

    def test_k_background_applied(self):
        """Background correction is negative when delta < 10."""
        # LAeq=85, Lbackground=80 -> delta=5 -> K=-5
        assert calculate_k_background(85, 80) == -5.0

    def test_k_background_not_applied(self):
        """No background correction when delta >= 10."""
        assert calculate_k_background(90, 78) == 0.0


class TestSensitiveWorkers:
    """Test sensitive worker adjustments per Allegato VIII."""

    def test_pregnant_worker(self):
        """Pregnant worker gets +3 dB."""
        factors = SensitiveWorkerFactors(is_pregnant=True)
        assert calculate_sensitive_adjustment(factors) == 3.0

    def test_minor_worker(self):
        """Minor worker gets +3 dB."""
        factors = SensitiveWorkerFactors(is_minor=True)
        assert calculate_sensitive_adjustment(factors) == 3.0

    def test_ototoxic_exposed(self):
        """Ototoxic exposed worker gets +3 dB."""
        factors = SensitiveWorkerFactors(is_ototoxic_exposed=True)
        assert calculate_sensitive_adjustment(factors) == 3.0

    def test_vibration_exposed(self):
        """Vibration exposed worker gets +2 dB."""
        factors = SensitiveWorkerFactors(is_vibration_exposed=True)
        assert calculate_sensitive_adjustment(factors) == 2.0

    def test_multiple_factors(self):
        """Multiple factors accumulate."""
        factors = SensitiveWorkerFactors(is_pregnant=True, is_ototoxic_exposed=True, is_vibration_exposed=True)
        # 3 + 3 + 2 = 8
        assert calculate_sensitive_adjustment(factors) == 8.0


class TestUncertainty:
    """Test cases for uncertainty calculation."""

    def test_uncertainty_all_measured(self):
        """Test uncertainty with all measured data."""
        exposures = [
            PhaseExposure(laeq_db_a=85, duration_hours=4.0, origin=ExposureOrigin.MEASURED),
            PhaseExposure(laeq_db_a=90, duration_hours=2.0, origin=ExposureOrigin.MEASURED),
            PhaseExposure(laeq_db_a=60, duration_hours=2.0, origin=ExposureOrigin.MEASURED),
        ]
        result = calculate_lex_8h(exposures)

        assert result.uncertainty_db is not None
        assert result.uncertainty_db > 0

    def test_uncertainty_all_estimated(self):
        """Higher uncertainty with estimated data."""
        exposures = [
            PhaseExposure(laeq_db_a=85, duration_hours=4.0, origin=ExposureOrigin.ESTIMATED),
            PhaseExposure(laeq_db_a=90, duration_hours=2.0, origin=ExposureOrigin.ESTIMATED),
        ]
        result = calculate_lex_8h(exposures)

        assert result.uncertainty_db is not None
        # ESTIMATED has 3.0 dB uncertainty each
        # combined = sqrt(3^2 + 3^2) = 4.24
        # extended (k=2) = 8.48
        assert result.uncertainty_db > 5.0

    def test_confidence_all_measured(self):
        """Test confidence score with all measured data."""
        exposures = [
            PhaseExposure(laeq_db_a=85, duration_hours=4.0, origin=ExposureOrigin.MEASURED),
        ]
        result = calculate_lex_8h(exposures)

        assert result.confidence_score == 1.0

    def test_confidence_mixed(self):
        """Test confidence with mixed origins."""
        exposures = [
            PhaseExposure(laeq_db_a=85, duration_hours=4.0, origin=ExposureOrigin.MEASURED),
            PhaseExposure(laeq_db_a=90, duration_hours=2.0, origin=ExposureOrigin.ESTIMATED),
        ]
        result = calculate_lex_8h(exposures)

        # (1.0 + 0.6) / 2 = 0.8
        assert result.confidence_score == 0.8


class TestLCPeak:
    """Test LCPeak aggregation."""

    def test_lcpeak_max_selected(self):
        """Maximum LCPeak is selected."""
        exposures = [
            PhaseExposure(laeq_db_a=85, duration_hours=4.0, lcpeak_db_c=130),
            PhaseExposure(laeq_db_a=90, duration_hours=2.0, lcpeak_db_c=138),
            PhaseExposure(laeq_db_a=60, duration_hours=2.0, lcpeak_db_c=125),
        ]
        result = calculate_lex_8h(exposures)

        assert result.lcpeak_aggregated == 138.0

    def test_lcpeak_no_peak(self):
        """No peak value returns None."""
        exposures = [
            PhaseExposure(laeq_db_a=85, duration_hours=4.0),
            PhaseExposure(laeq_db_a=90, duration_hours=2.0),
        ]
        result = calculate_lex_8h(exposures)

        assert result.lcpeak_aggregated is None
