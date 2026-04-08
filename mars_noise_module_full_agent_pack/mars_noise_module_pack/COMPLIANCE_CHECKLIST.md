# CHECKLIST CONFORMITÀ NORMATIVA - MODULO DVR RUMORE

**Versione:** 1.0  
**Data:** Aprile 2026  
**Obiettivo:** Verifica conformità D.Lgs. 81/2008 Titolo VIII Capo II

---

## STATO ATTUALE vs REQUISITI NORMATIVI

### LEGENDA
- ✅ **CONFORME** - Requisito implementato correttamente
- ⚠️ **PARZIALE** - Requisito implementato parzialmente
- ❌ **MANCANTE** - Requisito non implementato
- 🔴 **CRITICO** - Requisito obbligatorio per legge

---

## 1. VALUTAZIONE DEL RISCHIO - Art. 184

### 1.1 Contenuti Documento Valutazione

| # | Requisito | Articolo | Stato | Note |
|---|-----------|----------|-------|------|
| 1.1.1 | Identificazione sorgenti rumore | Art. 184, c. 2, lett. a) | ✅ | Presente in noise_source_catalog |
| 1.1.2 | Identificazione lavoratori esposti | Art. 184, c. 2, lett. b) | ⚠️ | Mancano dati anagrafici dettagliati |
| 1.1.3 | Esposizione giornaliera LEX,8h | Art. 184, c. 2, lett. c) | ✅ | Calcolato in noise_assessment_result |
| 1.1.4 | Esposizione settimanale (se variabile) | Art. 184, c. 2, lett. c) | ❌ | Non implementato |
| 1.1.5 | Valori di picco LpC,peak | Art. 184, c. 2, lett. d) | ⚠️ | Presente ma senza incertezza |
| 1.1.6 | Effetti sulla salute | Art. 184, c. 2, lett. e) | ⚠️ | Non strutturato nel data model |
| 1.1.7 | Interazione altri agenti | Art. 184, c. 2, lett. f) | ❌ | Non implementato |
| 1.1.8 | Informazioni fabbricanti | Art. 184, c. 2, lett. g) | ⚠️ | Parziale in machine_asset |
| 1.1.9 | Esistenza DPI adeguate | Art. 184, c. 2, lett. h) | ❌ | Entità DPI mancante |
| 1.1.10 | Estensione esposizione oltre 8h | Art. 184, c. 2, lett. i) | ⚠️ | Durata presente ma non normalizzazione |
| 1.1.11 | Risultati sorveglianza sanitaria | Art. 184, c. 2, lett. l) | ❌ | Entità medical_surveillance mancante |
| 1.1.12 | Esposizione rumori impulsivi | Art. 184, c. 2, lett. m) | ⚠️ | Non gestito esplicitamente |

**CRITICITÀ:** 4 requisiti mancanti, 6 parziali su 12 totali

---

### 1.2 Metodologia di Valutazione

| # | Requisito | Riferimento | Stato | Note |
|---|-----------|-------------|-------|------|
| 1.2.1 | Metodo descritto (stima/misura) | Art. 184, c. 4 | ✅ | value_origin presente |
| 1.2.2 | Giustificazione metodo | Art. 184, c. 4 | ⚠️ | methodology_note parziale |
| 1.2.3 | Strumentazione usata | ISO 9612 | ⚠️ | Campi presenti ma incompleti |
| 1.2.4 | Classe strumento (1 o 2) | ISO 9612 | ❌ | Non specificato |
| 1.2.5 | Calibrazione pre/post | ISO 9612 | ⚠️ | calibration_info presente ma generico |
| 1.2.6 | Incertezza di misura | ISO 9612 | ❌ | Non calcolato/stimato |
| 1.2.7 | Condizioni misura | ISO 9612 | ❌ | Non documentate |
| 1.2.8 | Strategia misura (job/task/full-day) | ISO 9612 | ❌ | Non specificato |

**CRITICITÀ:** 4 requisiti mancanti su 8 totali

---

### 1.3 Documentazione

