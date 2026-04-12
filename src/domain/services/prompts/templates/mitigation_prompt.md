# Template: Mitigation Prompt

## Descrizione
Suggerisce misure di prevenzione e protezione basate sui livelli di rischio.

## Input Context
- `lex_levels`: Mappa mansione -> LEX,8h
- `risk_bands`: Mappa mansione -> fascia rischio (negligible/low/medium/high)
- `affected_roles`: Lista mansioni a rischio
- `include_ppe`: Includi DPI (default: true)
- `include_engineering`: Includi controlli tecnici (default: true)
- `include_administrative`: Includi controlli organizzativi (default: true)

## Gerarchia Misure (D.Lgs. 81/2008)

1. **Eliminazione**: Eliminare la sorgente di rumore
2. **Sostituzione**: Sostituire con macchinario meno rumoroso
3. **Controlli Tecnici**: Isolamento, schermatura, silenziatori
4. **Controlli Amministrativi**: Rotazione, limitazione tempo esposizione
5. **DPI**: Protezione individuale (ultima risorsa)

## Output Atteso

```json
{
  "engineer_controls": [
    {
      "type": "Tipo controllo tecnico",
      "description": "Descrizione intervento",
      "estimated_effectiveness": 0.75,
      "estimated_cost": "low|medium|high",
      "priority": 1
    }
  ],
  "administrative_controls": [
    {
      "type": "Tipo controllo amministrativo",
      "description": "Descrizione",
      "estimated_effectiveness": 0.40,
      "priority": 2
    }
  ],
  "ppe_recommendations": [
    {
      "type": "Tipo DPI",
      "nrr": 25,
      "description": "Archi anti-rumore con NRR 25 dB",
      "suitable_for": ["Mansione 1", "Mansione 2"],
      "priority": 3
    }
  ],
  "priority_order": ["Controllo 1", "Controllo 2", "DPI"],
  "overall_risk_reduction": "Da 87 a 82 dB(A) stimato"
}
```

## DPI Standard

| Tipo | NRR tipico | Note |
|------|------------|------|
| Inserti auricolari | 25-35 dB | Usa singolo NRR |
| Archi anti-rumore | 20-25 dB | Più confortevoli |
| Cuffie anti-rumore | 25-35 dB | Migliore protezione |

## Vincoli

- Segui la gerarchia: tecnici prima di amministrativi, DPI per ultimo
- Indica sempre l'efficacia stimata
- Considera la praticabilità aziendale
- Proporziona le misure al livello di rischio
