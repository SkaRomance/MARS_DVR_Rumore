# MAPPA REQUISITI NORMATIVI COMPLETA - D.Lgs. 81/2008 RUMORE

**Versione:** 1.0  
**Data:** Aprile 2026  
**Fonte:** D.Lgs. 9 aprile 2008, n. 81 - Titolo VIII Capo II - Artt. 181-196  
**Riferimento europeo:** Direttiva 2003/10/CE  
**Riferimento tecnico:** ISO 9612:2009, UNI 11347:2015

---

## STRUTTURA NORMATIVA

### D.Lgs. 81/2008 - TITOLO VIII - Capo II - RUMORE

```
TITOLO VIII - Misure di protezione da agenti fisici
├── CAPO I - Disposizioni generali (Artt. 179-180)
├── CAPO II - Protezione dal rumore (Artt. 181-196) ← OGGETTO ANALISI
├── CAPO III - Vibrazioni (Artt. 197-210)
├── CAPO IV - Campi elettromagnetici (Artt. 211-222)
├── CAPO V - Radiazioni ottiche artificiali (Artt. 223-235)
└── CAPO VI - Microclima e aerazione (Artt. 236-239)
```

---

## ARTICOLI NORMATIVI DETTAGLIATI

### ART. 181 - DEFINIZIONI

**Stato normativo:** Definisce i termini tecnici utilizzati nel Capo II.

**Definizioni chiave:**

| Termine | Definizione | Implicazione operativa |
|---------|-------------|------------------------|
| **Rumore** | Qualsiasi suono che può determinare perdita dell'udito o effetti nocivi sulla salute | Base concettuale per valutazione |
| **Esposizione giornaliera personale al rumore (LEX,8h)** | Livello sonoro continuo equivalente ponderato A che produce la stessa energia sonora dell'esposizione effettiva durante una giornata lavorativa di 8 ore | Parametro fondamentale calcolo |
| **Esposizione settimanale personale al rumore (LEX,w)** | Esposizione normalizzata a 40 ore settimanali | Per orari variabili |
| **Livello di picco (LpC,peak)** | Massimo livello sonoro istantaneo ponderato C | Per rumori impulsivi |
| **Valore limite di esposizione** | LEX,8h = 87 dB(A) o LpC,peak = 140 dB(C) | Soglia non superabile |
| **Valore d'azione superiore** | LEX,8h = 85 dB(A) o LpC,peak = 137 dB(C) | Obblighi rafforzati |
| **Valore d'azione inferiore** | LEX,8h = 80 dB(A) o LpC,peak = 135 dB(C) | Primi obblighi |

**Requisiti implementazione:**

- Il sistema deve calcolare e gestire LEX,8h
- Deve gestire opzionalmente LEX,w per orari variabili
- Deve calcolare LpC,peak per rumori impulsivi
- Deve applicare le tre soglie normative correttamente

---

### ART. 182 - CAMPO DI APPLICAZIONE

**Stato normativo:** Definisce i settori inclusi ed esclusi.

**Ambito di applicazione:**

**INCLUSI:**
- Tutti i settori aventi esposizione rumore
- Tutti i lavoratori (dipendenti, interinali, etc.)
- Tutti i luoghi di lavoro

**ESCLUSIONI:**

| Esclusione | Specificazione | Gestione |
|------------|----------------|----------|
| Forze armate | Operazioni militari | Documentare esclusione |
| Servizi protezione civile | Emergenze | Documentare esclusione |
| Acustica non occupazionale | Rumore ambientale | Non soggetto |

**Requisiti implementazione:**

- Sistema deve permettere di documentare esclusioni
- Sistema deve applicare a tutti i settori ATECO con rumore
- Sistema deve gestire diversi tipi di rapporto di lavoro

---

### ART. 183 - VALORI LIMITE E VALORI D'AZIONE

**Stato normativo:** Fissa le soglie operative obbligatorie.

#### SOGLIE PRINCIPALI

| Grandezza | Valore | Cosa succede |
|-----------|--------|--------------|
| **Valore azione inferiore** | LEX,8h ≥ 80 dB(A) | Inizio obblighi soft |
| | LpC,peak ≥ 135 dB(C) | |
| **Valore azione superiore** | LEX,8h ≥ 85 dB(A) | Obblighi rafforzati |
| | LpC,peak ≥ 137 dB(C) | |
| **Valore limite** | LEX,8h > 87 dB(A) | DIVIETO |
| | LpC,peak > 140 dB(C) | |

