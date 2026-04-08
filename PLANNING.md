# PLANNING - Modulo DVR Rumore MARS

## Cronologia Sessione PLAN

**Data**: 2026-04-07
**Modello PLAN**: `glm-5:cloud`
**Modello BUILD**: `minimax-m2.7:cloud`
**Stato**: APPROVATO per BUILD

---

## 1. ARCHITETTURA DI PROGETTO

### Stack Tecnologico

| Componente | Tecnologia | Motivazione |
|------------|------------|-------------|
| **Backend** | Python 3.11+ / FastAPI / Pydantic 2.x | Calcoli scientifici (numpy/scipy), ecosistema AI, rapidità MVP |
| **Database** | PostgreSQL 15+ | Relazioni complesse, JSONB, full-text search, RLS per multi-tenant |
| **Cache** | Redis 7+ | Knowledge base caching, rate limiting AI |
| **AI** | OpenAI GPT-4 / Anthropic Claude via API | Qualità generazione testo,托管, costi contenuti |
| **Calcoli** | numpy / scipy | Precisione numerica per LEX,8h |

### Architettura: Monolite Modulare (NO microservizi per MVP)

```
noise_module/
├── api/          # Boundary API
├── domain/       # Business logic isolata
├── infrastructure/  # DB, external services
├── application/  # Use cases
└── bootstrap/    # Entry point
```

### Integrazione DVR Generale

**Raccomandazione**: Database condiviso con schema separato `noise_*`

```sql
-- Schema shared
noise_assessment.company_id → companies.id (FK)
noise_assessment.job_role_id → job_roles.id (FK)
```

**API Sync**: POST `/export/general-dvr` con payload JSON strutturato.

### Vincoli Deploy

| Tier | Tipo | Requisiti |
|------|------|-----------|
| **Tier 1** | On-Premise | 4 vCPU, 8GB RAM, 100GB SSD |
| **Tier 2** | Cloud Multi-tenant | Kubernetes, RDS PostgreSQL, ElastiCache |
| **Tier 3** | Ibrido | Roadmap M+12 |

---

## 2. DATABASE SCHEMA

### Schema SQL - 15+ Entità

#### ENUM Types

```sql
CREATE TYPE value_origin AS ENUM (
    'measured', 'calculated', 'estimated', 'imported',
    'ai_suggested', 'validated', 'default_value'
);

CREATE TYPE threshold_band AS ENUM (
    'negligible', 'low', 'medium', 'high', 'critical'
);

CREATE TYPE action_type AS ENUM (
    'administrative', 'technical', 'ppe', 'medical', 'training', 'engineering'
);

CREATE TYPE entity_status AS ENUM ('active', 'inactive', 'archived');
```

#### Entità Principali

| Entità | Descrizione | Note |
|--------|-------------|------|
| `company` | Anagrafica azienda | ATECO primario, secondari |
| `unit_site` | Unità produttive | GPS, indirizzo |
| `process` | Processi aziendali | Codice, nome, is_noisy |
| `work_phase` | Fasi lavorative | Durata tipica, noise_relevance_score |
| `job_role` | Mansioni | Codice, nome, categoria |
| `machine_asset` | Macchinari | Marca, modello, matricola, fonte |
| `noise_source_catalog` | Catalogo sorgenti | Range tipico min/max, fonte |
| `role_phase_exposure` | Esposizioni mansione-fase | LAeq, durata, origine |
| `measurement_session` | Sessioni fonometriche | Strumento, calibrazione, condizioni |
| `measurement_point` | Punti di misura | Valore, picco, incertezza |
| `noise_assessment` | Valutazione rumore | Versionata, status, approvazione |
| `noise_assessment_result` | Risultati per mansione | LEX,8h, peak, classificazione |
| `mitigation_action` | Azioni di mitigazione | Tipo, priorità, stato |
| `source_registry` | Registro fonti | URL, licenza, versione |

#### Versioning

- Copy-on-write: ogni modifica crea nuovo record con `version++` e `previous_version_id`
- Soft delete: `_is_deleted = TRUE` + `status = 'archived'`
- Trigger automatici per audit trail

#### Indici Critici

```sql
-- Performance critical
CREATE INDEX idx_noise_assessment_result_lex ON noise_assessment_result(lex_8h);
CREATE INDEX idx_noise_assessment_result_risk ON noise_assessment_result(risk_band) 
    WHERE risk_band IN ('high', 'critical');
CREATE INDEX idx_assessment_version ON noise_assessment(id, version);
```