| # | Requisito | Articolo | Stato | Note |
|---|-----------|----------|-------|------|
| 1.3.1 | Data valutazione | Art. 184, c. 3 | ⚠️ | created_by ma non assessment_date |
| 1.3.2 | Versione documento | Art. 184, c. 3 | ✅ | version presente |
| 1.3.3 | Stato (bozza/approvato) | Art. 184, c. 3 | ✅ | status presente |
| 1.3.4 | Validità temporale | Art. 184 | ❌ | Mancano date inizio/fine validità |
| 1.3.5 | Approvazione | Art. 184, c. 3 | ✅ | approved_by presente |
| 1.3.6 | Aggiornamento programmato | Art. 184 | ❌ | Non gestito |

**CRITICITÀ:** 2 requisiti mancanti su 6 totali

---

## 2. MISURE DI PREVENZIONE - Art. 185

### 2.1 Azioni Correttive

| # | Requisito | Articolo | Stato | Note |
|---|-----------|----------|-------|------|
| 2.1.1 | Programma misure riduzione | Art. 185, c. 1, lett. a) | ⚠️ | mitigation_action presente ma incompleto |
| 2.1.2 | Misura tecnica | Art. 185, c. 1, lett. a) | ⚠️ | type presente ma non categorizzato |
| 2.1.3 | Misura organizzativa | Art. 185, c. 1, lett. b) | ⚠️ | Non esplicito |
| 2.1.4 | Effetto atteso (riduzione dB) | Art. 185 | ❌ | Non gestito |
| 2.1.5 | Tempistiche | Art. 185 | ✅ | due_date presente |
| 2.1.6 | Responsabile | Art. 185 | ✅ | owner presente |
| 2.1.7 | Verifica efficacia | Art. 185, c. 2 | ❌ | Non gestito |

**CRITICITÀ:** 2 requisiti mancanti, 4 parziali su 7 totali

---

### 2.2 Gestione Superamento Valori

| # | Requisito | Articolo | Stato | Note |
|---|-----------|----------|-------|------|
| 2.2.1 | Alert superamento azione inferiore (80 dB) | Art. 183 | ✅ | threshold_band presente |
| 2.2.2 | Alert superamento azione superiore (85 dB) | Art. 183 | ✅ | threshold_band presente |
| 2.2.3 | Alert superamento limite (87 dB) | Art. 183 | ✅ | threshold_band presente |
| 2.2.4 | Azioni automatiche per superamento | Art. 185, c. 2 | ❌ | Non automatizzato |
| 2.2.5 | Tracciamento piano azioni | Art. 185 | ⚠️ | Parziale |

**CRITICITÀ:** 1 requisito mancante su 5 totali

---

## 3. SORVEGLIANZA SANITARIA - Art. 186

### 3.1 Gestione Medica

| # | Requisito | Articolo | Stato | Note |
|---|-----------|----------|-------|------|
| 3.1.1 **🔴** | Elenco lavoratori esposti | Art. 186, c. 1 | ❌ | Entità worker_exposure_registry MANCANTE |
| 3.1.2 **🔴** | Visita preassuntiva | Art. 186, c. 2 | ❌ | Entità medical_surveillance MANCANTE |
| 3.1.3 **🔴** | Visita periodica | Art. 186, c. 2 | ❌ | Entità medical_surveillance MANCANTE |
| 3.1.4 | Visita su richiesta | Art. 186, c. 2 | ❌ | Entità medical_surveillance MANCANTE |
| 3.1.5 **🔴** | Esame audiometrico | Art. 186, c. 3 | ❌ | Non gestito |
| 3.1.6 **🔴** | Giudizio idoneità | Art. 186, c. 4 | ❌ | Non gestito |
| 3.1.7 | Periodicità controlli | Art. 186 | ❌ | Non gestito |
| 3.1.8 | Fascia esposizione ≥ 80 dB(A) | Art. 186 | ⚠️ | medical_surveillance_flag presente |
| 3.1.9 | Fascia esposizione ≥ 85 dB(A) | Art. 186 | ⚠️ | medical_surveillance_flag presente |

**CRITICITÀ:**🔴 **8 requisiti su 9 MANCANTI - ENTITÀ CRITICA DA IMPLEMENTARE**

---

### 3.2 Dati Medici

