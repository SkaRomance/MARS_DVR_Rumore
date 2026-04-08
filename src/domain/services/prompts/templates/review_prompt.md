# Template: Review Prompt

## Descrizione
Usato per verificare e revisionare una valutazione del rumore esistente.

## Input Context
- `assessment_data`: Struttura JSON della valutazione completa
- `company_name`: Nome dell'azienda
- `ateco_code`: Codice ATECO principale

## Obiettivi di Revisione

1. **Completezza**: Verifica che tutti i dati richiesti siano presenti
2. **Consistenza**: Controlla che non ci siano contraddizioni
3. **Correttezza**: Verifica calcoli e classificazioni
4. **Copertura**: Assicurati che tutti i reparti/mansioni siano coperti

## Output Atteso (JSON)

```json
{
  "issues": [
    {
      "severity": "error|warning|info",
      "category": "completezza|consistenza|correttezza|copertura",
      "description": "Descrizione del problema",
      "location": "Dove si trova il problema",
      "suggestion": "Come risolverlo"
    }
  ],
  "warnings": [
    {
      "description": "Warning",
      "location": "Dove",
      "suggestion": "Come risolvere"
    }
  ],
  "missing_data": [
    "Dati mancanti"
  ],
  "validation_passed": true|false,
  "overall_score": 0.85
}
```

## Categorie di Controllo

### Completezza
- [ ] Company data presente
- [ ] ATECO code valido
- [ ] Assessment date presente
- [ ] Responsabile valutazione indicato
- [ ] Tutte le mansioni coperte

### Consistenza
- [ ] LEX,8h coerente con singole fasi
- [ ] Durate fasi sommano a 8h (o tempo effettivo)
- [ ] Fonti di rumore associate a mansioni

### Correttezza
- [ ] Formula ISO 9612 applicata correttamente
- [ ] Soglie di rispetto rispettate (80/85/87 dB)
- [ ] K corrections appropriate

### Copertura
- [ ] Tutti i reparti analizzati
- [ ] Tutte le mansioni con esposizione significativa
- [ ] DPI previsti dove necessario

## Vincoli

- Sii conservativo nei giudizi
- Preferisci false positives a falsi negativi
- Per ogni issue indica se è bloccante o meno