---

## 3. FONTI DATI

### ATECO 2007

| Fonte | Formato | Licenza | Commerciale |
|-------|---------|---------|-------------|
| **ISTAT** (primaria) | XLSX | Open Data | ✅ Consentito |
| **Schema.gov.it** (backup) | JSON-LD/RDF | CC-BY 4.0 | ✅ Consentito |

**Strategia**:
1. Download snapshot versionato: `data/ateco/YYYY-MM-DD_ateco2007.xlsx`
2. Conversione XLSX → JSON strutturato
3. Hash SHA256 per integrità
4. Aggiornamento: manuale on-demand

### PAF Banca Dati Rumore

| Stato | Uso Commerciale |
|-------|----------------|
| ⚠️ **VIETATO** | Uso parziale per scopi commerciali vietato dai ToS |

**Alternative**:
- A) Accordo formale con PAF
- B) Knowledge base interna MARS (curata, versionata)
- C) Import manuale utente (NON integrato automaticamente)

---

## 4. GAP CRITICI IDENTIFICATI DAGLI AGENTS

### Gap DATA_MODEL (corretti prima del build)

| Gap | Entità/Campo | Riferimento |
|-----|--------------|-------------|
| ❌ LCpeak mancante | `noise_assessment_result` | Art. 190, 191 D.Lgs. 81/2008 |
| ❌ lex_weekly mancante | `noise_assessment_result` | Art. 190 c.2 |
| ❌ exposure_type mancante | `role_phase_exposure` | Stima/Misura/Dichiarazione |
| ❌ workers_count_exposed mancante | `noise_assessment` | Numero lavoratori per mansione |
| ❌ representative_workers mancante | `noise_assessment` | Consultazione RLS |
| ❌ measurement_protocol mancante | `measurement_session` | UNI EN ISO 9612 |
| ❌ instrument_class mancante | `measurement_session` | Classe fonometro I/II |
| ❌ uncertainty_value mancante | `measurement_point` | Allegato IV bis |
| ❌ background_noise mancante | `measurement_point` | Rumore di fondo |
| ❌ corrective_action_status mancante | `mitigation_action` | Stato attuazione |

### Entità Aggiuntive da Creare

| Entità | Descrizione | Riferimento |
|--------|-------------|-------------|
| `dpi_hearing_protection` | Catalogo DPI uditivi con NRR/SNR | Art. 192 c.2 |
| `health_surveillance` | Sorveglianza sanitaria | Art. 196, 197 |
| `training_session` | Sessioni formazione | Art. 192 c.4 |
| `sensitive_worker_factors` | Gravidanza, minori, ototossici, vibrazioni | Art. 188, Allegato VIII |

### Gap NOISE_CALCULATION_SPEC

| Gap | Azione |
|-----|--------|
| Formula ESPLICITA ASSENTE | Integrare formula matematica ISO 1999 |
| Incertezza ±dB ASSENTE | Aggiungere sezione con ISO/IEC Guide 98-3 |
| Correzioni K ASSENTI | K_impulse, K_tone, K_background da ISO 1999 |
| LCPeak aggregato ASSENTE | Gestire soglie 135/137/140 dB(C) |
| Lavoratori sensibili ASSENTI | Effetto sinergico rumore+ototossici+vibrazioni |

---

## 5. NORMATIVA E COMPLIANCE

### Riferimenti Legislativi Obbligatori

| Riferimento | Oggetto |
|-------------|---------|
| **D.Lgs. 81/2008** | Titolo VIII Capo II (artt. 181-196) |
| **D.Lgs. 81/2008 Art. 190** | Contenuto documento valutazione |
| **D.Lgs. 195/2006** | Attuazione Direttiva 2003/10/CE |
| **UNI EN ISO 9612:2011** | Misurazione esposizione rumore |
| **Allegato IV bis D.Lgs. 81/2008** | Requisiti fonometri |

### Valori di Riferimento (Art. 188)

| Parametro | Valori inferiori | Valori superiori | Valore limite |
|-----------|------------------|------------------|---------------|
| LEX,8h | 80 dB(A) | 85 dB(A) | 87 dB(A) |
| Ppicco | 135 dB(C) | 137 dB(C) | 140 dB(C) |

### Obblighi per Soglia

