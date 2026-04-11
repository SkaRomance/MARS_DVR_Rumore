# CONTEXT_FOR_CODING_AGENT.md

## Project Identity
**Project name:** MARS DVR Rumore Module
**Project type:** B2B SaaS module for Italian HSE consulting software
**Primary goal:** Specialist module for noise risk assessment (D.Lgs. 81/2008) that integrates into the MARS general DVR system, supporting data collection, estimation, measurement, calculation, document generation, and AI-assisted review.

This project is **not** a generic noise assessment tool. It is a **vertical module** designed to work within the MARS consultant software ecosystem, interoperable with the general DVR, and AI-driven.

---

## What the product must do

Build a specialist module that:

1. Creates and manages noise risk assessments linked to companies, production units, departments, processes, and job roles
2. Maps ATECO codes → typical processes → standard job roles → potential noise sources
3. Manages a catalog of equipment (machinery, tools, plants, handling equipment) with known sound power levels
4. Accepts input data: knowledge base estimates, manual consultant declarations, instrumental measurements, attachments
5. Calculates LEX,8h (daily noise exposure), weekly exposure, peak levels
6. Classifies risk against action thresholds (lower action value 80 dB(A), upper action value 85 dB(A), limit value 87 dB(A))
7. Provides AI prompts for: initial setup, technical review, normative explanation, DVR chapter narrative generation
8. Exports structured data to the general DVR, with versioning and full audit trail
9. Distinguishes between estimated, declared, and measured data origins
10. Supports multi-language document export (Italian primary, English, others)

---

## Core users
### 1. Senior HSE Consultant
Uses the system to onboard clients, configure assessments, import or declare measurements, and generate DVR chapters.

### 2. HSE Technician / RSPP External
Needs job role mapping, exposure calculations, and mitigation recommendations.

### 3. Employer (assisted)
Needs to understand results and approve mitigation actions.

### 4. MARS Platform Internal Reviewer
Audits module outputs for quality and compliance.

---

## MVP scope (current implementation phase)
### In scope for MVP (Phase 1-4)
- NoiseAssessment CRUD linked to Company/UnitSite
- ATECO catalog import and mapping
- NoiseSourceCatalog (machines, equipment from PAF - Portale Agenti Fisici)
- JobRole exposure estimation (ISO 9612 based)
- Input data: estimates, manual declarations, measurements
- ISO 9612 calculation engine (LEX,8h, LEX,weekly, peak, K corrections, uncertainty)
- Risk classification per Art. 188 D.Lgs. 81/2008
- AI Orchestrator with 7 agents: Bootstrap, Review, Explain, Narrative, Mitigation, SourceDetection
- Ollama LLM integration (GLM-5.1 for planning, minimax-m2.7 for building)
- Export to JSON, DVR_FULL, DVR_SUMMARY formats
- DOCX generation with configurable header/footer/cover templates
- WYSIWYG in-browser document editor (Vanilla JS frontend)
- Assessment versioning on export

### Out of scope for MVP
- Real-time audio analysis from microphone
- Direct integration with certified phonometers
- 3D CAD/acoustic layout simulation
- Advanced environmental simulations
- Cloud-native multi-tenant SaaS deployment (future)
- License management system (future)

---

## Product principles

1. **Traceability first**: every data origin (estimated/declared/measured) must be labeled
2. **Auditability**: all AI inferences must be reviewable before approval
3. **Italian compliance context**: all labels, workflows, and normative references reflect Italian D.Lgs. 81/2008
4. **Consultant-friendly**: one assessment setup should be achievable in under 5 minutes
5. **Deterministic before AI**: calculation engine uses ISO 9612 rules; AI assists but does not decide
6. **No closed automatic decisions**: every AI suggestion must be confirmed or modified by the consultant

---

## Primary workflows to implement

### Workflow A: Consultant creates a new noise assessment
- Select/create Company + Unit Site
- Enter ATECO code(s) → system suggests typical processes, job roles, noise sources
- Bootstrap AI fills initial draft (processes, roles, equipment)
- Consultant reviews, modifies, confirms
- Add measurements or manual declarations
- Run ISO 9612 calculation
- Review results and risk classification
- Generate or regenerate DVR narrative via AI
- Export to DVR (new version)

### Workflow B: Consultant reviews and edits document
- Open assessment
- Select DVR chapter section to edit
- WYSIWYG editor loads section content
- Consultant modifies text directly in browser
- Save edits (stored as draft)
- Regenerate or export final version

### Workflow C: Generate and export document
- Select assessment + export format (JSON, DVR_FULL, DOCX)
- Configure template (header, footer, cover, language)
- System assembles document with:
  - Pre-formed structure (headers, footers, cover)
  - AI-generated content (intro, body sections)
  - Consultant-edited sections (from Workflow B)
- Create new version (AssessmentDocument)
- Return download URL or trigger browser download

### Workflow D: Consultant imports from MARS general DVR
- Receive assessment data from parent DVR system
- Map general DVR entities to noise module entities
- Populate assessment with imported data
- Continue with Workflow A from populated state

