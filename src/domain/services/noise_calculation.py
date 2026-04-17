"""Noise exposure calculation service - ISO 9612 implementation."""

from dataclasses import dataclass
from enum import Enum

import numpy as np


class ExposureOrigin(Enum):
    """Origin of exposure data."""

    MEASURED = "measured"
    CALCULATED = "calculated"
    ESTIMATED = "estimated"
    IMPORTED = "imported"
    AI_SUGGESTED = "ai_suggested"
    VALIDATED = "validated"
    DEFAULT_VALUE = "default_value"


@dataclass
class PhaseExposure:
    """Single phase exposure data."""

    laeq_db_a: float
    duration_hours: float
    origin: ExposureOrigin = ExposureOrigin.ESTIMATED
    lcpeak_db_c: float | None = None
    background_noise_db_a: float | None = None


@dataclass
class NoiseExposureResult:
    """Result of noise exposure calculation."""

    lex_8h: float
    lex_weekly: float | None = None
    lcpeak_aggregated: float | None = None
    uncertainty_db: float | None = None
    confidence_score: float = 0.0
    risk_band: str = "negligible"
    k_impulse: float = 0.0
    k_tone: float = 0.0
    k_background: float = 0.0


RISK_BANDS = {
    (0, 80): "negligible",
    (80, 85): "low",
    (85, 87): "medium",
    (87, float("inf")): "high",
}

EXPOSURE_UNCERTAINTY = {
    ExposureOrigin.MEASURED: 1.5,
    ExposureOrigin.CALCULATED: 2.0,
    ExposureOrigin.ESTIMATED: 3.0,
    ExposureOrigin.IMPORTED: 2.5,
    ExposureOrigin.AI_SUGGESTED: 4.0,
    ExposureOrigin.VALIDATED: 1.0,
    ExposureOrigin.DEFAULT_VALUE: 5.0,
}


def classify_risk_band(lex_8h: float) -> str:
    """Classify risk band based on LEX,8h value (Art. 188 D.Lgs. 81/2008)."""
    for (low, high), band in RISK_BANDS.items():
        if low <= lex_8h < high:
            return band
    return "critical"


def calculate_lex_8h(exposures: list[PhaseExposure]) -> NoiseExposureResult:
    """
    Calculate LEX,8h according to ISO 9612.

    Formula: LEX,A,8h = 10 × log10( Σi ( 10^(LAeq,i/10) × Ti / T0 ) )

    Args:
        exposures: List of phase exposures

    Returns:
        NoiseExposureResult with calculated values

    Raises:
        ValueError: If input is invalid
    """
    if not exposures:
        raise ValueError("Empty exposure list")

    for exp in exposures:
        if exp.laeq_db_a < 0 or exp.laeq_db_a > 140:
            raise ValueError(f"LAeq {exp.laeq_db_a} outside valid range [0, 140]")
        if exp.duration_hours <= 0 or exp.duration_hours > 24:
            raise ValueError(f"Duration {exp.duration_hours} invalid (must be 0 < T <= 24)")

    reference_time = 8.0
    total_dose = 0.0
    max_lcpeak = 0.0

    for exp in exposures:
        linear_laeq = 10 ** (exp.laeq_db_a / 10)
        total_dose += linear_laeq * exp.duration_hours

        if exp.lcpeak_db_c is not None:
            max_lcpeak = max(max_lcpeak, exp.lcpeak_db_c)

    if total_dose <= 0:
        raise ValueError("Total dose is zero or negative")

    lex_8h = 10 * np.log10(total_dose / reference_time)

    uncertainty_db = calculate_combined_uncertainty(exposures)
    confidence_score = calculate_confidence(exposures)

    return NoiseExposureResult(
        lex_8h=round(lex_8h, 1),
        lcpeak_aggregated=round(max_lcpeak, 1) if max_lcpeak > 0 else None,
        uncertainty_db=uncertainty_db,
        confidence_score=confidence_score,
        risk_band=classify_risk_band(lex_8h),
    )


def calculate_combined_uncertainty(exposures: list[PhaseExposure]) -> float | None:
    """Calculate combined extended uncertainty (ISO/IEC Guide 98-3)."""
    if not exposures:
        return None

    sum_squared = sum(EXPOSURE_UNCERTAINTY.get(exp.origin, 3.0) ** 2 for exp in exposures)
    combined = np.sqrt(sum_squared)
    extended = 2 * combined  # k=2 for 95% confidence
    return round(extended, 2)


