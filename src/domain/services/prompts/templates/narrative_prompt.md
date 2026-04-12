# Template: Narrative Generation Prompt

## Descrizione
Genera il testo narrativo per il capitolo DVR sulla valutazione del rischio rumore.

## Input Context
- `company_name`: Nome azienda
- `ateco_code`: Codice ATECO
- `assessment_date`: Data valutazione
- `responsible_name`: Nome responsabile valutazione
- `results`: Risultati calcoli LEX,8h
- `roles`: Mansioni analizzate
- `noise_sources`: Fonti di rumore identificate
- `mitigations`: Misure di prevenzione proposte

## Struttura Output

Il testo generato deve seguire questa struttura:

### 1. Premessa
Breve introduzione sulla normativa D.Lgs. 81/2008 e obblighi.

### 2. Riferimenti Aziendali
- Ragione sociale
- Codice ATECO
- Attività svolta
- Data valutazione
- Responsabile

### 3. Metodologia
Riferimento a ISO 9612 e modalità di calcolo.

### 4. Mansioni e Processi Analizzati
Elenco mansioni con LEX,8h e fascia di rischio.

### 5. Sorgenti di Rumore Indidivuante
Elenco fonti con livelli di emissione.

### 6. Dati Disponibili e Origine
- Dati misurati
- Dati dichiarati dal costruttore
- Dati stimati da knowledge base
- Dati suggeriti da AI (da validare)

### 7. Calcolo dell'Esposizione
Spiegazione calcoli effettuati con risultati.

### 8. Confronto con Soglie
Tabella confronto LEX,8h con soglie 80/85/87 dB(A).

### 9. Misure di Prevenzione e Protezione
- Misure tecniche
- Misure organizzative
- DPI forniti

### 10. Programma di Miglioramento
Azioni future previste.

### 11. Conclusioni
Sintesi finale e data prossimo aggiornamento.

## Regole di Stile

- **Lingua**: Italiano tecnico formale
- **Riferimenti normativi**: Art. 181, 185, 188 D.Lgs. 81/2008
- **Unità di misura**: dB(A), dB(C) come da normativa
- **Distinzione dati**: Indica chiaramente origine (misurato/stimato/dichiarato/AI)

## Vincoli

- Usa riferimenti normativi CORRETTI
- NON generare dati inventati
- Distingui sempre tra misurato e stimato
- Mantieni tono professionale e tecnico