---

## Functional requirements (current phase)

### FR-01 - Assessment Management
- Create NoiseAssessment linked to Company and UnitSite
- Store: description, status, assessment_date, next_review_date, measurement_protocol, instrument_class
- Support soft-delete (_is_deleted flag)

### FR-02 - ATECO Integration
- Seeded ATECO 2007 catalog (~700 codes, currently 15 sample)
- Macro-category descriptions generated dynamically by AI
- Map ATECO → suggested processes → suggested job roles → suggested noise sources

### FR-03 - Noise Source Catalog
- Source from PAF (Portale Agenti Fisici) - ~2,452 machines currently seeded
- Fields: marca, modello, tipologia, alimentazione, laeq_min/typ/max, lcpeak, fonte
- Link to MachineAsset for company-specific instances

### FR-04 - ISO 9612 Calculation Engine
- Input: exposure time per job role, sound levels, peak levels
- Calculate: LEX,8h, LEX,weekly, lcpeak, uncertainty, confidence
- Apply K corrections: k_impulse, k_tone, k_background
- Classify: risk band (green/yellow/orange/red per Art. 188)
- Support measured vs. estimated data distinction

### FR-05 - AI Orchestration (Phase 3 complete)
- 7 agents: Bootstrap, Review, Explain, Narrative, Mitigation, SourceDetection
- OllamaProvider with GLM-5.1/minimax-m2.7 via local Ollama
- 750 max_tokens, 0.3 temperature for JSON responses
- AIInteraction logging, AISuggestion with approve/reject workflow
- NarrativeTemplate database model for section templates

### FR-06 - Export System (Phase 4 in progress)
- Export formats: JSON, DVR_FULL, DVR_SUMMARY, DOCX
- DOCX generation with python-docx
- Template system: file-based (.docx on disk) + database overrides
- Print settings: header, footer, cover page configurable
- Assessment versioning (each export creates new AssessmentDocument version)
- Language support: Italian (primary), English

### FR-07 - Document Editor (Phase 4 in progress)
- Vanilla JS frontend (no React/Angular/Vue)
- WYSIWYG in-browser editing via contenteditable
- Toolbar: bold, italic, underline, headings, lists, tables
- Section-by-section editing
- Preview before export

### FR-08 - Multi-tenant Licensing (future phase)
- SaaS-ready architecture (future)
- License key management
- Tenant isolation
- Usage metering

---

## Technical stack

### Backend
- **Framework**: FastAPI (Python)
- **ORM**: SQLAlchemy 2.0 (async with asyncpg)
- **Migrations**: Alembic
- **AI**: Ollama local provider + OllamaProvider abstraction
- **Template**: Jinja2 (for AI prompts; DOCX uses python-docx)
- **Document**: python-docx, mammoth (for reading existing DOCX)

### Frontend
- **Type**: Vanilla JS (no framework)
- **Styling**: Plain CSS with CSS variables
- **Editor**: Native contenteditable API
- **Serving**: FastAPI static file mounting

### Database
- **Engine**: PostgreSQL (via asyncpg)
- **Cache**: Redis (for session and LLM caching)

---

## Architecture

```
src/
├── api/
│   ├── routes/           # FastAPI routers (assessments, ai_routes, export_routes, health)
│   └── schemas/          # Pydantic schemas (assessment, ai, export)
├── application/
│   └── use_cases/        # Business logic orchestration
├── bootstrap/
│   ├── main.py           # FastAPI app, lifespan, CORS, route registration
│   └── config.py         # Settings (pydantic-settings)
├── domain/
│   ├── entities/         # Domain entities (if separate from models)
│   ├── value_objects/    # Value objects (ExposureOrigin, RiskBand, etc.)
│   └── services/
│       ├── ai_orchestrator.py
│       ├── agents/       # 7 AI agents
│       ├── prompts/      # Template loader, prompt templates
│       ├── noise_calculation.py  # ISO 9612 engine
│       └── docx_generator.py      # DOCX generation (Phase 4)
├── infrastructure/
│   ├── database/
│   │   ├── models/       # SQLAlchemy models
│   │   └── repositories/ # Data access
│   ├── llm/              # OllamaProvider, MockProvider
│   └── cache/            # Redis integration
└── paf_noise_cli/        # CLI application

static/                   # Frontend (Vanilla JS)
├── index.html
├── css/
├── js/
└── assets/

migrations/versions/      # Alembic migrations (001-006 planned)
data/
├── ateco/               # ATECO catalog JSON
└── knowledge_base/      # PAF noise source data
```

---

## Database models

### Existing (001-005 migrations applied)
- `Company` - organization with ATECO
- `NoiseAssessment` - main assessment entity
- `NoiseAssessmentResult` - per-job-role exposure results
- `NoiseSourceCatalog` - PAF machines/equipment
- `MachineAsset` - company-specific equipment instances
- `AtecoCatalog` - ATECO 2007 codes
- `AIInteraction` - AI query/response log
- `AISuggestion` - AI-generated suggestions with approval workflow
- `NarrativeTemplate` - section templates (DB-stored)

