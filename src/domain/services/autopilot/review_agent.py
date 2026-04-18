"""ReviewAgent — cross-validation of ExposureEstimator output via LLM.

Given a list of PhaseExposureEstimate, this agent asks the LLM (acting as
an independent HSE reviewer) to flag:

- Outliers: phases whose LAeq is >10 dB outside the peer group average
- Low-confidence estimates: confidence < 0.5
- Aggregated data_gaps: missing info that could impact the assessment

The output is a structured list of ReviewFinding objects that downstream
agents (mitigation, narrative) can use to qualify their output, and that
eventually surfaces in the DVR audit trail.

Same structural pattern as `exposure_estimator.py`: Italian system prompt
framed in D.Lgs. 81/2008 + ISO 9612 terminology, strict JSON output,
typed exception on parse failure.
"""

from __future__ import annotations

import json
import logging

from src.domain.services.autopilot.types import PhaseExposureEstimate, ReviewFinding
from src.infrastructure.llm.base import LLMProvider, LLMRequest

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_IT = """\
Sei un consulente HSE indipendente incaricato di rivedere una valutazione del rischio rumore prodotta da un altro consulente, ai sensi del D.Lgs. 81/2008 (Art. 188 e seguenti) e della norma ISO 9612.

Il tuo compito è identificare anomalie, criticità e lacune informative nelle stime fornite. Non ri-calcolare LEX,8h: concentrati sulla coerenza dei dati di input.

Criteri di revisione:
1. OUTLIER: una fase con LAeq distante più di 10 dB dalla media del gruppo di pari (fasi con tipologia/mansione simile) è sospetta — va segnalata con severity="warning" e spiegata.
2. LOW CONFIDENCE: se confidence < 0.5, segnala con severity="warning" e suggerisci misure integrative (misurazione fonometrica diretta, richiesta scheda tecnica macchinario).
3. DATA GAPS: se la stima elenca data_gaps non banali (es. "modello macchina non specificato", "durata esposizione non confermata"), aggregali in una finding con severity="info" o "warning" a seconda dell'impatto.
4. COERENZA: se la combinazione LAeq + K_tone + K_imp supera 100 dB(A) corretto ma confidence è alta e data_gaps è vuoto, ipotizza un possibile errore (severity="error").
5. Se non ci sono problemi, restituisci una lista vuota: "findings": [].

IMPORTANTE: rispondi SOLO con JSON valido, nessun testo libero. Lo schema di output è:

{
  "findings": [
    {
      "phase_id": "string (dalla fase analizzata)",
      "severity": "info" | "warning" | "error",
      "issue": "breve descrizione dell'anomalia",
      "recommendation": "azione concreta consigliata al consulente HSE"
    }
  ]
}
"""


class ReviewAgentError(RuntimeError):
    """Raised when the LLM returns malformed output that cannot be parsed."""


class ReviewAgent:
    """LLM-backed review of ExposureEstimator output."""

    def __init__(
        self,
        llm: LLMProvider,
        *,
        max_tokens: int = 1000,
        temperature: float = 0.2,  # low: deterministic, conservative flags
    ):
        self._llm = llm
        self._max_tokens = max_tokens
        self._temperature = temperature

    async def review(self, estimates: list[PhaseExposureEstimate]) -> list[ReviewFinding]:
        """Review the estimates and return structured findings.

        Empty input returns empty list — no LLM call.
        """
        if not estimates:
            return []

        user_prompt = self._build_user_prompt(estimates)
        request = LLMRequest(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT_IT,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        response = await self._llm.generate(request)
        return self._parse_response(response.content)

    # ── internal ───────────────────────────────────────────────────

    @staticmethod
    def _build_user_prompt(estimates: list[PhaseExposureEstimate]) -> str:
        payload = [
            {
                "phase_id": e.phase_id,
                "phase_name": e.phase_name,
                "job_role": e.job_role,
                "laeq_db": e.laeq_db,
                "duration_hours": e.duration_hours,
                "lcpeak_db": e.lcpeak_db,
                "k_tone_db": e.k_tone_db,
                "k_imp_db": e.k_imp_db,
                "confidence": e.confidence,
                "reasoning": e.reasoning,
                "data_gaps": list(e.data_gaps),
            }
            for e in estimates
        ]
        return (
            "Ecco le stime di esposizione da rivedere:\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            "Identifica outlier, stime a bassa confidenza e lacune informative "
            "rilevanti. Rispondi SOLO con JSON rispettando lo schema richiesto."
        )

    @staticmethod
    def _parse_response(content: str) -> list[ReviewFinding]:
        cleaned = _strip_fences(content)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if 0 <= start < end:
                try:
                    parsed = json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    raise ReviewAgentError(f"LLM returned non-JSON content: {content[:200]}") from exc
            else:
                raise ReviewAgentError(f"LLM returned non-JSON content: {content[:200]}") from exc

        raw_findings = parsed.get("findings")
        if not isinstance(raw_findings, list):
            raise ReviewAgentError("Missing 'findings' list in LLM response")

        allowed_severity = {"info", "warning", "error"}
        results: list[ReviewFinding] = []
        for idx, raw in enumerate(raw_findings):
            if not isinstance(raw, dict):
                logger.warning("Skipping non-dict finding at index %d", idx)
                continue

            phase_id = str(raw.get("phase_id", "")).strip()
            if not phase_id:
                logger.warning("Skipping finding %d: missing phase_id", idx)
                continue

            severity = str(raw.get("severity", "info")).strip().lower()
            if severity not in allowed_severity:
                logger.warning("Skipping finding %d: invalid severity %r", idx, severity)
                continue

            issue = str(raw.get("issue", "")).strip()
            recommendation = str(raw.get("recommendation", "")).strip()
            if not issue:
                logger.warning("Skipping finding %d: empty issue", idx)
                continue

            results.append(
                ReviewFinding(
                    phase_id=phase_id,
                    severity=severity,  # type: ignore[arg-type]
                    issue=issue,
                    recommendation=recommendation,
                )
            )
        return results


def _strip_fences(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


__all__ = ["ReviewAgent", "ReviewAgentError", "SYSTEM_PROMPT_IT"]
