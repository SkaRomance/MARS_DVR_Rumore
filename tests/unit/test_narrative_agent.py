"""Unit tests for NarrativeAgent.

Narrative agent returns plain text (not JSON). MockProvider returns a
canned Italian paragraph; the agent strips whitespace and defensively
unwraps any code fences. Empty output raises NarrativeAgentError.
"""

from __future__ import annotations

import pytest

from src.domain.services.autopilot.narrative_agent import (
    NarrativeAgent,
    NarrativeAgentError,
)
from src.domain.services.autopilot.types import (
    PhaseExposureEstimate,
    ReviewFinding,
)
from src.infrastructure.llm.mock_provider import MockProvider


def _estimate(**over):
    defaults = dict(
        phase_id="ph-1",
        phase_name="Taglio lamiera",
        job_role="operaio",
        laeq_db=90.0,
        duration_hours=2.0,
        lcpeak_db=None,
        k_tone_db=0.0,
        k_imp_db=3.0,
        confidence=0.7,
        reasoning="stima",
        data_gaps=[],
    )
    defaults.update(over)
    return PhaseExposureEstimate(**defaults)


def _finding(**over):
    defaults = dict(
        phase_id="ph-1",
        severity="warning",
        issue="Bassa confidenza",
        recommendation="Misurazione diretta",
    )
    defaults.update(over)
    return ReviewFinding(**defaults)


SAMPLE_NARRATIVE = (
    "La valutazione del rischio rumore ai sensi del D.Lgs. 81/2008 (Artt. 187-198) e della norma "
    "ISO 9612 ha determinato un valore LEX,8h pari a 88.50 dB(A), collocando l'azienda nella banda "
    "di rischio orange (valore superiore d'azione superato). Per la fase 'Taglio lamiera' è stato "
    "stimato un LAeq di 90 dB(A) su una durata giornaliera di 2 ore; è stata applicata la correzione "
    "K_I=+3 dB per rumore impulsivo secondo la ISO 9612. Dalla revisione è emerso un rilievo di tipo "
    "warning relativo alla bassa confidenza della stima, per cui si raccomanda una misurazione "
    "fonometrica diretta. Ai sensi dell'Art. 192 del D.Lgs. 81/2008 si procederà con misure tecniche "
    "prioritarie, integrazione di DPI appropriati e sorveglianza sanitaria dei lavoratori esposti."
)


async def test_narrative_happy_path_returns_plain_text():
    provider = MockProvider(response_content=SAMPLE_NARRATIVE)
    agent = NarrativeAgent(provider)

    narrative = await agent.generate(
        lex_8h_db=88.5,
        risk_band="orange",
        estimates=[_estimate()],
        findings=[_finding()],
    )
    assert "LEX,8h" in narrative
    assert "D.Lgs. 81/2008" in narrative
    assert "88.50" in narrative
    assert provider.call_count == 1


async def test_narrative_strips_leading_trailing_whitespace():
    provider = MockProvider(response_content=f"\n\n  {SAMPLE_NARRATIVE}\n\n  ")
    agent = NarrativeAgent(provider)
    narrative = await agent.generate(88.5, "orange", [_estimate()], [])
    assert narrative == SAMPLE_NARRATIVE


async def test_narrative_strips_code_fence():
    provider = MockProvider(response_content=f"```text\n{SAMPLE_NARRATIVE}\n```")
    agent = NarrativeAgent(provider)
    narrative = await agent.generate(88.5, "orange", [_estimate()], [])
    assert narrative.startswith("La valutazione")


async def test_narrative_empty_output_raises():
    provider = MockProvider(response_content="   \n  \n  ")
    agent = NarrativeAgent(provider)
    with pytest.raises(NarrativeAgentError, match="empty"):
        await agent.generate(88.5, "orange", [_estimate()], [])


async def test_narrative_no_findings_passes():
    """Pipeline without findings still works (empty list is fine)."""
    provider = MockProvider(response_content=SAMPLE_NARRATIVE)
    agent = NarrativeAgent(provider)
    narrative = await agent.generate(82.0, "yellow", [_estimate()], [])
    assert narrative == SAMPLE_NARRATIVE


async def test_narrative_no_estimates_still_calls_llm():
    """The orchestrator gates on estimates, but the agent itself does not."""
    provider = MockProvider(response_content=SAMPLE_NARRATIVE)
    agent = NarrativeAgent(provider)
    narrative = await agent.generate(0.0, "green", [], [])
    # Agent makes the call; orchestrator decides whether to skip.
    assert provider.call_count == 1
    assert narrative == SAMPLE_NARRATIVE