### Planned (Migration 006)
- `JobRole` - job roles with exposure mapping
- `MitigationMeasure` - technical/administrative/PPE measures
- `DocumentTemplate` - DOCX template overrides
- `PrintSettings` - header/footer/cover configuration
- `AssessmentDocument` - versioned exported documents

---

## API endpoints (current + planned)

### Assessments (complete)
- `POST /api/v1/assessments` - Create assessment
- `GET /api/v1/assessments/{id}` - Get assessment
- `POST /api/v1/assessments/calculate` - Run ISO 9612 calculation

### AI (Phase 3 complete)
- `POST /api/v1/assessments/{id}/ai/bootstrap` - Initial setup
- `POST /api/v1/assessments/{id}/ai/review` - Technical review
- `POST /api/v1/assessments/{id}/ai/explain` - Normative explanation
- `POST /api/v1/assessments/{id}/ai/narrative` - Generate DVR text
- `POST /api/v1/assessments/{id}/ai/suggest-mitigations` - Mitigation recommendations
- `POST /api/v1/assessments/{id}/ai/detect-sources` - Match noise sources
- `GET /api/v1/assessments/{id}/ai/suggestions` - List suggestions
- `POST /api/v1/assessments/{id}/ai/suggestions/{sid}/action` - Approve/reject

### Export (Phase 4 in progress)
- `GET /api/v1/assessments/{id}/document` - Get full DVR document
- `GET /api/v1/assessments/{id}/document/sections` - List sections
- `GET /api/v1/assessments/{id}/document/sections/{section}` - Get section
- `PUT /api/v1/assessments/{id}/document/sections/{section}` - Update section (editor)
- `POST /api/v1/assessments/{id}/export/json` - Export JSON
- `POST /api/v1/assessments/{id}/export/docx` - Export DOCX
- `GET /api/v1/assessments/{id}/export/preview` - Export preview
- `GET /api/v1/templates` - List templates
- `PUT /api/v1/templates/{id}` - Override template
- `GET /api/v1/print-settings` - Get print settings
- `PUT /api/v1/print-settings` - Save print settings

### Health
- `GET /health` - Health check

---

## Risk classification (Art. 188 D.Lgs. 81/2008)

| Risk Band | LEX,8h Range | Color | Action |
|-----------|-------------|-------|--------|
| GREEN | < 80 dB(A) | Basso | No specific action |
| YELLOW | 80-85 dB(A) | Media | Provide hearing protection, information |
| ORANGE | 85-87 dB(A) | Alto | Hearing protection mandatory, program |
| RED | > 87 dB(A) | Elevato | Exposure limit exceeded, immediate action |

---

## Implementation status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0 - Discovery | ✅ Complete | Context, PRD, normative analysis |
| Phase 1 - Foundations | ✅ Complete | DB schema, catalogs, API bootstrap |
| Phase 2 - Calculation Core | ✅ Complete | ISO 9612 engine, 34 tests passing |
| Phase 3 - AI Integration | ✅ Complete | 7 agents, 38 tests passing |
| Phase 4 - DVR Integration | 🔄 In Progress | DOCX export, WYSIWYG editor, templates |
| Phase 5 - Hardening | ⏳ Planned | QA, security, audit logging |

---

## Model configuration (per CORE_PROTOCOL.md)

- **Plan Mode (strategy, architecture, research)**: `ollama/glm-5.1:cloud`
  - Modalità: massima potenza, analisi dipendenze, contesto esteso
- **Build Mode (implementation, UI, backend)**: `ollama/minimax-m2.7:cloud`
  - Modalità: implementazione massiva, focus su test

---

## Workflow di riferimento

1. **Plan Mode** → usa glm-5.1:cloud per pianificazione
2. **Build Mode** → usa minimax-m2.7:cloud per implementazione
3. Dopo ogni task significativa: review → commit → push
4. Ogni 10 messaggi: context compaction

---

## Acceptance criteria (current phase)

1. Export DOCX generates valid Word document with all DVR sections
2. WYSIWYG editor loads, edits, and saves section content
3. Template override (file + DB) works correctly
4. Print settings (header/footer/cover) apply to generated DOCX
5. Language switching (IT/EN) reflected in exported document
6. Each export creates new versioned document
7. Assessment not found → 404 response
8. All existing tests pass (38 tests Phase 3)

---

## Definition of done for engineering agent

The work is done only when:
- Code compiles/runs without errors
- Database migration created for new models
- DOCX export produces valid Word document
- WYSIWYG editor functional in browser
- API endpoints return correct responses
- Unit tests pass for new functionality
- Commit with descriptive message after each significant change

---

## Context compaction

Every 10 messages, summarize conversation state:
- Current task progress
- What has been completed
- What remains to be done
- Any blockers or questions

---

## Licensing & multi-tenant (future)

Architecture must be ready for:
- License key validation per tenant
- Tenant isolation at database level
- Usage metering and limits
- MARS MADRE system integration (logo inheritance)
