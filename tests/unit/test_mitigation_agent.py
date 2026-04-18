"""Unit tests for MitigationAgent.

Mirrors test_exposure_estimator.py patterns: MockProvider canned JSON,
happy path, phases below threshold are skipped, malformed output raises.
"""

from __future__ import annotations

import json

import pytest

from src.domain.services.autopilot.mitigation_agent import (
    ACTION_THRESHOLD_DB,
    MitigationAgent,
    MitigationAgentError,
)
from src.domain.services.autopilot.types import PhaseExposureEstimate
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
        k_imp_db=0.0,
        confidence=0.7,
        reasoning="stima",
        data_gaps=[],
    )
    defaults.update(over)
    return PhaseExposureEstimate(**defaults)


def _provider_for(suggestions: list[dict]) -> MockProvider:
    return MockProvider(response_content=json.dumps({"suggestions": suggestions}))


async def test_mitigation_happy_path():
    provider = _provider_for(
        [
            {
                "phase_id": "ph-1",
                "category": "technical",
                "measure": "Sostituzione con flessibile a bassa rumorosità",
                "expected_reduction_db": 8.0,
                "reasoning": "Prodotti certificati esistono sul mercato",
            },
            {
                "phase_id": "ph-1",
                "category": "ppe",
                "measure": "Cuffie antirumore SNR=28 dB",
                "expected_reduction_db": 20.0,
                "reasoning": "Residuale per proteggere dal rumore impulsivo",
            },
            {
                "phase_id": "ph-1",
                "category": "organizational",
                "measure": "Rotazione ogni 2 ore",
                "expected_reduction_db": 3.0,
                "reasoning": "Dimezza l'esposizione cumulativa",
            },
        ]
    )
    agent = MitigationAgent(provider)
    sugs = await agent.suggest([_estimate(laeq_db=95.0)], lex_8h_db=92.0)
    assert len(sugs) == 3
    assert {s.category for s in sugs} == {"technical", "ppe", "organizational"}
    assert all(s.phase_id == "ph-1" for s in sugs)
    assert provider.call_count == 1


async def test_mitigation_skips_phases_below_action_threshold():
    """79 dB is below threshold → skipped, no LLM call."""
    provider = MockProvider(response_content='{"suggestions": []}')
    agent = MitigationAgent(provider)
    sugs = await agent.suggest([_estimate(laeq_db=ACTION_THRESHOLD_DB - 1.0)], lex_8h_db=75.0)
    assert sugs == []
    assert provider.call_count == 0


async def test_mitigation_threshold_boundary_included():
    """Exactly 80 dB triggers an LLM call (>= threshold)."""
    provider = _provider_for(
        [
            {
                "phase_id": "ph-1",
                "category": "technical",
                "measure": "Schermo fonoassorbente",
                "expected_reduction_db": 5.0,
                "reasoning": "Prima linea",
            }
        ]
    )
    agent = MitigationAgent(provider)
    sugs = await agent.suggest([_estimate(laeq_db=ACTION_THRESHOLD_DB)], lex_8h_db=80.0)
    assert len(sugs) == 1
    assert provider.call_count == 1


async def test_mitigation_empty_input_skips_llm_call():
    provider = MockProvider(response_content='{"suggestions": []}')
    agent = MitigationAgent(provider)
    sugs = await agent.suggest([], lex_8h_db=0.0)
    assert sugs == []
    assert provider.call_count == 0


async def test_mitigation_mixed_only_calls_llm_for_risky():
    """Phases below threshold are filtered, but risky ones trigger one call."""
    provider = _provider_for(
        [
            {
                "phase_id": "ph-risky",
                "category": "technical",
                "measure": "Cabinatura",
                "expected_reduction_db": 10.0,
                "reasoning": "r",
            }
        ]
    )
    agent = MitigationAgent(provider)
    phases = [
        _estimate(phase_id="ph-ok", laeq_db=75.0),
        _estimate(phase_id="ph-risky", laeq_db=92.0),
    ]
    sugs = await agent.suggest(phases, lex_8h_db=88.0)
    assert len(sugs) == 1
    assert sugs[0].phase_id == "ph-risky"
    assert provider.call_count == 1


async def test_mitigation_malformed_json_raises():
    provider = MockProvider(response_content="NOT JSON")
    agent = MitigationAgent(provider)
    with pytest.raises(MitigationAgentError, match="non-JSON"):
        await agent.suggest([_estimate(laeq_db=95.0)], lex_8h_db=90.0)


async def test_mitigation_missing_suggestions_field_raises():
    provider = MockProvider(response_content=json.dumps({"other": []}))
    agent = MitigationAgent(provider)
    with pytest.raises(MitigationAgentError, match="Missing 'suggestions'"):
        await agent.suggest([_estimate(laeq_db=95.0)], lex_8h_db=90.0)


async def test_mitigation_invalid_category_is_dropped():
    provider = _provider_for(
        [
            {
                "phase_id": "ph-1",
                "category": "magic",  # not allowed
                "measure": "x",
                "expected_reduction_db": 5,
                "reasoning": "r",
            },
            {
                "phase_id": "ph-1",
                "category": "technical",
                "measure": "ok",
                "expected_reduction_db": 5,
                "reasoning": "r",
            },
        ]
    )
    agent = MitigationAgent(provider)
    sugs = await agent.suggest([_estimate(laeq_db=90.0)], lex_8h_db=88.0)
    assert len(sugs) == 1
    assert sugs[0].category == "technical"


async def test_mitigation_expected_reduction_null_ok():
    provider = _provider_for(
        [
            {
                "phase_id": "ph-1",
                "category": "organizational",
                "measure": "Turnazione",
                "expected_reduction_db": None,
                "reasoning": "Difficile da quantificare",
            }
        ]
    )
    agent = MitigationAgent(provider)
    sugs = await agent.suggest([_estimate(laeq_db=90.0)], lex_8h_db=88.0)
    assert len(sugs) == 1
    assert sugs[0].expected_reduction_db is None


async def test_mitigation_code_fence_is_stripped():
    body = json.dumps(
        {
            "suggestions": [
                {
                    "phase_id": "ph-1",
                    "category": "technical",
                    "measure": "M",
                    "expected_reduction_db": 6,
                    "reasoning": "r",
                }
            ]
        }
    )
    provider = MockProvider(response_content=f"```json\n{body}\n```")
    agent = MitigationAgent(provider)
    sugs = await agent.suggest([_estimate(laeq_db=90.0)], lex_8h_db=88.0)
    assert len(sugs) == 1
