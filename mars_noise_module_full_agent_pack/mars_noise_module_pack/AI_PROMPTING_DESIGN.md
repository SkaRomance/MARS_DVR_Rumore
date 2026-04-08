# AI Prompting Design - Modulo Rumore

## Obiettivo
Consentire all'utente di configurare e usare il modulo anche via prompt naturale, mantenendo output strutturato e controllabile.

## Modalità di prompting

### 1. Bootstrap prompt
Esempio:
> Azienda metalmeccanica con taglio, piegatura, saldatura, compressore e reparto finitura. Crea una prima valutazione rumore.

Output atteso:
- processi identificati
- mansioni ipotizzate
- sorgenti rumorose
- dati mancanti
- richiesta conferma

### 2. Review prompt
Esempio:
> Riesamina la mansione addetto piegatrice, confronta la durata di esposizione con la lavorazione effettiva.

### 3. Rewriting prompt
Esempio:
> Riscrivi il capitolo DVR rumore in linguaggio tecnico-formale.

### 4. Explain prompt
Esempio:
> Spiegami perché questa mansione supera il valore d'azione superiore.

## Regole di sicurezza AI

- Non inventare misure strumentali
- Evidenziare sempre assunzioni e stime
- Chiedere conferma sui dati critici
- Restituire output in JSON + testo umano leggibile
- Mantenere separati suggerimenti AI e dati approvati

## Schema output raccomandato
```json
{
  "summary": "",
  "detected_processes": [],
  "detected_roles": [],
  "detected_noise_sources": [],
  "missing_data": [],
  "assumptions": [],
  "confidence": 0.0,
  "next_actions": []
}
```