#### SOGLIE SETTIMANALI (se applicabile)

| Grandezza | Valore |
|-----------|--------|
| Valore azione inferiore settimanale | LEX,w = 80 dB(A) |
| Valore azione superiore settimanale | LEX,w = 85 dB(A) |
| Valore limite settimanale | LEX,w = 87 dB(A) |

#### APPLICAZIONE SOGLIE

**Regola normativa esatta:**

```
SE LEX,8h < 80 dB(A) AND LpC,peak < 135 dB(C):
    → Nessun obbligo specifico rumore
    → Valutazione generica (Art. 17)

SE LEX,8h ≥ 80 dB(A) OR LpC,peak ≥ 135 dB(C):
    → Valore azione inferiore
    → Obblighi: informazione, formazione, DPI su richiesta, sorveglianza su richiesta

SE LEX,8h ≥ 85 dB(A) OR LpC,peak ≥ 137 dB(C):
    → Valore azione superiore
    → Obblighi: tutti i precedenti + DPI obbligatori, sorveglianza obbligatoria, elenco esposti

SE LEX,8h > 87 dB(A) OR LpC,peak > 140 dB(C):
    → Valore limite superato
    → DIVIETO, azioni immediate obbligatorie

NOTA: I valori sono riferiti all'esposizione effetiva del lavoratore.
La valuta del rumore incidente deve considerare l'attenuazione dei DPI uditivi.
```

**Requisiti implementazione:**

- Calcolo automatico fascia di esposizione
- Alert automatici per superamento soglie
- Trigger automatico per obblighi per fascia
- Gestione separata esposizione con/senza DPI

---

### ART. 184 - VALUTAZIONE DEL RISCHIO

**Stato normativo:** OBBLIGO FONDAMENTALE di valutazione del rischio rumore.

#### OBBLIGO PRIMARIO

> **Art. 184, c. 1:** "Il datore di lavoro effettua la valutazione del rischio da esposizione dei lavoratori al rumore"

#### CONTENUTI OBBLIGATORI DELLA VALUTAZIONE

**Art. 184, c. 2 - Contenuti minimi:**

| # | Contenuto | Lettera | Implementazione |
|---|-----------|---------|-----------------|
| 1 | Identificazione sorgenti di rumore | lett. a) | noise_source_catalog, machine_asset |
| 2 | Identificazione lavoratori esposti | lett. b) | worker_exposure_registry (MANCANTE) |
| 3 | Esposizione giornaliera personale (LEX,8h) | lett. c) | noise_assessment_result.lex8h |
| 4 | Esposizione settimanale (se significativa) | lett. c) | NON IMPLEMENTATO |
| 5 | Valori di picco | lett. d) | noise_assessment_result.peak_value |
| 6 | Effetti sulla salute | lett. e) | medical_surveillance (MANCANTE) |
| 7 | Interazione con altri agenti | lett. f) | other_agents_evaluation (MANCANTE) |
| 8 | Informazioni fabbricanti | lett. g) | machine_asset (parziale) |
| 9 | Esistenza DPI adeguate | lett. h) | dpi_hearing_protection (MANCANTE) |
| 10 | Estensione oltre 8h | lett. i) | durata espositiva (parziale) |
| 11 | Risultati sorveglianza sanitaria | lett. l) | medical_surveillance (MANCANTE) |
| 12 | Esposizione rumori impulsivi | lett. m) | noise_type (MANCANTE) |

#### DOCUMENTAZIONE OBBLIGATORIA

**Art. 184, c. 3 - Documentazione:**

| # | Documento | Contenuto | Implementazione |
|---|-----------|-----------|-----------------|
| 1 | Relazione tecnica | Metodo, strumenti, risultati | methodology_note (parziale) |
| 2 | Identificazione sorgenti | Elenco sorgenti | noise_source_catalog |
| 3 | Identificazione mansioni | Elenco mansioni | job_role |
| 4 | Livelli esposizione | LEX,8h, peak | noise_assessment_result |
| 5 | Misure prevenzione | Piano azioni | mitigation_action |
| 6 | Dati metrologici | Strumenti, calibrazione | measurement_session (parziale) |