| LEX,8h | Obblighi |
|---------|----------|
| **< 80 dB(A)** | Valutazione, nessun obbligo specifico |
| **80-85 dB(A)** | Informazione, formazione, DPI disponibili |
| **85-87 dB(A)** | DPI obbligatori, sorveglianza sanitaria, programma misure |
| **> 87 dB(A)** | Azioni immediate, misure urgenti, sorveglianza |

---

## 6. BACKLOG MVP

### MoSCoW

#### MUST HAVE

| ID | Feature | RF | Story Points |
|----|---------|----|--------------|
| M-01 | Creazione valutazione anagrafica | RF-01 | 5 |
| M-02 | Associazione ATECO + proposta processi/mansioni | RF-02 | 3 |
| M-03 | Catalogo sorgenti rumore / macchinari | RF-03 | 8 |
| M-04 | Input tempi esposizione manuali | RF-04 | 5 |
| M-05 | Calcolo LEX,8h base | RF-05 | 8 |
| M-06 | Classificazione soglie (80/85/87 dB) | RF-05 | 5 |
| M-07 | Generazione capitolo DVR rumore | RF-06 | 13 |

#### SHOULD HAVE

| ID | Feature | RF | Story Points |
|----|---------|----|--------------|
| S-01 | Import misure strumentali | RF-04 | 8 |
| S-02 | Prompt AI guidato | RF-06 | 8 |
| S-03 | Suggerimenti misure prevenzione | RF-05 | 5 |
| S-04 | Logging origine dato | RF-04/NF | 3 |

#### COULD HAVE

| ID | Feature | RF | SP |
|----|---------|----|----|
| C-01 | Prompt AI libero (natural language) | RF-06 | - |
| C-02 | Allegati (relazioni fonometriche, foto) | RF-04 | - |

#### WON'T HAVE (MVP)

| ID | Feature |
|----|---------|
| W-01 | Analisi realtime da file audio |
| W-02 | Integrazione fonometri IoT |
| W-03 | CAD/layout acustico |

### Sprint Plan

| Sprint | Focus | SP | Durata |
|--------|-------|-----|--------|
| 1 | Foundation | 16 | 2 settimane |
| 2 | Data Input | 21 | 2 settimane |
| 3 | Calculation Core | 26 | 2 settimane |
| 4 | AI & Generation | 31 | 2 settimane |
| 5 | Export & Integration | 23 | 2 settimane |
| 6 | Hardening | 26 | 2 settimane |
| **TOTAL** | **MVP** | **143** | **12 settimane** |

---

## 7. API ENDPOINTS

### Base Path: `/api/v1/noise`

| Method | Endpoint | Descrizione |
|--------|----------|-------------|
| POST | `/assessments` | Crea nuova valutazione |
| GET | `/assessments/{id}` | Recupera valutazione |
| POST | `/assessments/{id}/bootstrap` | Bootstrap da ATECO/prompt |
| POST | `/assessments/{id}/phases` | Gestione fasi |
| POST | `/assessments/{id}/machines` | Gestione macchinari |
| POST | `/assessments/{id}/measurements/import` | Import misure |
| POST | `/assessments/{id}/calculate` | Calcola LEX,8h |
| POST | `/assessments/{id}/generate-report` | Genera capitolo DVR |
| POST | `/assessments/{id}/ai/prompt` | Prompt AI (bootstrap/review/rewrite/explain) |
| POST | `/assessments/{id}/export/general-dvr` | Export verso DVR |

---

## 8. AI PROMPTING FRAMEWORK

### 5 Modalità

| Mode | Purpose | Output |
|------|---------|--------|
| `bootstrap` | Inizializzazione da ATECO/descrizione | Processi, mansioni, sorgenti |
| `review` | Revisione dati esistenti | Anomalie, correzioni |
| `explain` | Spiegazione tecnica normativa | Riferimenti, conseguenze |
| `rewrite` | Generazione testo DVR | Narrativa formale |
| `detect_sources` | Identificazione sorgenti | Livelli tipici, fonti |

### Guardrails

| ID | Type | Enforcement |
|----|------|-------------|
| GH-01 | No Invented Values | STRICT |
| GH-02 | Source Attribution | STRICT |
| GH-03 | Range Reasonableness | STRICT |
| GN-01 | No False Certainty | STRICT |
| GN-02 | Regulatory Accuracy | STRICT |
| GR-01 | Physical Values | STRICT |
| GR-02 | Calculation Integrity | STRICT |
| GC-01 | Internal Consistency | STRICT |
| GC-02 | Temporal Logic | STRICT |

