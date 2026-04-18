"""ExposureEstimatorAgent — stima LAeq + durata per fase/mansione via LLM.

L'agente legge le fasi di lavoro + macchinari dal DVR MARS, opzionalmente
incrocia con il catalogo PAF (Portale Agenti Fisici) per sorgenti note,
e chiede al modello di stimare:
- LAeq (dB(A)) per fase/mansione
- durata esposizione (h/giorno)
- LCpeak (dB(C)) quando rilevante
- K_T (tonale) / K_I (impulsiva) per ISO 9612
- confidence + reasoning + data_gaps espliciti

Framework legale esplicito nel system prompt → il modello si ancora su
Art. 188 D.Lgs. 81/2008 e distingue correttamente i valori soglia.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from src.domain.services.autopilot.types import PhaseExposureEstimate, PhaseInput
from src.infrastructure.llm.base import LLMProvider, LLMRequest

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_IT = """\
Sei un consulente HSE esperto in valutazione del rischio rumore ai sensi del D.Lgs. 81/2008 (Art. 188 e seguenti) e della norma tecnica ISO 9612.

Il tuo compito: stimare l'esposizione al rumore per fasi di lavoro specifiche, producendo LAeq (dB(A)), durata (h/giorno), eventuale LCpeak (dB(C)), e correzioni K per carattere tonale/impulsivo, sulla base delle informazioni fornite (descrizione fase, macchinari, mansione).

Framework legale (valori di riferimento LEX,8h):
- Valore inferiore d'azione: 80 dB(A) — sorveglianza sanitaria, formazione, DPI a richiesta
- Valore superiore d'azione: 85 dB(A) — DPI obbligatori, formazione specifica
- Valore limite esposizione: 87 dB(A) — protezione DPI non deve essere superata

Regole di stima:
1. Se il macchinario è riconoscibile (es. flessibile, trapano a percussione, compressore), usa valori tipici di letteratura per la categoria.
2. Se la fase è generica (es. "assemblaggio"), stima conservativamente sulla base del contesto (officina metalmeccanica, edilizia, ecc.).
3. Le correzioni K (ISO 9612):
   - K_T = +3 dB se componenti tonali udibili (es. ventole, pompe centrifughe)
   - K_T = +6 dB se forte tonalità
   - K_I = +3 dB se rumore impulsivo moderato (es. martellatura leggera)
   - K_I = +6 dB se impulsi forti (es. chiodatrice, martello pneumatico pesante)
   - Default: 0 per entrambi se non dichiarato o non applicabile.
4. LCpeak è opzionale: includilo solo se la fase genera picchi impulsivi significativi (martellatura, sparo, chiodatura).
5. La durata (h/giorno) è tipicamente 1-4h per una singola fase; raramente 8h. Se la descrizione non specifica, stima sul tipo di lavoro.
6. Confidence (0.0-1.0):
   - 0.8-1.0: dati dettagliati (modello macchina, riferimento PAF)
   - 0.5-0.8: categoria di macchinario chiara
   - 0.2-0.5: stima da descrizione generica
   - < 0.2: dati insufficienti — usa data_gaps per segnalarlo
7. data_gaps: lista di stringhe che elenca DATI MANCANTI noti (es. "modello macchina non specificato", "durata esposizione non chiara"). NON inventare numeri quando mancano dati fondamentali: segnalalo qui.

IMPORTANTE: rispondi SOLO con JSON valido, nessun testo libero. Lo schema di output è:

{
  "estimates": [
    {
      "phase_id": "string (dal input)",
      "phase_name": "string (dal input)",
      "job_role": "string o null",
      "laeq_db": 85.2,
      "duration_hours": 2.5,
      "lcpeak_db": 130.0,
      "k_tone_db": 0,
      "k_imp_db": 3,
      "confidence": 0.75,
      "reasoning": "breve (1-2 frasi) motivazione della stima",
      "data_gaps": ["modello non specificato"]
    }
  ]
}
"""


class ExposureEstimatorError(RuntimeError):
    """Raised when the LLM returns malformed output that cannot be parsed."""


class ExposureEstimatorAgent:
    """Wraps an LLM + Italian prompt to produce phase exposure estimates."""

    def __init__(
        self,
        llm: LLMProvider,
        *,
        max_tokens: int = 1200,
        temperature: float = 0.25,  # low: we want deterministic conservative numbers
    ):
        self._llm = llm
        self._max_tokens = max_tokens
        self._temperature = temperature

    async def estimate(
        self,
        phases: list[PhaseInput],
        *,
        industry_context: str | None = None,
    ) -> list[PhaseExposureEstimate]:
        """Estimate exposure for each phase. Returns one estimate per phase
        (or one per phase/job_role combination when job_roles are distinct).

        Empty input returns empty list — no LLM call.
        """
        if not phases:
            return []

        user_prompt = self._build_user_prompt(phases, industry_context)
        request = LLMRequest(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT_IT,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        response = await self._llm.generate(request)
        return self._parse_response(response.content, phases)

    # ── internal ───────────────────────────────────────────────────

    @staticmethod
    def _build_user_prompt(
        phases: list[PhaseInput], industry_context: str | None
    ) -> str:
        phases_json = [
            {
                "phase_id": p.phase_id,
                "phase_name": p.phase_name,
                "description": p.description or "",
                "job_role": p.job_role or "",
                "equipments": p.equipments,
            }
            for p in phases
        ]
        header = "Ecco le fasi da analizzare:\n\n"
        ctx = (
            f"Contesto settoriale: {industry_context}\n\n"
            if industry_context
            else ""
        )
        return (
            f"{ctx}{header}"
            f"{json.dumps(phases_json, ensure_ascii=False, indent=2)}\n\n"
            f"Produci una stima per ciascuna fase, rispettando lo schema JSON "
            f"richiesto nel system prompt. Rispondi SOLO con JSON."
        )

    @staticmethod
    def _parse_response(
        content: str, phases: list[PhaseInput]
    ) -> list[PhaseExposureEstimate]:
        # Strip common LLM noise — code fences, leading prose
        cleaned = content.strip()
        if cleaned.startswith("```"):
            # Drop the fence line, and the closing fence if present
            lines = cleaned.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            # Best-effort: try to find a top-level { ... } block
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if 0 <= start < end:
                try:
                    parsed = json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    raise ExposureEstimatorError(
                        f"LLM returned non-JSON content: {content[:200]}"
                    ) from exc
            else:
                raise ExposureEstimatorError(
                    f"LLM returned non-JSON content: {content[:200]}"
                ) from exc

        raw_estimates = parsed.get("estimates")
        if not isinstance(raw_estimates, list):
            raise ExposureEstimatorError(
                "Missing 'estimates' list in LLM response"
            )

        phase_by_id = {p.phase_id: p for p in phases}
        results: list[PhaseExposureEstimate] = []
        for idx, raw in enumerate(raw_estimates):
            if not isinstance(raw, dict):
                logger.warning("Skipping non-dict estimate at index %d", idx)
                continue
            phase_id = str(raw.get("phase_id", ""))
            phase_name = str(raw.get("phase_name", ""))
            # Fall back to input if LLM dropped the phase_name
            if not phase_name and phase_id in phase_by_id:
                phase_name = phase_by_id[phase_id].phase_name

            try:
                laeq = float(raw.get("laeq_db", 0))
                duration = float(raw.get("duration_hours", 0))
            except (TypeError, ValueError) as exc:
                logger.warning(
                    "Skipping estimate %d: non-numeric laeq/duration: %s", idx, exc
                )
                continue

            if laeq <= 0 or duration <= 0:
                logger.warning(
                    "Skipping estimate %d: non-positive laeq=%s duration=%s",
                    idx, laeq, duration,
                )
                continue

            results.append(
                PhaseExposureEstimate(
                    phase_id=phase_id,
                    phase_name=phase_name,
                    job_role=raw.get("job_role") or None,
                    laeq_db=laeq,
                    duration_hours=duration,
                    lcpeak_db=_nullable_float(raw.get("lcpeak_db")),
                    k_tone_db=float(raw.get("k_tone_db", 0) or 0),
                    k_imp_db=float(raw.get("k_imp_db", 0) or 0),
                    confidence=_clamp01(raw.get("confidence", 0.5)),
                    reasoning=str(raw.get("reasoning", "")),
                    data_gaps=[
                        str(g) for g in (raw.get("data_gaps") or []) if g
                    ],
                    source="llm_inferred",
                )
            )
        return results


def _nullable_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp01(value: Any) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, v))
