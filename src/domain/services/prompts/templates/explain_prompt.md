# Template: Explain Prompt

## Descrizione
Genera spiegazioni tecniche su calcoli, decisioni di rischio, soglie normative.

## Input Context
- `subject`: Argomento da spiegare (lex_calculation, risk_band, threshold, mitigation)
- `target_id`: ID elemento specifico (opzionale)
- `level`: Livello dettaglio (beginner, technical, expert)
- `context_data`: Dati contestuali per la spiegazione

## Livelli di Dettaglio

### Beginner
Spiegazione semplice, senza tecnicismi.
Usa analogie e esempi quotidiani.
Lunghezza: 2-3 paragrafi.

### Technical
Spiegazione con termini tecnici appropriati.
Riferimenti normativi e calcoli.
Lunghezza: 1 pagina.

### Expert
Approfondimento completo.
Derivazioni matematiche se relevanti.
Riferimenti a standard ISO/EN.
Lunghezza: 2-3 pagine.

## Output Atteso

```json
{
  "explanation": "Testo della spiegazione in italiano",
  "technical_details": {
    "formulas": ["Formula ISO 9612"],
    "references": ["Art. 188 D.Lgs. 81/2008"],
    "values": {"param": "value"}
  },
  "related_regulations": [
    "Riferimento normativo 1",
    "Riferimento normativo 2"
  ],
  "confidence": 0.92
}
```

## Argomenti Supportati

### lex_calculation
Spiega come si calcola LEX,8h secondo ISO 9612.

### risk_band
Spiega come viene classificata la fascia di rischio.

### threshold
Spiega il significato delle soglie 80/85/87 dB(A).

### mitigation
Spiega le misure di prevenzione disponibili.