### Confidence Scoring

| Range | Label | Azione |
|-------|-------|--------|
| 0.90-1.00 | Very High | Procedi normalmente |
| 0.75-0.89 | High | Verifica opzionale |
| 0.50-0.74 | Medium | Verifica raccomandata |
| 0.25-0.49 | Low | Verifica richiesta |
| 0.00-0.24 | Very Low | Non utilizzare |

### Fallback Strategy

| Level | Status | Features |
|-------|--------|----------|
| 1 | Optimal | Full AI, all features |
| 2 | Degraded | Basic bootstrap, limited suggestions |
| 3 | Minimal | Template only, manual required |
| 4 | Fallback | Offline mode, cached suggestions |

---

## 9. UX FLOW

### Flusso Principale

```
[NUOVA VALUTAZIONE]
       ↓
[ATECO INPUT + BOOTSTRAP AI]
       ↓
[PROCESSI & MANSIONI (AI propose → utente valida)]
       ↓
[SORGENTI RUMOROSE (catalogo + manuale)]
       ↓
[ESPOSIZIONI PER MANSIONE (tempi + LAeq)]
       ↓
[CALCOLO LEX,8h + CLASSIFICAZIONE SOGLIE]
       ↓
[MISURE SUGGERITE (DPI, formazione, sorveglianza)]
       ↓
[GENERAZIONE CAPITOLO DVR]
       ↓
[EXPORT → DVR GENERALE]
```

### Badge Origine Dato

| Badge | Label | Descrizione |
|-------|-------|-------------|
| 🤖 | AI Suggested | Valore generato da AI, richiede validazione |
| 📊 | Measured | Dato da misura strumentale |
| 📏 | Manufacturer | Dichiarazione costruttore |
| 📚 | KB Estimated | Database pubblico |
| ✓ | Validated | Confermato dal consulente |

---

## 10. CASI TEST

### Calcolo LEX,8h

#### Positivo: Metalmeccanico

```
Input:
  - Fase 1: Tornio CNC, LAeq=85 dB(A), T=4h, origine=MEASURED
  - Fase 2: Saldatura, LAeq=90 dB(A), T=2h, origine=MANUFACTURER_DECLARED
  - Fase 3: Ufficio, LAeq=60 dB(A), T=2h, origine=MEASURED

Output atteso:
  - LEX,8h ≈ 83.2 dB(A)
  - Soglia: 80 < LEX < 85 → Azioni migliorative
```

#### Positivo: Edilizia

```
Input:
  - Fase 1: Mazzetta demolitrice, LAeq=105 dB(A), T=2h, LCPeak=138 dB(C)
  - Fase 2: Trapano, LAeq=95 dB(A), T=3h
  - Fase 3: Viaggio cantiere, LAeq=70 dB(A), T=3h

Output atteso:
  - LEX,8h ≈ 95.8 dB(A) → SUPERIORE 85 dB(A)
  - LCPeak = 138 dB(C) → SUPERIORE 135 dB(C)
```

#### Negativo: Valore impossibile

```
Input:
  - LAeq = -10 dB(A)

Output atteso:
  - ERRORE: "LAeq negativo non valido"
```

---

## 11. DISCLAIMER OBBLIGATORI

### Disclaimer Generale

```
ATTENZIONE: MARS è uno strumento di supporto alla valutazione del rischio rumore.
NON sostituisce la responsabilità professionale del consulente che firma il DVR.
Tutti i calcoli, suggerimenti e narrative generate sono da intendersi come
supporto tecnico da validare caso per caso.
```

### Disclaimer Calcolo

```
CALCOLATORE LEX,8h: Il risultato è un'elaborazione matematica basata 
sui dati immessi. L'esattezza del risultato dipende completamente 
dalla qualità dei dati di input.
```

### Disclaimer AI

```
TESTO GENERATO DA AI: I contenuti proposti sono elaborazioni basate su
pattern testuali e riferimenti normativi. Devono essere rivisti,
integrati e validati dal consulente prima dell'inclusione nel DVR.
```

---

## 12. KPI