| # | Requisito | Articolo | Stato | Note |
|---|-----------|----------|-------|------|
| 3.2.1 | Data visita | Art. 186 | ❌ | Non gestito |
| 3.2.2 | Tipo visita | Art. 186 | ❌ | Non gestito |
| 3.2.3 | Esito audiometria | Art. 186 | ❌ | Non gestito |
| 3.2.4 | Giudizio idoneità | Art. 186 | ❌ | Non gestito |
| 3.2.5 | Prescrizioni | Art. 186 | ❌ | Non gestito |
| 3.2.6 | Prossima visita | Art. 186 | ❌ | Non gestito |
| 3.2.7 | Medico competente | Art. 186 | ❌ | Non collegato |

**CRITICITÀ:**🔴 ** tutti i 7 requisiti MANCANTI**

---

## 4. INFORMAZIONE E FORMAZIONE - Art. 187

### 4.1 Contenuti Formazione

| # | Requisito | Articolo | Stato | Note |
|---|-----------|----------|-------|------|
| 4.1.1 | Natura rischio rumore | Art. 187, c. 1 | ⚠️ | Non strutturato |
| 4.1.2 | Misure adottate | Art. 187, c. 1 | ⚠️ | Non strutturato |
| 4.1.3 | Valori limite | Art. 187, c. 1 | ⚠️ | Non strutturato |
| 4.1.4 | Esposizione specifica | Art. 187, c. 1 | ⚠️ | Non strutturato |
| 4.1.5 | Uso corretto DPI | Art. 187, c. 1 | ❌ | Entità DPI mancante |
| 4.1.6 | Ruolo sorveglianza sanitaria | Art. 187, c. 1 | ❌ | Entità medica mancante |
| 4.1.7 | Risultati valutazione | Art. 187, c. 1 | ⚠️ | Presente ma non formalizzato |
| 4.1.8 | Procedure segnalazione | Art. 187, c. 1 | ❌ | Non gestito |

**CRITICITÀ:** 3 requisiti mancanti, 5 parziali su 8 totali

---

### 4.2 Registrazione Formazione

| # | Requisito | Articolo | Stato | Note |
|---|-----------|----------|-------|------|
| 4.2.1 **🔴** | Data formazione | Art. 187 | ❌ | Entità training_record MANCANTE |
| 4.2.2 **🔴** | Registro presenze | Art. 187 | ❌ | Entità training_record MANCANTE |
| 4.2.3 **🔴** | Programma formazione | Art. 187 | ❌ | Non gestito |
| 4.2.4 | Materiale didattico | Art. 187 | ❌ | Non gestito |
| 4.2.5 | Attestato frequenza | Art. 187 | ❌ | Non gestito |
| 4.2.6 | Conservazione 10 anni | Art. 187 | ❌ | Non gestito |

**CRITICITÀ:**🔴 **6 requisiti su 6 MANCANTI - ENTITÀ CRITICA**

---

## 5. DPI UDITIVI - Art. 192

### 5.1 Gestione DPI

| # | Requisito | Articolo | Stato | Note |
|---|-----------|----------|-------|------|
| 5.1.1 **🔴** | Elenco DPI | Art. 192, c. 1 | ❌ | Entità dpi_hearing_protection MANCANTE |
| 5.1.2 **🔴** | Marcatura CE | Art. 192, c. 1 | ❌ | Non gestito |
| 5.1.3 **🔴** | Categoria III | Art. 192, c. 1 | ❌ | Non gestito |
| 5.1.4 | Attenuazione dichiarata (SNR) | Art. 192 | ❌ | Non gestito |
| 5.1.5 **🔴** | Calcolo attenuazione efficace | Art. 192, c. 5 | ❌ | Non implementato |
| 5.1.6 **🔴** | LEX,8h con DPI | Art. 192, c. 5 | ❌ | Non calcolato |
| 5.1.7 | Prova individuale | Art. 192, c. 5 | ❌ | Non gestito |
| 5.1.8 | Registro consegna | Art. 192 | ❌ | Non gestito |

**CRITICITÀ:**🔴 **8 requisiti su 8 MANCANTI - ENTITÀ CRITICA**

---

### 5.2 Obblighi per Fasce

