"""ISO 9612 LEX,8h calculation + D.Lgs. 81/2008 Art. 188 risk banding.

Given a list of (LAeq, duration_hours) for each phase, compute the
daily 8-hour weighted noise exposure:

    LEX,8h = 10 * log10( (1/T_ref) * Σ T_i * 10^(L_Aeq,Ti / 10) )

where T_ref = 8 h.

Risk bands per Art. 188:
    < 80 dB         → green   (below lower action value)
    80 <= x < 85    → yellow  (lower action value)
    85 <= x < 87    → orange  (upper action value)
    >= 87           → red     (exposure limit)
"""
from __future__ import annotations

import math
from typing import Iterable, Literal


RiskBand = Literal["green", "yellow", "orange", "red"]
T_REF_HOURS = 8.0


def compute_lex_8h(
    exposures: Iterable[tuple[float, float]],
    *,
    k_corrections_db: float = 0.0,
) -> float:
    """Compute LEX,8h from a sequence of (laeq_db, duration_hours) pairs.

    `k_corrections_db` is added to the final value (typically 0 unless the
    caller wants to apply a flat K correction to the aggregated result).
    Per-phase K corrections should be applied to each LAeq before passing
    in (that's what `compute_lex_8h_from_estimates` does).
    """
    accumulator = 0.0
    for laeq, hours in exposures:
        if hours <= 0 or laeq <= 0:
            continue
        accumulator += hours * (10 ** (laeq / 10))

    if accumulator <= 0:
        return 0.0

    lex = 10 * math.log10(accumulator / T_REF_HOURS)
    return lex + k_corrections_db


def compute_lex_8h_from_estimates(estimates) -> float:
    """Convenience: accepts PhaseExposureEstimate list (with K corrections)."""
    pairs: list[tuple[float, float]] = []
    for e in estimates:
        k = (e.k_tone_db or 0) + (e.k_imp_db or 0)
        laeq_corrected = e.laeq_db + k
        pairs.append((laeq_corrected, e.duration_hours))
    return compute_lex_8h(pairs)


def risk_band(lex_8h_db: float) -> RiskBand:
    """Classify LEX,8h against Art. 188 thresholds."""
    if lex_8h_db < 80:
        return "green"
    if lex_8h_db < 85:
        return "yellow"
    if lex_8h_db < 87:
        return "orange"
    return "red"