#### QUANDO MISURAZIONE OBBLIGATORIA

**Art. 184, c. 4:**

| Criterio | Obbligo |
|----------|---------|
| Superamento valori azione inferiori | MISURA OBBLIGATORIA |
| Assenza dati pregressi affidabili | MISURA OBBLIGATORIA |
| Variazione processi significativa | MISURA OBBLIGATORIA |
| Richiesta RLS | MISURA OBBLIGATORIA |
| Indicazione MC | MISURA OBBLIGATORIA |
| Nuove sorgenti di rumore | MISURA OBBLIGATORIA |

#### AGGIORNAMENTO VALUTAZIONE

**Art. 184, c. 5:**

| Evento | Aggiornamento |
|--------|---------------|
| Modifiche processi | OBBLIGATORIO |
| Nuove macchine | OBBLIGATORIO |
| Superamento soglie | OBBLIGATORIO |
| Infortuni o malattie | OBBLIGATORIO |
| Richiesta RLS | OBBLIGATORIO |
| Periodico | Consigliato ogni 2 anni |

**Requisiti implementazione:**

- Data valutazione obbligatoria (assessment_date) - MANCANTE
- Data prossimo aggiornamento - MANCANTE
- Metodo stima/misura (methodology_type) - MANCANTE
- Strumentazione completa - MANCANTE
- Incertezza misura - MANCANTE
- Giustificazione metodo - PARZIALE

---

### ART. 185 - MISURE DI PREVENZIONE E PROTEZIONE

**Stato normativo:** OBBLIGO di adottare misure di riduzione del rumore.

#### MISURE TECNICHE

**Art. 185, c. 1, lett. a):**

| Misure tecniche | Descrizione |
|-----------------|-------------|
| Eliminazione alla fonte | Sostituzione macchine, processi meno rumorosi |
| Riduzione alla fonte | silenziatori, barriere, fonoassorbenti |
| Manutenzione | Programma manutenzione macchine |
| Cabine acustiche | Isolamento operatore |

#### MISURE ORGANIZZATIVE

**Art. 185, c. 1, lett. b):**

| Misure organizzative | Descrizione |
|-----------------------|-------------|
| Riduzione tempi esposizione | Rotazione mansioni |
| Distacco esposizione | Limitazione ore in zona rumorosa |
| Orari differenziati | Evitare sovrapposizione fonte |

#### MISURE INDIVIDUALI

**Art. 185, c. 1, lett. c):**

- DPI uditivi (vedi Art. 192)

#### OBBLIGHI PER FASCIA

**Fascia 1: LEX,8h ≥ 80 dB(A) [Valore azione inferiore]**

| Obbligo | Descrizione |
|---------|-------------|
| Informazione | Su rischi, misure, valori limite |
| Formazione | Specifica sul rumore |
| DPI su richiesta | Messi a disposizione |

**Fascia 2: LEX,8h ≥ 85 dB(A) [Valore azione superiore]**

| Obbligo | Descrizione |
|---------|-------------|
| Tutti i precedenti | Più: |
| DPI OBBLIGATORI | Uso obbligatorio |
| Sorveglianza sanitaria | Obbligatoria |
| Elenco esposti | Registro Art. 193 |
| Programma riduzione | Piano azioni |
| Segnaletica | Zone rumorose |

**Fascia 3: LEX,8h > 87 dB(A) [Valore limite superato]**

| Obbligo | Descrizione |
|---------|-------------|
| DIVIETO esposizione | Interrazione immediata |
| Indagine cause | Relazione tecnica |
| Misure correttive | Piano immediato |
| Sorveglianza intensificata | Controlli frequenti |
| Dermoga temporale | Max 6 mesi (con autorizzazione) |

#### DOCUMENTAZIONE MISURE

**Contenuti obbligatori piano azioni:**

| Contenuto | Implementazione |
|-----------|-----------------|
| Tipo azione | mitigation_action.type |
| Descrizione | mitigation_action.description |
| Priorità | mitigation_action.priority |
| Responsabile | mitigation_action.owner |
| Scadenza | mitigation_action.due_date |
| Effetto atteso (dB) | MANCANTE |
| Stato attuazione | MANCANTE |
| Verifica efficacia | MANCANTE |