| # | Fascia | Requisito | Articolo | Stato | Note |
|---|--------|-----------|----------|-------|------|
| 5.2.1 | ≥ 80 dB(A) | Dpi disponibili su richiesta | Art. 192, c. 3 | ⚠️ | Flag presente ma non completo |
| 5.2.2 | ≥ 80 dB(A) | Formazione su DPI | Art. 187 | ❌ | Entità training mancante |
| 5.2.3 | ≥ 85 dB(A) | Dpi OBBLIGATORI | Art. 192, c. 4 | ⚠️ | Flag presente ma non completo |
| 5.2.4 | ≥ 85 dB(A) | Verifica utilizzo | Art. 192, c. 4 | ❌ | Non gestito |
| 5.2.5 | > 87 dB(A) | Azioni immediate | Art. 185, c. 2 | ⚠️ | Parziale |

**CRITICITÀ:** 3 requisiti mancanti, 2 parziali su 5 totali

---

## 6. CONSULTAZIONE RLS - Art. 188

| # | Requisito | Articolo | Stato | Note |
|---|-----------|----------|-------|------|
| 6.1 **🔴** | Data consultazione | Art. 188 | ❌ | Entità rls_consultation MANCANTE |
| 6.2 **🔴** | Verbale consultazione | Art. 188 | ❌ | Non gestito |
| 6.3 | Argomenti discussi | Art. 188 | ❌ | Non gestito |
| 6.4 | Osservazioni RLS | Art. 188 | ❌ | Non gestito |
| 6.5 | Firma RLS | Art. 188 | ❌ | Non gestito |
| 6.6 | Firma Datore Lavoro | Art. 188 | ❌ | Non gestito |

**CRITICITÀ:**🔴 **6 requisiti su 6 MANCANTI - ENTITÀ CRITICA**

---

## 7. SEGNALETICA - Art. 189

| # | Requisito | Articolo | Stato | Note |
|---|-----------|----------|-------|------|
| 7.1 **🔴** | Identificazione zone | Art. 189 | ❌ | Entità signage MANCANTE |
| 7.2 | Livello rumore zona | Art. 189 | ❌ | Non gestito |
| 7.3 | Tipo segnaletica | Art. 189 | ❌ | Non gestito |
| 7.4 | DPI richiesti | Art. 189 | ❌ | Non gestito |
| 7.5 | Data installazione | Art. 189 | ❌ | Non gestito |
| 7.6 | Controllo periodico | Art. 189 | ❌ | Non gestito |

**CRITICITÀ:**🔴 **6 requisiti su 6 MANCANTI - ENTITÀ CRITICA**

---

## 8. REGISTRO ESPOSTI - Art. 193

| # | Requisito | Articolo | Stato | Note |
|---|-----------|----------|-------|------|
| 8.1 **🔴** | Nome lavoratore | Art. 193 | ❌ | Entità worker_exposure_registry MANCANTE |
| 8.2 **🔴** | Cognome lavoratore | Art. 193 | ❌ | MANCANTE |
| 8.3 **🔴** | Codice fiscale | Art. 193 | ❌ | MANCANTE |
| 8.4 **🔴** | Mansione | Art. 193 | ❌ | MANCANTE |
| 8.5 **🔴** | Livello esposizione | Art. 193 | ❌ | MANCANTE |
| 8.6 **🔴** | Superamento valori | Art. 193 | ❌ | MANCANTE |
| 8.7 **🔴** | Data elaborazione | Art. 193 | ❌ | MANCANTE |
| 8.8 **🔴** | Firma datore lavoro | Art. 193 | ❌ | MANCANTE |
| 8.9 | Conservazione 10 anni | Art. 193 | ❌ | Non gestito |

**CRITICITÀ:**🔴 **9 requisiti su 9 MANCANTI - ENTITÀ CRITICA**

---

## 9. CALCOLI TECNICI - ISO 9612

### 9.1 Calcolo LEX,8h

