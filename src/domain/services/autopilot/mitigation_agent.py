"""MitigationAgent — D.Lgs. 81/2008 Art. 192 mitigation hierarchy via LLM.

For each phase whose LAeq >= 80 dB (action value), ask the LLM to propose
3-5 concrete mitigation measures mapped to the Art. 192 hierarchy:

1. Technical — source replacement, enclosure, damping, silencers
2. Organizational — job rotation, exposure time limits, scheduling
3. PPE — hearing protectors with NRR/SNR matched to residual exposure

Phases below 80 dB are skipped entirely (no LLM call for those phases).
If no risky phases exist, returns empty list with no LLM call at all.
"""

from __future__ import annotations

import json
import logging

from src.domain.services.autopilot.types import (
    MitigationSuggestion,
    PhaseExposureEstimate,
)
from src.infrastructure.llm.base import LLMProvider, LLMRequest

logger = logging.getLogger(__name__)


# D.Lgs. 81/2008 Art. 188 — lower action value
ACTION_THRESHOLD_DB = 80.0

ALLOWED_CATEGORIES = {"technical", "organizational", "ppe"}


SYSTEM_PROMPT_IT = """\
Sei un consulente HSE esperto nella definizione di misure di mitigazione del rischio rumore ai sensi del D.Lgs. 81/2008 (Art. 192) e della norma ISO 9612.

Il tuo compito: per ciascuna fase di lavoro con LAeq >= 80 dB(A) (valore inferiore d'azione), proporre 3-5 misure concrete di mitigazione seguendo la gerarchia prevista dall'Art. 192:

1. TECNICHE (prioritarie):
   - Sostituzione del macchinario/utensile con versione a bassa rumorosità
   - Incapsulamento / cabinatura acustica della sorgente
   - Schermi fonoassorbenti e silenziatori
   - Smorzamento vibrazionale (isolamento antivibrante)
   - Manutenzione preventiva (lubrificazione, sostituzione cuscinetti)

2. ORGANIZZATIVE:
   - Rotazione delle mansioni per ridurre l'esposizione giornaliera
   - Limitazione del tempo di esposizione / pause programmate
   - Pianificazione lavorazioni rumorose in orari con meno personale
   - Segnaletica delle aree a elevata rumorosità e formazione specifica

3. DPI (solo come misura residuale):
   - Cuffie / inserti auricolari con NRR o SNR adeguati
   - Selezionare DPI tali che il livello attenuato (L'Aeq) rientri sotto 80 dB(A)
   - Programma di sorveglianza sanitaria (audiometria)

Regole:
- Ogni misura DEVE essere pertinente al tipo di macchinario e al livello stimato.
- Stima una `expected_reduction_db` realistica (tipicamente: 3-6 dB per organizzative, 5-15 dB per tecniche, 15-30 dB per DPI di classe III).
- Se `expected_reduction_db` non è ragionevolmente stimabile, usa null.
- Preferisci soluzioni tecniche a DPI quando possibile (gerarchia Art. 192).
- NON proporre misure generiche (es. "stare attenti"): sii concreto.

IMPORTANTE: rispondi SOLO con JSON valido, nessun testo libero. Lo schema di output è:

{
  "suggestions": [
    {
      "phase_id": "string (dalla fase analizzata)",
      "category": "technical" | "organizational" | "ppe",
      "measure": "descrizione concreta della misura",
      "expected_reduction_db": 6.0,
      "reasoning": "breve motivazione della scelta"
    }
  ]
}
"""


class MitigationAgentError(RuntimeError):
    """Raised when the LLM returns malformed output that cannot be parsed."""


class MitigationAgent:
    """LLM-backed mitigation suggestions for phases above the action threshold."""

    def __init__(
        self,
        llm: LLMProvider,
        *,
        max_tokens: int = 1500,
        temperature: float = 0.3,  # slightly higher: want varied measures
    ):
        self._llm = llm
        self._max_tokens = max_tokens
        self._temperature = temperature

    async def suggest(
        self,
        estimates: list[PhaseExposureEstimate],
        lex_8h_db: float,
    ) -> list[MitigationSuggestion]:
        """Suggest mitigation measures for each phase with LAeq >= 80 dB.

        Phases below the action threshold are skipped. If no phase crosses
        the threshold, returns empty list with no LLM call.
        """
        risky = [e for e in estimates if e.laeq_db >= ACTION_THRESHOLD_DB]
        if not risky:
            return []

        user_prompt = self._build_user_prompt(risky, lex_8h_db)
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
    def _build_user_prompt(risky: list[PhaseExposureEstimate], lex_8h_db: float) -> str:
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
                "reasoning": e.reasoning,
            }
            for e in risky
        ]
        return (
            f"LEX,8h complessivo stimato: {lex_8h_db:.1f} dB(A).\n\n"
            "Fasi con LAeq >= 80 dB da mitigare:\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            "Proponi 3-5 misure per ciascuna fase, rispettando la gerarchia Art. 192 "
            "(tecniche > organizzative > DPI). Rispondi SOLO con JSON."
        )

    @staticmethod
    def _parse_response(content: str) -> list[MitigationSuggestion]:
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
                    raise MitigationAgentError(f"LLM returned non-JSON content: {content[:200]}") from exc
            else:
                raise MitigationAgentError(f"LLM returned non-JSON content: {content[:200]}") from exc

        raw_items = parsed.get("suggestions")
        if not isinstance(raw_items, list):
            raise MitigationAgentError("Missing 'suggestions' list in LLM response")

        results: list[MitigationSuggestion] = []
        for idx, raw in enumerate(raw_items):
            if not isinstance(raw, dict):
                logger.warning("Skipping non-dict suggestion at index %d", idx)
                continue

            phase_id = str(raw.get("phase_id", "")).strip()
            if not phase_id:
                logger.warning("Skipping suggestion %d: missing phase_id", idx)
                continue

            category = str(raw.get("category", "")).strip().lower()
            if category not in ALLOWED_CATEGORIES:
                logger.warning("Skipping suggestion %d: invalid category %r", idx, category)
                continue

            measure = str(raw.get("measure", "")).strip()
            if not measure:
                logger.warning("Skipping suggestion %d: empty measure", idx)
                continue

            expected_reduction = _nullable_float(raw.get("expected_reduction_db"))
            reasoning = str(raw.get("reasoning", "")).strip()

            results.append(
                MitigationSuggestion(
                    phase_id=phase_id,
                    category=category,  # type: ignore[arg-type]
                    measure=measure,
                    expected_reduction_db=expected_reduction,
                    reasoning=reasoning,
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


def _nullable_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "ACTION_THRESHOLD_DB",
    "MitigationAgent",
    "MitigationAgentError",
    "SYSTEM_PROMPT_IT",
]
