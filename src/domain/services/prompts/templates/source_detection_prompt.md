# Template: Source Detection Prompt

## Descrizione
Usato per identificare sorgenti di rumore da descrizioni testuali free-text.

## Input Context
- `description`: Descrizione testuale delle attivita lavorative o dell'ambiente
- `company_type`: Tipo di azienda (default: manifatturiero)
- `assessment_id`: ID della valutazione opzionale

## Output Atteso
JSON con la seguente struttura:

```json
{
  "sources": [
    {
      "type": "Tipo macchinario/attivita",
      "description": "Descrizione dettagliata della sorgente",
      "noise_level": "75-85 dB(A)",
      "confidence": 0.85,
      "source_match": "Riferimento PAF opzionale"
    }
  ],
  "confidence": 0.80,
  "notes": "Note sulla procedura di rilevamento"
}
```

## Regole di Generazione

1. **Tipo Sorgente**: Classifica in categorie PAF (macchinari, attrezzature, ambienti)
2. **Livello Rumore**: Indica livelli tipici in dB(A) con range quando possibile
3. **Confidence**: Valuta 0.0-1.0 basata su quanto sei sicuro del rilevamento
4. **Source Match**: Se possibile, collega a voci del catalogo PAF

## Vincoli

- NON inventare livelli di rumore specifici non presenti in letteratura
- Usa solo informazioni derivate dalla descrizione fornita
- Per ogni sorgente indica sempre il livello di confidenza
- Distingui tra informazioni certe e ipotesi

## Esempio di Output

```json
{
  "sources": [
    {
      "type": "Tornio automatico",
      "description": "Macchinario per lavorazione meccanica con rotazione ad alta velocita",
      "noise_level": "78-85 dB(A)",
      "confidence": 0.88,
      "source_match": "PAF-AT-001"
    },
    {
      "type": "Compressore aria",
      "description": "Sistema di压缩空气 per utensili pneumatici",
      "noise_level": "75-80 dB(A)",
      "confidence": 0.75,
      "source_match": "PAF-CM-003"
    }
  ],
  "confidence": 0.82,
  "notes": "Rilevate 2 sorgenti principali. Si consiglia misurazione fonometrica per conferma."
}
```
