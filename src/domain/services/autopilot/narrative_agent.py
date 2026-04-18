"""NarrativeAgent — DVR "Valutazione del Rischio Rumore" paragraph generator.

Produces the Italian narrative paragraph that goes into the DVR document
section dedicated to noise risk assessment. Unlike the other agents this
one returns PLAIN TEXT (not JSON) — the system prompt is explicit about
this and the parsing is a simple strip/validation.

The narrative must cite:
- LEX,8h numeric value + risk band (D.Lgs. 81/2008 Art. 188 thresholds)
- K corrections used (ISO 9612 — K_T tonale, K_I impulsiva)
- At least one concrete phase finding (outlier, low-confidence, etc.)
- Length: 400-800 Italian words.
"""

from __future__ import annotations

import logging

from src.domain.services.autopilot.types import (
    PhaseExposureEstimate,
    ReviewFinding,
)
from src.infrastructure.llm.base import LLMProvider, LLMRequest

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_IT = """\
Sei un consulente HSE che redige la sezione "Valutazione del Rischio Rumore" del Documento di Valutazione dei Rischi (DVR) di un'azienda, ai sensi del D.Lgs. 81/2008 (Titolo VIII, Capo II, Artt. 187-198) e della norma tecnica ISO 9612.

Il tuo compito: generare il paragrafo narrativo da inserire nel DVR. Il testo deve essere professionale, coerente con la terminologia normativa italiana, e deve citare:

1. Il valore di LEX,8h calcolato (in dB(A), con decimale) e la banda di rischio secondo Art. 188:
   - < 80 dB(A)  → rischio trascurabile (al di sotto del valore inferiore d'azione)
   - 80 <= x < 85 → valore inferiore d'azione superato
   - 85 <= x < 87 → valore superiore d'azione superato
   - >= 87       → valore limite di esposizione superato
2. Le correzioni K applicate secondo ISO 9612 (K_T per componenti tonali, K_I per componenti impulsive), spiegando brevemente il loro significato.
3. Almeno un riferimento concreto a una fase specifica tra quelle fornite (cita il phase_name e il LAeq).
4. Se sono presenti review_findings con severity "warning" o "error", menzionale esplicitamente indicando le azioni consigliate.
5. Gli obblighi conseguenti alla banda di rischio (es. sorveglianza sanitaria, DPI obbligatori, formazione).

Requisiti di forma:
- Lunghezza: 400-800 parole (italiane).
- Registro tecnico-professionale, adatto a un documento ufficiale.
- NON includere intestazioni Markdown (#, ##), NON elenchi puntati con "-", NON tabelle.
- Usa paragrafi discorsivi. Ammessi elenchi inline con "a)", "b)", "c)" se utili.
- Cita le norme in forma esplicita (es. "ai sensi dell'Art. 188 del D.Lgs. 81/2008").

IMPORTANTE: rispondi SOLO con il testo del paragrafo. NON restituire JSON, NON aggiungere preamboli tipo "Ecco il paragrafo:" o commenti finali. Solo testo.
"""


class NarrativeAgentError(RuntimeError):
    """Raised when the LLM returns empty / unusable narrative."""


class NarrativeAgent:
    """LLM-backed generator of the DVR noise risk narrative paragraph."""

    def __init__(
        self,
        llm: LLMProvider,
        *,
        max_tokens: int = 1800,
        temperature: float = 0.4,  # moderate: want prose variation but stay on-topic
    ):
        self._llm = llm
        self._max_tokens = max_tokens
        self._temperature = temperature

    async def generate(
        self,
        lex_8h_db: float,
        risk_band: str,
        estimates: list[PhaseExposureEstimate],
        findings: list[ReviewFinding],
    ) -> str:
        """Generate the Italian DVR narrative paragraph (plain text)."""
        user_prompt = self._build_user_prompt(lex_8h_db, risk_band, estimates, findings)
        request = LLMRequest(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT_IT,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        response = await self._llm.generate(request)
        return self._clean_response(response.content)

    # ── internal ───────────────────────────────────────────────────

    @staticmethod
    def _build_user_prompt(
        lex_8h_db: float,
        risk_band: str,
        estimates: list[PhaseExposureEstimate],
        findings: list[ReviewFinding],
    ) -> str:
        phases_summary = (
            "\n".join(
                [
                    f"- {e.phase_name}"
                    + (f" [{e.job_role}]" if e.job_role else "")
                    + f": LAeq={e.laeq_db:.1f} dB(A), durata={e.duration_hours:.1f}h, "
                    f"K_T={e.k_tone_db:.0f} K_I={e.k_imp_db:.0f}, confidence={e.confidence:.2f}"
                    for e in estimates
                ]
            )
            or "(nessuna fase rilevante identificata)"
        )

        findings_summary = (
            "\n".join([f"- [{f.severity.upper()}] {f.phase_id}: {f.issue} — {f.recommendation}" for f in findings])
            or "(nessun rilievo particolare dalla revisione)"
        )

        return (
            f"Dati di input per la narrativa DVR:\n\n"
            f"LEX,8h calcolato: {lex_8h_db:.2f} dB(A)\n"
            f"Banda di rischio: {risk_band}\n\n"
            f"Stime per fase:\n{phases_summary}\n\n"
            f"Rilievi della revisione:\n{findings_summary}\n\n"
            f"Genera la sezione 'Valutazione del Rischio Rumore' del DVR secondo le istruzioni del system prompt. "
            f"Rispondi SOLO con il testo del paragrafo."
        )

    @staticmethod
    def _clean_response(content: str) -> str:
        cleaned = content.strip()
        # Strip accidental code fences even though we asked for plain text
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        if not cleaned:
            raise NarrativeAgentError("LLM returned empty narrative")
        return cleaned


__all__ = ["NarrativeAgent", "NarrativeAgentError", "SYSTEM_PROMPT_IT"]