| KPI | Target | Misurazione |
|-----|--------|-------------|
| Setup Time | < 5 min | Timestamp creazione → primo calcolo |
| Precompilation Rate | > 60% | (campi confermati / proposti) × 100 |
| Chapter Generation Time | < 30 s | Timestamp richiesta → completamento |
| AI Revision Cycles | < 2 | Contatore revisioni rigenerate |
| DVR Integration Reuse | > 80% | (dati esportati / totali) × 100 |
| Calculation Error Rate | < 1% | (calcoli falliti / totali) × 100 |

---

## 13. MACRO-TASK FASE 1 (FOUNDATIONS)

### Macro-task 1.1: Setup Progetto

- **Branch**: `feature/project-setup`
- **File**: Struttura cartelle, pyproject.toml, .gitignore
- **Dipendenze**: fastapi, uvicorn, pydantic, sqlalchemy, asyncpg, alembic, numpy, scipy, openai, jinja2

### Macro-task 1.2: Database Schema

- **Branch**: `feature/db-schema-v1`
- **File**: `migrations/versions/*.sql`
- **Contenuto**: 15 entità, 4 ENUM, indici, trigger audit

### Macro-task 1.3: Schema Fixes

- **Branch**: `feature/schema-fixes`
- **File**: Modifiche DATA_MODEL + SQL
- **Contenuto**: Aggiunge LCpeak, uncertainty, DPI, health_surveillance, training

### Macro-task 1.4: Catalogo ATECO

- **Branch**: `feature/catalog-ateco`
- **File**: Script Python + seed data
- **Contenuto**: Download ISTAT XLSX, conversione JSON, seed PostgreSQL

### Macro-task 1.5: Knowledge Base Rumore

- **Branch**: `feature/knowledge-base`
- **File**: Seed scripts
- **Contenuto**: 50+ entries sorgenti rumore con range tipici

### Macro-task 1.6: API Bootstrap

- **Branch**: `feature/api-bootstrap`
- **File**: `src/api/`
- **Contenuto**: FastAPI skeleton, CRUD /assessments, /bootstrap

---

## 14. RISCHI E MITIGAZIONI

| ID | Rischio | Gravità | Probabilità | Mitigazione |
|----|---------|---------|-------------|-------------|
| R-01 | Scope Creep AI | Alto | Media | Feature freeze post-MVP |
| R-02 | Errori Calcolo LEX | Critico | Alta | Test esaustivi, formula trasparente |
| R-03 | Integrazione DVR | Medio | Media | API contract first |
| R-04 | AI Hallucination | Alto | Alta | Guardrails, validation obbligatoria |
| R-05 | Dati KB Incompleti | Alto | Alta | Validazione, fonte multipla |
| R-06 | Compliance Normativa | Critico | Alta | Review legale, audit trail |

---

## 15. BRANCH STRATEGY

```
main
├── feature/project-setup (1.1)
├── feature/db-schema-v1 (1.2)
├── feature/schema-fixes (1.3)
├── feature/catalog-ateco (1.4)
├── feature/knowledge-base (1.5)
├── feature/api-bootstrap (1.6)
├── feature/calculation-core (Fase 2)
├── feature/ai-integration (Fase 3)
└── feature/dvr-integration (Fase 4)
```

**Regole**:
- Commit atomici, descrittivi
- PR obbligatoria per merge
- Auto-flow: review → commit → push

---

## 16. AGENTS DISPONIBILI

### Agents PLAN (glm-5:cloud)

- `plan-orchestrator-senior`: Coordinamento
- `hse-italy-senior`: Normativa HSE Italia
- `noise-risk-specialist-senior`: Calcoli rumore
- `legal-normative-italy-senior`: Compliance legale
- `product-manager-senior`: Product owner
- `ux-design-senior`: UX specialist
- `consultant-workflow-senior`: Workflow consulente
- `solution-architect-senior`: Architettura
- `data-architect-senior`: Schema dati
- `data-source-researcher-senior`: Banche dati
- `ai-systems-designer-senior`: AI framework
- `evals-designer-senior`: Testing AI

### Agents BUILD (minimax-m2.7:cloud)

- `build/minimax27-cloud`: Implementazione
- `vibe-coder`: Vibe coding
- `compliance-review`: Review compliance
- `backend-architect`: Schema, API

---

**Documento generato**: 2026-04-07
**Stato**: APPROVATO per BUILD
**Prossimo passo**: Esecuzione Macro-task 1.1