| # | Requisito | Riferimento | Stato | Note |
|---|-----------|-------------|-------|------|
| 9.1.1 | Formula corretta | ISO 9612 | ✅ | Specificato in NOISE_CALCULATION_SPEC |
| 9.1.2 | Normalizzazione 8h | ISO 9612 | ⚠️ | Formula presente ma non verifica |
| 9.1.3 | Somma fasi espositive | ISO 9612 | ✅ | Ruolo-fase presente |
| 9.1.4 | Durata per fase | ISO 9612 | ✅ | duration_hours presente |
| 9.1.5 | LAeq per fase | ISO 9612 | ✅ | laeq_value presente |
| 9.1.6 **🔴** | Incertezza misura | ISO 9612 | ❌ | NON GESTITA |
| 9.1.7 | Strategia misura | ISO 9612 | ❌ | Non specificata |
| 9.1.8 | Condizioni operative | ISO 9612 | ❌ | Non documentate |

**CRITICITÀ:** 3 requisiti mancanti su 8 totali

---

### 9.2 Calcolo Picco

| # | Requisito | Riferimento | Stato | Note |
|---|-----------|-------------|-------|------|
| 9.2.1 | Misura LpC,peak | ISO 9612 | ✅ | peak_value presente |
| 9.2.2 | Incertezza picco | ISO 9612 | ❌ | NON GESTITA |
| 9.2.3 | Soglia 135 dB(C) | Art. 183 | ✅ | Verificabile |
| 9.2.4 | Soglia 137 dB(C) | Art. 183 | ✅ | Verificabile |
| 9.2.5 | Soglia 140 dB(C) | Art. 183 | ✅ | Verificabile |

**CRITICITÀ:** 1 requisito mancante su 5 totali

---

### 9.3 Calcolo Esposizione Settimanale

| # | Requisito | Riferimento | Stato | Note |
|---|-----------|-------------|-------|------|
| 9.3.1 | Opzione LEX,w | ISO 9612 | ❌ | NON IMPLEMENTATO |
| 9.3.2 | Gestione orari variabili | Art. 184 | ❌ | NON IMPLEMENTATO |
| 9.3.3 | Confronto soglie settimanali | ISO 9612 | ❌ | NON IMPLEMENTATO |

**CRITICITÀ:** 3 requisiti su 3 MANCANTI

---

## 10. SOGLIE NORMATIVE - Art. 183

### 10.1 Verifica Soglie

| Soglia | Valore | Stato | Note |
|--------|--------|-------|------|
| Valore azione inferiore LEX,8h | 80 dB(A) | ✅ | threshold_band presente |
| Valore azione inferiore LpC,peak | 135 dB(C) | ✅ | Verificabile |
| Valore azione superiore LEX,8h | 85 dB(A) | ✅ | threshold_band presente |
| Valore azione superiore LpC,peak | 137 dB(C) | ✅ | Verificabile |
| Valore limite LEX,8h | 87 dB(A) | ✅ | threshold_band presente |
| Valore limite LpC,peak | 140 dB(C) | ✅ | Verificabile |

**STATO:** Conforme - Soglie implementate correttamente

---

## 11. TRACCIABILITÀ E AUDIT

### 11.1 Origine Dati

| # | Requisito | Riferimento | Stato | Note |
|---|-----------|-------------|-------|------|
| 11.1.1 | value_origin per ogni dato | GOVERNANCE | ✅ | Presente in role_phase_exposure |
| 11.1.2 | confidence_level | GOVERNANCE | ✅ | Presente |
| 11.1.3 | Distingere stimato vs misurato | GOVERNANCE | ✅ | value_origin gestisce |
| 11.1.4 | Distingere AI suggerito | GOVERNANCE | ✅ | AI_SUGGESTED presente |
| 11.1.5 | Versionamento dati | GOVERNANCE | ✅ | Presente |

**STATO:** Buon livello di tracciabilità

---

### 11.2 Audit Trail

| # | Requisito | Riferimento | Stato | Note |
|---|-----------|-------------|-------|------|
| 11.2.1 | Logging modifiche | GOVERNANCE | ⚠️ | Non strutturato |
| 11.2.2 | Chi ha creato/modificato | GOVERNANCE | ✅ | created_by presente |
| 11.2.3 | Quando | GOVERNANCE | ⚠️ | created_by ma non updated_at |
| 11.2.4 | Quale dato | GOVERNANCE | ❌ | Non tracciato |
| 11.2.5 | Prompt AI usato | GOVERNANCE | ❌ | Non gestito |