**Requisiti implementazione:**

- Classificazione azioni (tecnica/organizzativa/DPI)
- Stima riduzione in dB
- Tracciamento stato attuazione
- Verifica efficacia misure
- Programma temporale

---

### ART. 186 - SORVEGLIANZA SANITARIA

**Stato normativo:** OBBLIGO di sorveglianza sanitaria per esposti.

#### OBBLIGHI PER FASCIA

| Fascia esposizione | Obbligo sorveglianza |
|--------------------|----------------------|
| LEX,8h < 80 dB(A) | Nessun obbligo |
| LEX,8h ≥ 80 dB(A) | Su richiesta lavoratore |
| LEX,8h ≥ 85 dB(A) | **OBBLIGATORIO** |
| Superamento limite | **OBBLIGATORIO + intensificata** |

#### TIPI DI VISITA

| Tipo visita | Quando | Obbligo |
|-------------|-------|---------|
| Preassuntiva | Prima dell'esposizione | OBBLIGATORIO |
| Periodica | Secondo MC | OBBLIGATORIO (≥ 85 dB) |
| Su richiesta | Lavoratore | OBBLIGATORIO |
| Alla cessazione | Fine esposizione | Su richiesta |

#### ESAMI OBBLIGATORI

**Art. 186, c. 3:**

| Esame | Obbligo | Periodicità |
|-------|---------|-------------|
| Audiometria tonale | OBBLIGATORIO | Annuale o biennale (MC decide) |
| Audiometria vocale | Se necessario | MC decide |
| Altri esami | Se necessari | MC decide |

#### CONTENUTO GIUDIZIO

**Art. 186, c. 4:**

| Contenuto | Implementazione |
|-----------|-----------------|
| Giudizio idoneità | medical_surveillance.medical_judgment (MANCANTE) |
| Prescrizioni | medical_surveillance.limitations (MANCANTE) |
| Periodicità | medical_surveillance.next_exam_date (MANCANTE) |
| Riserve privacy | Note |

#### PERIODICITÀ CONTROLLI

| Situazione | Periodicità minima |
|------------|--------------------|
| Esposizione ≥ 85 dB(A) | Annuale (MC può estendere a 2 anni) |
| Superamento limite | Annuale o semestrale |
| Sospetto danno | Immediata |

#### REGISTRAZIONE

**Art. 186, c. 5:**

- Giudizio di idoneità comunicato al lavoratore
- Copia nel fascicolo sanitario
- Riservatezza sui dati sanitari

**Requisiti implementazione:**

- Entità medical_surveillance (MANCANTE)
- Fascicolo sanitario digitale
- Giudizio idoneità
- Periodicità controlli
- Collegamento a worker_exposure_registry

---

### ART. 187 - INFORMAZIONE E FORMAZIONE

**Stato normativo:** OBBLIGO di informazione e formazione specifica.

#### CONTENUTI OBBLIGATORI

**Art. 187, c. 1:**

| # | Contenuto | Dettaglio |
|---|-----------|-----------|
| 1 | Natura del rischio rumore | Effetti su udito e salute |
| 2 | Misure adottate | Prevenzione, protezione |
| 3 | Valori limite e azione | Soglie normative |
| 4 | Esposizione specifica | Livelli per mansione |
| 5 | Uso corretto DPI | Modalità, manutenzione |
| 6 | Ruolo sorveglianza | Funzioni MC |
| 7 | Risultati valutazione | Livelli misurati |
| 8 | Procedure segnalazione | Come segnalare problemi |

#### WHEN FORMAZIONE OBBLIGATORIA

| Occasione | Obbligo |
|-----------|---------|
| Assunzione | OBBLIGATORIO |
| Cambio mansione | OBBLIGATORIO |
| Nuovo rischio | OBBLIGATORIO |
| Aggiornamento | Periodico (consigliato annuale) |

#### DOCUMENTAZIONE

| Documento | Conservazione |
|-----------|---------------|
| Programma formazione | 10 anni |
| Registro presenze | 10 anni |
| Materiale didattico | 10 anni |
| Attestato frequenza | 10 anni |