def calculate_lex_weekly(daily_lex: list[float]) -> float:
    """
    Calculate LEX,weekly from daily LEX values.

    Formula: LEX,weekly = 10 × log10( Σ_daily 10^(LEX,d/10) / N_days )
    """
    if not daily_lex:
        raise ValueError("Empty daily lex list")

    n_days = len(daily_lex)
    total_weekly_dose = sum(10 ** (lex / 10) for lex in daily_lex)

    lex_weekly = 10 * np.log10(total_weekly_dose / n_days)
    return round(lex_weekly, 1)


def calculate_confidence(exposures: list[PhaseExposure]) -> float:
    """
    Calculate confidence score based on data quality.

    Returns:
        float between 0 and 1
    """
    if not exposures:
        return 0.0

    quality_scores = []
    for exp in exposures:
        if exp.origin == ExposureOrigin.MEASURED:
            quality_scores.append(1.0)
        elif exp.origin == ExposureOrigin.CALCULATED:
            quality_scores.append(0.85)
        elif exp.origin == ExposureOrigin.VALIDATED:
            quality_scores.append(0.9)
        elif exp.origin == ExposureOrigin.ESTIMATED:
            quality_scores.append(0.6)
        else:
            quality_scores.append(0.4)

    return round(np.mean(quality_scores), 2)


def calculate_k_impulse(laeq: float, lcpeak: float) -> float:
    """
    Calculate K_impulse correction per ISO 1999.

    K_impulse = 0 dB if LAeq - Lpeak < 3 dB
    K_impulse = 3 dB if 3 <= LAeq - Lpeak < 10 dB
    K_impulse = 6 dB if LAeq - Lpeak >= 10 dB
    """
    if lcpeak is None or lcpeak <= 0:
        return 0.0
    delta = laeq - lcpeak
    if delta < 3:
        return 0.0
    elif delta < 10:
        return 3.0
    else:
        return 6.0


def calculate_k_tone(laeq: float, background: float | None) -> float:
    """
    Calculate K_tone correction per ISO 1999.

    K_tone = 0 dB if LAeq - Lbackground >= 10 dB (no tonal component)
    K_tone = 3 dB if 5 <= LAeq - Lbackground < 10 dB (moderate)
    K_tone = 6 dB if LAeq - Lbackground < 5 dB (strong tonal)
    """
    if background is None:
        return 0.0
    delta = laeq - background
    if delta >= 10:
        return 0.0
    elif delta >= 5:
        return 3.0
    else:
        return 6.0


def calculate_k_background(laeq: float, background: float | None) -> float:
    """
    Calculate K_background correction.

    K_background = -(LAeq - Lbackground) dB if LAeq - Lbackground < 10 dB
    K_background = 0 dB otherwise
    """
    if background is None:
        return 0.0
    delta = laeq - background
    if delta < 10:
        return delta - 10  # Negative correction
    return 0.0


def calculate_k_corrections(
    exposures: list[PhaseExposure],
) -> tuple[float, float, float]:
    """
    Calculate all K corrections (ISO 1999).

    Returns:
        tuple of (k_impulse, k_tone, k_background)
    """
    k_impulse = 0.0
    k_tone = 0.0
    k_background = 0.0

    for exp in exposures:
        # K_impulse: based on peak measurement
        if exp.lcpeak_db_c is not None:
            ki = calculate_k_impulse(exp.laeq_db_a, exp.lcpeak_db_c)
            k_impulse = max(k_impulse, ki)

        # K_background: presence of background noise
        if exp.background_noise_db_a is not None:
            kb = calculate_k_background(exp.laeq_db_a, exp.background_noise_db_a)
            k_background += kb

    return (k_impulse, k_tone, k_background)


@dataclass
class SensitiveWorkerFactors:
    """Factors for sensitive worker adjustment (Allegato VIII D.Lgs. 81/2008)."""

    is_pregnant: bool = False
    is_minor: bool = False
    is_ototoxic_exposed: bool = False
    is_vibration_exposed: bool = False


def calculate_sensitive_adjustment(factors: SensitiveWorkerFactors) -> float:
    """
    Calculate additional dB adjustment for sensitive workers.

    Per Allegato VIII D.Lgs. 81/2008, certain factors require extra protection.
    """
    adjustment = 0.0
    if factors.is_pregnant:
        adjustment += 3.0
    if factors.is_minor:
        adjustment += 3.0
    if factors.is_ototoxic_exposed:
        adjustment += 3.0
    if factors.is_vibration_exposed:
        adjustment += 2.0
    return adjustment
