"""Unit tests for ReviewAgent.

Mirrors the test patterns used in test_exposure_estimator.py: MockProvider
with canned JSON, happy path, empty input (no LLM call), malformed JSON
raises typed exception.
"""

from __future__ import annotations

import json

import pytest

from src.domain.services.autopilot.review_agent import (
    ReviewAgent,
    ReviewAgentError,
)
from src.domain.services.autopilot.types import PhaseExposureEstimate
from src.infrastructure.llm.mock_provider import MockProvider


def _estimate(**over):
    defaults = dict(
        phase_id="ph-1",
        phase_name="Taglio lamiera",
        job_role="operaio",
        laeq_db=95.0,
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


def _provider_for(findings: list[dict]) -> MockProvider:
    return MockProvider(response_content=json.dumps({"findings": findings}))


async def test_review_happy_path_returns_findings():
    provider = _provider_for(
        [
            {
                "phase_id": "ph-1",
                "severity": "warning",
                "issue": "Outlier: LAeq 12 dB sopra il gruppo di pari",
                "recommendation": "Verificare con misurazione fonometrica diretta.",
            },
            {
                "phase_id": "ph-2",
                "severity": "info",
                "issue": "Bassa confidenza (0.35)",
                "recommendation": "Raccogliere la scheda tecnica del macchinario.",
            },
        ]
    )
    agent = ReviewAgent(provider)

    findings = await agent.review([_estimate(phase_id="ph-1"), _estimate(phase_id="ph-2")])

    assert len(findings) == 2
    assert findings[0].phase_id == "ph-1"
    assert findings[0].severity == "warning"
    assert "Outlier" in findings[0].issue
    assert findings[1].severity == "info"
    assert provider.call_count == 1


async def test_review_empty_input_skips_llm_call():
    provider = MockProvider(response_content='{"findings": []}')
    agent = ReviewAgent(provider)
    findings = await agent.review([])
    assert findings == []
    assert provider.call_count == 0


async def test_review_empty_findings_returns_empty_list():
    provider = _provider_for([])
    agent = ReviewAgent(provider)
    findings = await agent.review([_estimate()])
    assert findings == []


async def test_review_malformed_json_raises():
    provider = MockProvider(response_content="NOT JSON")
    agent = ReviewAgent(provider)
    with pytest.raises(ReviewAgentError, match="non-JSON"):
        await agent.review([_estimate()])


async def test_review_missing_findings_field_raises():
    provider = MockProvider(response_content=json.dumps({"other_field": []}))
    agent = ReviewAgent(provider)
    with pytest.raises(ReviewAgentError, match="Missing 'findings'"):
        await agent.review([_estimate()])


async def test_review_code_fence_is_stripped():
    body = json.dumps(
        {
            "findings": [
                {
                    "phase_id": "ph-1",
                    "severity": "warning",
                    "issue": "X",
                    "recommendation": "Y",
                }
            ]
        }
    )
    provider = MockProvider(response_content=f"```json\n{body}\n```")
    agent = ReviewAgent(provider)
    findings = await agent.review([_estimate()])
    assert len(findings) == 1


async def test_review_invalid_severity_is_dropped():
    provider = _provider_for(
        [
            {
                "phase_id": "ph-1",
                "severity": "CRITICAL",  # not in the allowed set
                "issue": "X",
                "recommendation": "Y",
            },
            {
                "phase_id": "ph-2",
                "severity": "error",
                "issue": "real error",
                "recommendation": "fix it",
            },
        ]
    )
    agent = ReviewAgent(provider)
    findings = await agent.review([_estimate(phase_id="ph-1"), _estimate(phase_id="ph-2")])
    assert len(findings) == 1
    assert findings[0].phase_id == "ph-2"


async def test_review_drops_finding_with_missing_phase_id():
    provider = _provider_for(
        [
            {"severity": "warning", "issue": "orphan", "recommendation": "x"},
            {
                "phase_id": "ph-1",
                "severity": "info",
                "issue": "ok",
                "recommendation": "ok",
            },
        ]
    )
    agent = ReviewAgent(provider)
    findings = await agent.review([_estimate()])
    assert len(findings) == 1
    assert findings[0].phase_id == "ph-1"


async def test_review_drops_finding_with_empty_issue():
    provider = _provider_for(
        [
            {
                "phase_id": "ph-1",
                "severity": "info",
                "issue": "",
                "recommendation": "x",
            }
        ]
    )
    agent = ReviewAgent(provider)
    findings = await agent.review([_estimate()])
    assert findings == []
