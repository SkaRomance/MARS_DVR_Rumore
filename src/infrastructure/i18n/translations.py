from enum import Enum


class Language(str, Enum):
    it = "it"
    en = "en"


TRANSLATIONS = {
    "it": {
        "risk_band.negligible": "Trascurabile",
        "risk_band.low": "Basso",
        "risk_band.medium": "Medio",
        "risk_band.high": "Alto",
        "risk_band.critical": "Critico",
        "section.intro": "Introduzione",
        "section.methodology": "Metodologia",
        "section.results": "Risultati",
        "section.mitigation": "Misure di riduzione",
        "section.conclusion": "Conclusioni",
        "section.references": "Riferimenti normativi",
        "doc.title": "Valutazione del Rischio Rumore",
        "doc.subtitle": "D.Lgs. 81/2008 - Art. 190",
        "doc.cover_text": "Documento di Valutazione del Rischio da Agenti Fisici - Rumore",
        "label.company": "Azienda",
        "label.assessment_date": "Data valutazione",
        "label.next_review": "Prossima revisione",
        "label.prepared_by": "Redatto da",
        "label.approved_by": "Approvato da",
        "label.lex_8h": "LEX,8h [dB(A)]",
        "label.lcpeak": "LCpeak [dB(C)]",
        "label.risk_band": "Fascia di rischio",
        "label.job_role": "Mansione",
        "label.exposure_level": "Livello di esposizione",
        "label.uncertainty": "Incertezza estesa",
        "label.confidence": "Indice di confidenza",
        "label.k_impulse": "Correzione impulso K1",
        "label.k_tone": "Correzione tonale K2",
        "status.draft": "Bozza",
        "status.under_review": "In revisione",
        "status.approved": "Approvato",
        "status.archived": "Archiviato",
    },
    "en": {
        "risk_band.negligible": "Negligible",
        "risk_band.low": "Low",
        "risk_band.medium": "Medium",
        "risk_band.high": "High",
        "risk_band.critical": "Critical",
        "section.intro": "Introduction",
        "section.methodology": "Methodology",
        "section.results": "Results",
        "section.mitigation": "Mitigation measures",
        "section.conclusion": "Conclusions",
        "section.references": "Regulatory references",
        "doc.title": "Noise Risk Assessment",
        "doc.subtitle": "D.Lgs. 81/2008 - Art. 190",
        "doc.cover_text": "Physical Agent Risk Assessment Document - Noise",
        "label.company": "Company",
        "label.assessment_date": "Assessment date",
        "label.next_review": "Next review",
        "label.prepared_by": "Prepared by",
        "label.approved_by": "Approved by",
        "label.lex_8h": "LEX,8h [dB(A)]",
        "label.lcpeak": "LCpeak [dB(C)]",
        "label.risk_band": "Risk band",
        "label.job_role": "Job role",
        "label.exposure_level": "Exposure level",
        "label.uncertainty": "Extended uncertainty",
        "label.confidence": "Confidence index",
        "label.k_impulse": "Impulse correction K1",
        "label.k_tone": "Tonal correction K2",
        "status.draft": "Draft",
        "status.under_review": "Under review",
        "status.approved": "Approved",
        "status.archived": "Archived",
    },
}


def t(key: str, lang: str = "it") -> str:
    return TRANSLATIONS.get(lang, TRANSLATIONS["it"]).get(key, key)


def get_available_languages() -> list[str]:
    return list(TRANSLATIONS.keys())