**CRITICITÀ:** 2 requisiti mancanti, 2 parziali su 5 totali

---

## RIEPILOGO CRITICITÀ

### ENTITÀ MANCANTI CRITICHE (OBBLIGATORIE PER LEGGE)

| # | Entità | Articolo | Priorità | Note |
|---|--------|----------|----------|------|
| 1 **🔴** | worker_exposure_registry | Art. 193 | **BLOCCANTE** | Registro esposti obbligatorio |
| 2 **🔴** | medical_surveillance | Art. 186 | **BLOCCANTE** | Sorveglianza sanitaria obbligatoria |
| 3 **🔴** | dpi_hearing_protection | Art. 192 | **BLOCCANTE** | Gestione DPI obbligatoria |
| 4 **🔴** | training_record | Art. 187 | **BLOCCANTE** | Formazione obbligatoria |
| 5 **🔴** | rls_consultation | Art. 188 | **BLOCCANTE** | Consultazione RLS obbligatoria |
| 6 **🔴** | signage | Art. 189 | **ALTA** | Segnaletica obbligatoria |

---

### CAMPI MANCANTI CRITICI

| # | Entità | Campo Mancante | Articolo | Priorità |
|---|--------|----------------|----------|----------|
| 1 | noise_assessment | assessment_date | Art. 184 | **BLOCCANTE** |
| 2 | noise_assessment | validity_period | Art. 184 | **ALTA** |
| 3 | noise_assessment | measurement_uncertainty | ISO 9612 | **BLOCCANTE** |
| 4 | noise_assessment | instrument_class | ISO 9612 | **BLOCCANTE** |
| 5 | noise_assessment | other_agents_evaluation | Art. 184, c. 2, lett. f) | **ALTA** |
| 6 | role_phase_exposure | laeq_uncertainty | ISO 9612 | **BLOCCANTE** |
| 7 | role_phase_exposure | noise_type | ISO 9612 | **ALTA** |
| 8 | noise_assessment_result | lex8h_uncertainty | ISO 9612 | **BLOCCANTE** |
| 9 | noise_assessment_result | lex8h_effective | Art. 192 | **BLOCCANTE** |
| 10 | measurement_session | instrument_serial_number | ISO 9612 | **ALTA** |
| 11 | measurement_session | calibration_certificate | ISO 9612 | **ALTA** |
| 12 | mitigation_action | effectiveness_verification | Art. 185 | **MEDIA** |

---

### FUNZIONALITÀ MANCANTI CRITICHE

| # | Funzionalità | Articolo | Priorità |
|---|--------------|----------|----------|
| 1 **🔴** | Calcolo incertezza misura | ISO 9612 | **BLOCCANTE** |
| 2 **🔴** | Calcolo LEX,8h con DPI | Art. 192 | **BLOCCANTE** |
| 3 **🔴** | Gestione esposizione settimanale | ISO 9612 | **ALTA** |
| 4 | Gestione rumore impulsivo | Art. 184 | **ALTA** |
| 5 | Gestione bassa frequenza | Art. 184 | **MEDIA** |
| 6 | Gestione interazione agenti | Art. 184 | **ALTA** |
| 7 | Verifica efficacia misure | Art. 185 | **MEDIA** |
| 8 | Generazione documento completo | Art. 184 | **BLOCCANTE** |

---

## PUNTEGGIO CONFORMITÀ

### Calcolo Conformità

| Area | Requisiti Totali | Conformi | Parziali | Mancanti | Punteggio |
|------|------------------|----------|----------|----------|-----------|
| **1. Valutazione Rischio** | 26 | 4 | 12 | 10 | **15%** |
| **2. Misure Prevenzione** | 12 | 3 | 5 | 4 | **25%** |
| **3. Sorveglianza Sanitaria** | 16 | 1 | 2 | 13 | **6%** |
| **4. Formazione** | 14 | 0 | 5 | 9 | **0%** |
| **5. DPI Uditivi** | 13 | 0 | 2 | 11 | **0%** |
| **6. Consultazione RLS** | 6 | 0 | 0 | 6 | **0%** |
| **7. Segnaletica** | 6 | 0 | 0 | 6 | **0%** |
| **8. Registro Esposti** | 9 | 0 | 0 | 9 | **0%** |
| **9. Calcoli Tecnici** | 16 | 7 | 2 | 7 | **44%** |
| **10. Soglie Normative** | 6 | 6 | 0 | 0 | **100%** |
| **11. Tracciabilità** | 10 | 5 | 3 | 2 | **50%** |
| **TOTALE** | **134** | **26** | **31** | **77** | **19%** |

