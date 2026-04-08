# Template: Bootstrap Prompt

## Descrizione
Usato per generare suggerimenti iniziali per una nuova valutazione del rumore.

## Input Context
- `ateco_codes`: Lista codici ATECO 2007
- `company_description`: Descrizione testuale dell'azienda
- `existing_data`: Dati già presenti nella valutazione

## Output Atteso
JSON con la seguente struttura:

```json
{
  "processes": [
    {
      "name": "Nome processo lavorativo",
      "description": "Descrizione dettagliata",
      "typical_noise_sources": ["Sorgente 1", "Sorgente 2"],
      "confidence": 0.85
    }
  ],
  "roles": [
    {
      "name": "Mansione",
      "typical_exposure_hours": 6.5,
      "processes": ["Processo 1"],
      "confidence": 0.80
    }
  ],
  "noise_sources": [
    {
      "type": "Tipo macchinario",
      "typical_noise_level": "75-85 dB(A)",
      "source_confidence": 0.75
    }
  ],
  "missing_data": [
    "Dati mancanti da raccogliere"
  ],
  "next_actions": [
    "Azioni successive consigliate"
  ],
  "confidence_overall": 0.78
}
```

## Regole di Generazione

1. **Codici ATECO**: Usa i codici ATECO forniti per identificare processi tipici
2. **Macchinari**: Fai riferimento alla banca dati PAF (Portal Agenti Fisici) se possibile
3. **Mansioni**: Collega ogni mansione ai processi identificati
4. **Rumore**: Indica livelli tipici in dB(A) con range quando possibile
5. **Confidence**: Valuta 0.0-1.0 basata su quanto sei sicuro del suggerimento

## Vincoli

- NON inventare dati specifici di misurazione
- Usa solo informazioni derivate da ATECO o conosciute
- Per ogni suggerimento indica sempre il livello di confidenza
- Distingui tra informazioni certe e ipotesi

## Esempio di Output

```json
{
  "processes": [
    {
      "name": "Lavorazione meccanica con CNC",
      "description": "Operazioni di tornitura e fresatura su macchinari CNC",
      "typical_noise_sources": ["Tornio CNC", "Fresatrice", "Compressore"],
      "confidence": 0.92
    }
  ],
  "roles": [
    {
      "name": "Operaio CNC",
      "typical_exposure_hours": 7.5,
      "processes": ["Lavorazione meccanica con CNC"],
      "confidence": 0.88
    }
  ],
  "noise_sources": [
    {
      "type": "Tornio CNC",
      "typical_noise_level": "78-85 dB(A)",
      "source_confidence": 0.85
    }
  ],
  "missing_data": [
    "Misurazioni fonometriche specifiche",
    "Verifica presenza ofabbisogno di DPI"
  ],
  "next_actions": [
    "Raccogliere schede tecniche macchinari",
    "Verificare esistenza misurazioni precedenti",
    "Proporre ciclo di misurazioni"
  ],
  "confidence_overall": 0.85
}
```