**Requisiti implementazione:**

- Entità training_record (MANCANTE)
- Contenuti formazione strutturati
- Registro presenze
- Attestati
- Collegamento a lavoratori

---

### ART. 188 - CONSULTAZIONE DEI LAVORATORI

**Stato normativo:** OBBLIGO di consultare il RLS.

#### CONTENUTO CONSULTAZIONE

| Argomento | Quando |
|-----------|--------|
| Valutazione rischio | Prima di approvazione |
| Misure prevenzione | Prima di attuazione |
| Risultati sorveglianza | Aggregati anonimi |
| Programma riduzione | Prima di attuazione |

#### DOCUMENTAZIONE

| Documento | Contenuto |
|-----------|-----------|
| Data consultazione | Quando |
| Argomenti discussi | Cosa |
| Osservazioni RLS | Pareri |
| Firma RLS | Accordo |
| Firma DL | Convalida |

**Requisiti implementazione:**

- Entità rls_consultation (MANCANTE)
- Verbale consultazione
- Osservazioni RLS
- Firme digitali

---

### ART. 189 - SEGNALLETICA

**Stato normativo:** OBBLIGO di identificare e segnalare zone rumorose.

#### OBBLIGHI

| Zone | Obbligo |
|------|---------|
| LEX,8h ≥ 80 dB(A) | Cartello informativo |
| LEX,8h ≥ 85 dB(A) | Divieto accesso senza DPI |
| Superamento limite | Segnale pericolo + divieto |

#### CONTENUTO CARTELLI

| Contenuto | Esempio |
|-----------|---------|
| Livello rumore presente | "Zona rumorosa - 88 dB(A)" |
| Obblighi | "Obbligo DPI uditivi" |
| Rischi | "Pericolo per l'udito" |
| Responsabile | Nome referente |

**Requisiti implementazione:**

- Entità signage (MANCANTE)
- Zone rumorose identificate
- Livelli per zona
- DPI richiesti
- Controllo cartelli

---

### ART. 190 - REGISTRO CASI DI IPOACUSIA

**Stato normativo:** Mantenuto ma reinterpretato dopo sentenza Corte Costituzionale.

**NOTA IMPORTANTE:**

Dopo sentenza Corte Costituzionale n. 300 del 2013, il registro di cui all'Art. 190 è stato sostituito dal registro di cui all'Art. 193. Il registro deve contenere tutti i lavoratori esposti, non solo i casi di ipoacusia.

**Contenuto:**
- Dati lavoratori esposti
- Livelli esposizione
- DPI forniti
- Visite mediche
- Giudizi idoneità

---

### ART. 191 - (Abrogato)

**Stato normativo:** Articolo abrogato.

---

### ART. 192 - DPI UDITIVI

**Stato normativo:** OBBLIGO di DPI uditivi adeguati.

#### REQUISITI DPI

| Requisito | Normativa | Verifica |
|-----------|-----------|----------|
| Marcatura CE | Reg. UE 2016/425 | Obbligatoria |
| Categoria III | D.Lgs. 81/08 Art. 76 | Obbligatoria |
| Certificato conformità | UNI EN 352 | Obbligatoria |
| Attenuazione dichiarata | UNI EN ISO 4869-1 | Obbligatoria |

#### OBBLIGHI PER FASCIA

**Fascia 1: LEX,8h ≥ 80 dB(A)**

| Obbligo | Art. 192, c. 3 |
|---------|----------------|
| DPI disponibili | Su richiesta |
| Informazione | Su uso e necessità |
| Formazione | Su uso corretto |
| Nessun obbligo uso | Facoltativo |

**Fascia 2: LEX,8h ≥ 85 dB(A)**

| Obbligo | Art. 192, c. 4 |
|---------|----------------|
| DPI OBBLIGATORI | Uso non facoltativo |
| Controllo utilizzo | Verifica DL |
| DPI idonei | Attenuazione suff. |

#### PROCEDURA SCELTA DPI

**Art. 192, c. 5:**