---

## PRIORITÀ IMPLEMENTAZIONE

### FASE 1 - CRITICO (BLOCCANTE PER CONFORMITÀ)

**Tempo stimato:** 4-6 settimane

1. **Implementare entità worker_exposure_registry** (Art. 193)
2. **Implementare entità medical_surveillance** (Art. 186)
3. **Implementare entità dpi_hearing_protection** (Art. 192)
4. **Implementare entità training_record** (Art. 187)
5. **Implementare entità rls_consultation** (Art. 188)
6. **Implementare calcolo incertezza misura** (ISO 9612)
7. **Implementare calcolo LEX,8h efficace con DPI** (Art. 192)
8. **Aggiungere campi incertezza** a tutte le misure
9. **Aggiungere assessment_date** a noise_assessment
10. **Aggiungere instrument_class** a measurement_session

---

### FASE 2 - ALTA PRIORITÀ

**Tempo stimato:** 2-3 settimane

1. **Implementare entità signage** (Art. 189)
2. **Implementare gestione esposizione settimanale** (ISO 9612)
3. **Implementare gestione rumore impulsivo**
4. **Implementare gestione interazione altri agenti** (Art. 184)
5. **Aggiungere validity_period** a noise_assessment
6. **Aggiungere noise_type** a role_phase_exposure
7. **Aggiungere effectiveness_verification** a mitigation_action
8. **Migliorare audit trail**

---

### FASE 3 - MEDIA PRIORITÀ

**Tempo stimato:** 1-2 settimane

1. **Implementare gestione bassa frequenza**
2. **Migliorare reportistica**
3. **Migliorare tracciabilità prompt AI**
4. **Implementare gestione lavoratori interinali**
5. **Implementare gestione smart working**

---

## DOCUMENTI NECESSARI PER CONFORMITÀ

### Documenti da Generare Automaticamente

1. **Documento Valutazione Rischio Rumore** (Art. 184)
   - Tutti i 16 contenuti obbligatori
   
2. **Registro Lavoratori Esposti** (Art. 193)
   - Dati anagrafici completi
   
3. **Registro Consegna DPI** (Art. 192)
   - Tracciabilità DPI per lavoratore
   
4. **Registro Formazione** (Art. 187)
   - Presenze, contenuti, attestati
   
5. **Verbale Consultazione RLS** (Art. 188)
   - Data, argomenti, firme
   
6. **Piano Misure Riduzione** (Art. 185)
   - Azioni, tempistiche, responsabili

---

## CONCLUSIONI

**STATO ATTUALE:**
- Conformità normativa: **19%**
- Entità critiche mancanti: **6**
- Campi critici mancanti: **12**
- Funzionalità critiche mancanti: **8**

**BLOCCANTI PER CONFORMITÀ LEGALE:**
- Registro esposti (Art. 193)
- Sorveglianza sanitaria (Art. 186)
- Gestione DPI (Art. 192)
- Formazione (Art. 187)
- Consultazione RLS (Art. 188)
- Calcolo incertezza (ISO 9612)
- Calcolo esposizione con DPI (Art. 192)

**AZIONI IMMEDIATE RICHIESTE:**
1. Implementare le 6 entità critiche mancanti
2. Aggiungere campi incertezza a tutte le misure
3. Implementare calcolo LEX,8h efficace con DPI
4. Completare i campi metodologia valutazione
5. Implementare generazione documenti obbligatori

---

**Documento elaborato:** Aprile 2026  
**Versione:** 1.0  
**Riferimenti:** D.Lgs. 81/2008, ISO 9612:2009, UNI 11347:2015