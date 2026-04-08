"""Noise exposure report generator using Jinja2 templates."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from jinja2 import Environment, PackageLoader, select_autoescape


@dataclass
class ReportContext:
    """Context data for report generation."""

    company_name: str
    unit_site_name: str
    assessment_date: datetime
    assessment_id: str
    lex_8h: float
    lex_weekly: Optional[float]
    lcpeak: Optional[float]
    risk_band: str
    uncertainty_db: Optional[float]
    confidence_score: float
    workers_count: int
    job_roles: list[dict]
    mitigation_actions: list[dict]
    measurement_protocol: Optional[str] = None
    instrument_class: Optional[str] = None


REPORT_TEMPLATE = """
VALUTAZIONE RISCHIO RUMORE
=========================
D.Lgs. 81/2008 Titolo VIII Capo II

DATI IDENTIFICATIVI
-------------------
Soggetto: {{ company_name }}
Unità Produttiva: {{ unit_site_name }}
Data Valutazione: {{ assessment_date.strftime('%d/%m/%Y') }}
ID Valutazione: {{ assessment_id }}

SINTESI RISULTATI
-----------------
Livello di Esposizione Giornaliero (LEX,8h): {{ lex_8h }} dB(A)
{% if lex_weekly %}
Livello di Esposizione Settimanale (LEX,weekly): {{ lex_weekly }} dB(A)
{% endif %}
{% if lcpeak %}
Livello di Pressione Acustica di Picco (LCPicco): {{ lcpeak }} dB(C)
{% endif %}
Classe di Rischio: {{ risk_band|upper }}
{% if uncertainty_db %}
Incertezza Espansione (k=2): ±{{ uncertainty_db }} dB
{% endif %}
Affidabilità del Calcolo: {{ (confidence_score * 100)|round|int }}%
Numero Lavoratori Esposti: {{ workers_count }}

ESPOSIZIONE PER MANSIONE
------------------------
{% for role in job_roles %}
- {{ role.name }}: LEX,8h = {{ role.lex_8h }} dB(A) ({{ role.workers_count }} lavoratori)
{% endfor %}

MISURE DI PREVENZIONE E PROTEZIONE
----------------------------------
{% for action in mitigation_actions %}
- [{{ action.priority|upper }}] {{ action.description }}
  Scadenza: {{ action.deadline|default('N/A') }}
{% endfor %}

{% if measurement_protocol %}
METODOLOGIA DI MISURA
---------------------
Protocollo: {{ measurement_protocol }}
Strumento: {{ instrument_class|default('N/D') }}
{% endif %}

LEGAL REFERENCE: D.Lgs. 81/2008 Art. 190-196
FONTE CALCOLO: ISO 9612:2011
"""


class ReportGenerator:
    """Generates noise assessment reports."""

    def __init__(self):
        self.env = Environment(
            loader=PackageLoader("src.domain.services", "templates"),
            autoescape=select_autoescape(default=False),
        )
        if not self.env.loader.list_templates():
            self.env = None

    def generate(self, context: ReportContext) -> str:
        """Generate report text from context."""
        if self.env is None:
            return self._generate_from_template(context)
        return self._generate_with_jinja(context)

    def _generate_with_jinja(self, context: ReportContext) -> str:
        """Generate using Jinja2 template."""
        template = self.env.from_string(REPORT_TEMPLATE)
        return template.render(**self._context_to_dict(context))

    def _generate_from_template(self, context: ReportContext) -> str:
        """Generate using simple string replacement."""
        ctx = self._context_to_dict(context)
        template = REPORT_TEMPLATE

        for key, value in ctx.items():
            if isinstance(value, datetime):
                template = template.replace(
                    f"{{{{ {key} }}}}", value.strftime("%d/%m/%Y")
                )
            elif isinstance(value, list):
                continue
            elif value is None:
                template = template.replace(f"{{{{ {key} }}}}", "N/D")
            else:
                template = template.replace(f"{{{{ {key} }}}}", str(value))

        return template

    def _context_to_dict(self, context: ReportContext) -> dict:
        """Convert context to dict for template rendering."""
        return {
            "company_name": context.company_name,
            "unit_site_name": context.unit_site_name,
            "assessment_date": context.assessment_date,
            "assessment_id": context.assessment_id,
            "lex_8h": context.lex_8h,
            "lex_weekly": context.lex_weekly,
            "lcpeak": context.lcpeak,
            "risk_band": context.risk_band,
            "uncertainty_db": context.uncertainty_db,
            "confidence_score": context.confidence_score,
            "workers_count": context.workers_count,
            "job_roles": context.job_roles,
            "mitigation_actions": context.mitigation_actions,
            "measurement_protocol": context.measurement_protocol,
            "instrument_class": context.instrument_class,
        }