| Passo | Azione | Formula |
|-------|--------|---------|
| 1 | Misurare esposizione | LEX,8h |
| 2 | Definire obiettivo | LEX,8h_con_DPI < 80 dB(A) |
| 3 | Calcolare attenuazione necessaria | Att_necessaria = LEX,8h - 80 + margine |
| 4 | Selezionare DPI | SNR ≥ Att_necessaria |
| 5 | Provare individualmente | Comfort, sigillamento |
| 6 | Formare sul uso | Modalità, manutenzione |

#### CALCOLO ATTENUAZIONE

**Metodo SNR (Single Number Rating):**

```
LEX,8h_DPI = LEX,8h - SNR + margine_sicurezza

Dove:
- SNR = attenuazione dichiarata dal costruttore
- margine_sicurezza = almeno 5 dB (raccomandato)
```

**Metodo MIRE (Microphone In Real Ear):**

```
Attenuazione_effettiva = MIRE - 2σ

Dove:
- MIRE = misura soggettiva
- σ = deviazione standard
```

#### CONTROLLO EFFICACIA

| Verifica | Periodicità |
|----------|-------------|
| Stato DPI | Ogni uso |
| Sostituzione | Secondo fabbricante |
| Efficacia | Se cambiano condizioni |

**Requisiti implementazione:**

- Entità dpi_hearing_protection (MANCANTE)
- Calcolo LEX,8h efficace con DPI
- Attenuazione per tipo DPI
- SNR, H, M, L
- Registro consegna
- Prova individuale

---

### ART. 193 - ELENCO DEI LAVORATORI ESPOSTI

**Stato normativo:** OBBLIGO di registro esposti.

#### CONTENUTO OBBLIGATORIO

**Art. 193, c. 1:**

| # | Contenuto | Implementazione |
|---|-----------|-----------------|
| 1 | Nome | worker_exposure_registry.worker_name (MANCANTE) |
| 2 | Cognome | worker_exposure_registry.worker_surname (MANCANTE) |
| 3 | Codice fiscale | worker_exposure_registry.worker_fiscal_code (MANCANTE) |
| 4 | Mansione | worker_exposure_registry.job_role_id |
| 5 | Livello esposizione | worker_exposure_registry.lex8h_measured |
| 6 | Superamento valori azione | worker_exposure_registry.threshold_band |
| 7 | Data elaborazione | worker_exposure_registry.exposure_start_date |
| 8 | Firma datore lavoro | MANCANTE |

#### CONSERVAZIONE

**Periodo:** 10 anni dalla cessazione dell'esposizione

#### ACCESSO

| Soggetto | Diritto |
|----------|---------|
| Organo vigilanza | Accesso completo |
| ASL competente | Accesso completo |
| INAIL | Accesso completo |
| RLS | Accesso completo |
| Lavoratore | Propri dati aggregati |

**Requisiti implementazione:**

- Entità worker_exposure_registry (MANCANTE)
- Dati anagrafici completi
- Livelli esposizione
- DPI forniti
- Visite mediche
- Periodo esposizione

---

### ART. 194 - DICHIARAZIONE DI CONFORMITÀ

**Stato normativo:** Informazioni obbligatorie sui macchinari.

#### REQUISITI INFORMAZIONI

**D.Lgs. 17/2010 (Direttiva Macchine):**

| Informazione | Fonte | Obbligo |
|---------------|-------|---------|
| Livello potenza sonora (LWA) | Dichiarazione conformità | Obbligatorio |
| Livello pressione sonora (LpA) | Dichiarazione conformità | Se > 70 dB(A) |
| Picco sonoro | Dichiarazione conformità | Se > 130 dB(C) |

#### USO NELLA VALUTAZIONE

**I dati dichiarati sono:**
- Punto di partenza per stima
- **NON sostituiscono** la misurazione in campo
- Da verificare con condizioni operative reali

**Requisiti implementazione:**

- Campo per livelli dichiarati in machine_asset
- Flag per origine dato (dichiarato vs misurato)
- Verifica discrepanze dichiarato/misurato

---

### ART. 195 - SANZIONI PER IL DATORE DI LAVORO

**Stato normativo:** Sanzioni penali per violazioni.

#### SANZIONI PRINCIPALI

| Violazione | Sanzione |
|------------|----------|
| Mancata valutazione | Arresto 3-6 mesi o multa 2.740-7.014€ |
| Valutazione incompleta | Arresto 3-6 mesi o multa 2.740-7.014€ |
| Mancata adozione misure | Arresto 3-6 mesi o multa 2.740-7.014€ |
| Mancata sorveglianza | Arresto 3-6 mesi o multa 2.740-7.014€ |
| Mancata formazione | Arresto fino 6 mesi o multa 2.740-7.014€ |
| Mancato registro esposti | Multa 546-1.947€ |
| Mancata consultazione RLS | Multa 546-1.947€ |

---

### ART. 196 - SANZIONI PER I DIRIGENTI

**Stato normativo:** Sanzioni per dirigenti.

| Violazione | Sanzione |
|------------|----------|
| Stesse del DL | Multa 2.740-7.014€ |

---

## ISO 9612:2009 - REQUISITI TECNICI

### STRATEGIE DI MISURA

**Tre strategie approvate:**

| Strategia | Descrizione | Quando usare |
|-----------|-------------|--------------|
| **Task-based** | Misura per mansione/fase | Lavori ben definiti |
| **Job-based** | Misura per lavoratore | Variabilità alta |
| **Full-day** | Misura giornata intera | Variabilità molto alta |

### REQUISITI STRUMENTAZIONE

| Requisito | Specificazione |
|-----------|----------------|
| Classe fonometro | 1 o 2 (UNI EN 61672-1) |
| Calibrazione | Pre e post misura |
| Deviazione max | ± 0,5 dB |
| Taratura | Certificato < 2 anni |

### CALCOLO INCERTEZZA

**Componenti:**

| Componente | Descrizione |
|-------------|-------------|
| u_misura | Incertezza strumento |
| u_posizione | Variabilità posizione |
| u_campionamento | Variabilità temporale |
| u_strategia | Incertezza metodo |

**Formula:**

```
U = k · √(u_misura² + u_posizione² + u_campionamento² + u_strategia²)

Dove k = 2 (livello confidenza 95%)
```

**Risultato:** LEX,8h ± U

---

## RIEPILOGO REQUISITI IMPLEMENTAZIONE

### ENTITÀ MANCANTI CRITICHE

| # | Entità | Articolo | Priorità |
|---|--------|----------|----------|
| 1 | worker_exposure_registry | Art. 193 | **BLOCCANTE** |
| 2 | medical_surveillance | Art. 186 | **BLOCCANTE** |
| 3 | dpi_hearing_protection | Art. 192 | **BLOCCANTE** |
| 4 | training_record | Art. 187 | **BLOCCANTE** |
| 5 | rls_consultation | Art. 188 | **BLOCCANTE** |
| 6 | signage | Art. 189 | **ALTA** |

### CAMPI MANCANTI CRITICI

| # | Entità | Campo | Articolo | Priorità |
|---|--------|-------|----------|----------|
| 1 | noise_assessment | assessment_date | Art. 184 | **BLOCCANTE** |
| 2 | noise_assessment | validity_period | Art. 184 | **ALTA** |
| 3 | noise_assessment | measurement_uncertainty | ISO 9612 | **BLOCCANTE** |
| 4 | noise_assessment | instrument_class | ISO 9612 | **BLOCCANTE** |
| 5 | role_phase_exposure | laeq_uncertainty | ISO 9612 | **BLOCCANTE** |
| 6 | noise_assessment_result | lex8h_uncertainty | ISO 9612 | **BLOCCANTE** |
| 7 | noise_assessment_result | lex8h_effective | Art. 192 | **BLOCCANTE** |

### FUNZIONALITÀ MANCANTI CRITICHE

| # | Funzionalità | Riferimento | Priorità |
|---|--------------|-------------|----------|
| 1 | Calcolo incertezza | ISO 9612 | **BLOCCANTE** |
| 2 | Calcolo LEX,8h con DPI | Art. 192 | **BLOCCANTE** |
| 3 | Gestione esposizione settimanale | ISO 9612 | **ALTA** |
| 4 | Gestione rumore impulsivo | Art. 184 | **ALTA** |
| 5 | Gestione interazione agenti | Art. 184 | **ALTA** |

---

**Documento elaborato:** Aprile 2026  
**Versione:** 1.0  
**Riferimenti:** D.Lgs. 81/2008, Direttiva 2003/10/CE, ISO 9612:2009, UNI 11347:2015