# STRUCTURED_PLAN_PHASE3.md - AI Integration

## Phase 3: AI Integration for MARS Noise Module

**Branch**: `phase3-ai-integration`  
**Based on**: Phase 1 (Project Structure) + Phase 2 (ISO 9612 Calculation Engine)  
**Target**: LLM Integration (GPT-4o / Claude) for intelligent DVR noise assessment assistance

---

## 1. Executive Summary

Phase 3 adds AI capabilities to the MARS Noise Module, enabling:
- **Bootstrap orchestration**: AI-guided initial assessment setup from ATECO + company description
- **Review/Explainability**: AI explanations of calculation results and risk classifications
- **Narrative Generation**: Auto-generation of DVR document text sections
- **Suggested Mitigations**: AI-powered PPE and engineering control recommendations
- **LLM Integration**: Pluggable provider (OpenAI GPT-4o, Anthropic Claude)

---

## 2. Architecture Design

### 2.1 Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                     │
├─────────────────────────────────────────────────────────────┤
│  /ai/bootstrap    │  /ai/review   │  /ai/explain          │
│  /ai/generate     │  /ai/suggest  │  /ai/detect-sources   │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│              AI Orchestration Service                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │BootstrapAgent│ │ ReviewAgent  │ │NarrativeGen  │       │
│  └──────────────┘ └──────────────┘ └──────────────┘       │
│  ┌──────────────┐ ┌──────────────┐                         │
│  │MitigationAge │ │SourceDetect  │                         │
│  └──────────────┘ └──────────────┘                         │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│              LLM Provider Abstraction Layer                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ OpenAI       │ │ Anthropic    │ │ Local/Ollama │       │
│  │ (GPT-4o)     │ │ (Claude)     │ │ (GLM)        │       │
│  └──────────────┘ └──────────────┘ └──────────────┘       │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│              Prompt Templates (Jinja2)                         │
│  bootstrap_prompt.md │ review_prompt.md │ narrative_prompt.md│
│  explain_prompt.md   │ mitigation_prompt.md                   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 AI Service Architecture

```
src/
├── domain/
│   └── services/
│       ├── ai_orchestrator.py      # Main AI service coordinator
│       ├── llm_provider.py          # Abstract LLM interface
│       ├── prompts/
│       │   ├── bootstrap.py         # Bootstrap prompt builder
│       │   ├── review.py            # Review prompt builder
│       │   ├── narrative.py         # Narrative generation
│       │   ├── explain.py           # Explainability prompts
│       │   └── mitigation.py        # Mitigation suggestions
│       └── tools/
│           ├── noise_tools.py       # Tools exposed to AI
│           └── assessment_tools.py  # Assessment context tools
├── infrastructure/
│   └── llm/
│       ├── openai_provider.py       # OpenAI GPT-4o implementation
│       ├── anthropic_provider.py    # Claude implementation
│       └── ollama_provider.py       # Local LLM fallback
└── api/
    └── routes/
        └── ai_routes.py             # AI endpoints
```

---

## 3. Database Schema Additions

### 3.1 New Tables

```sql
-- AI Interaction Log
CREATE TABLE ai_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id UUID NOT NULL REFERENCES noise_assessments(id),
    interaction_type VARCHAR(50) NOT NULL, -- 'bootstrap', 'review', 'explain', 'narrative', 'mitigation'
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    model_used VARCHAR(100) NOT NULL,
    tokens_used INTEGER,
    confidence_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- AI Suggestions with approval workflow
CREATE TABLE ai_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id UUID NOT NULL REFERENCES noise_assessments(id),
    suggestion_type VARCHAR(50) NOT NULL, -- 'process', 'machine', 'role', 'mitigation', 'narrative'
    target_entity_type VARCHAR(50), -- 'phase', 'machine', 'role', etc.
    target_entity_id UUID,
    suggested_data JSONB NOT NULL,
    confidence_score FLOAT,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'rejected', 'modified'
    approved_by UUID,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Narrative Templates (customizable per company)
CREATE TABLE narrative_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_key VARCHAR(100) NOT NULL UNIQUE,
    template_content TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 3.2 Schema Enum Additions

```sql
-- Add to noise_assessments.status
ALTER TYPE assessment_status ADD VALUE 'ai_review_pending';
ALTER TYPE assessment_status ADD VALUE 'ai_generating';
```

---

## 4. API Endpoints to Add

### 4.1 AI Routes (`/api/v1/ai`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/assessments/{id}/ai/bootstrap` | AI-guided initial setup |
| POST | `/assessments/{id}/ai/review` | Review assessment data |
| POST | `/assessments/{id}/ai/explain` | Explain risk decisions |
| POST | `/assessments/{id}/ai/generate-narrative` | Generate DVR text |
| POST | `/assessments/{id}/ai/suggest-mitigations` | Get mitigation suggestions |
| POST | `/assessments/{id}/ai/detect-sources` | Detect noise sources from description |
| GET | `/assessments/{id}/ai/suggestions` | List pending AI suggestions |
| POST | `/assessments/{id}/ai/suggestions/{suggestion_id}/approve` | Approve/reject suggestion |
| GET | `/assessments/{id}/ai/interactions` | View AI interaction history |

### 4.2 Request/Response Schemas

```python
# POST /assessments/{id}/ai/bootstrap
class AIBootstrapRequest(BaseModel):
    ateco_codes: list[str]
    company_description: str
    prompt_mode: Literal["concise", "detailed", "technical"] = "detailed"
    existing_data: Optional[dict] = None

class AIBootstrapResponse(BaseModel):
    suggested_processes: list[ProcessSuggestion]
    suggested_roles: list[RoleSuggestion]
    suggested_noise_sources: list[NoiseSourceSuggestion]
    missing_data: list[str]
    confidence_scores: dict[str, float]
    next_actions: list[str]

# POST /assessments/{id}/ai/explain
class AIExplainRequest(BaseModel):
    subject: Literal["lex Calculation", "risk_band", "threshold", "mitigation"]
    target_id: Optional[UUID] = None
    level: Literal["beginner", "technical", "expert"] = "technical"

class AIExplainResponse(BaseModel):
    explanation: str
    technical_details: Optional[dict]
    related_regulations: list[str]
    confidence: float

# POST /assessments/{id}/ai/suggest-mitigations
class MitigationSuggestionRequest(BaseModel):
    risk_bands: list[str]  # ['high', 'medium']
    affected_roles: Optional[list[UUID]] = None
    include_ppe: bool = True
    include_engineering: bool = True
    include_administrative: bool = True

class MitigationSuggestionResponse(BaseModel):
    mitigations: list[MitigationRecommendation]
    priority_order: list[str]
    estimated_effectiveness: dict[str, float]
```

---

## 5. Prompt Templates to Create

### 5.1 Template Files Structure

```
src/domain/services/prompts/templates/
├── bootstrap_prompt.md
├── review_prompt.md
├── narrative_prompt.md
├── explain_prompt.md
├── mitigation_prompt.md
└── source_detection_prompt.md
```

### 5.2 Template Specifications

#### `bootstrap_prompt.md`
```markdown
# Bootstrap Prompt Template

## System Context
You are an expert HSE consultant specializing in Italian noise risk assessment (D.Lgs. 81/2008).
You are assisting a consulente in setting up a new noise assessment for a company.

## Company Data
- ATECO Codes: {ateco_codes}
- Company Description: {company_description}
- Existing Data: {existing_data}

## Output Format (JSON)
{
  "processes": [...],
  "roles": [...],
  "noise_sources": [...],
  "confidence": {...},
  "missing_data": [...],
  "next_actions": [...]
}

## Safety Rules
- Never invent measured data
- Always flag assumptions
- Request confirmation on critical data
```

#### `narrative_prompt.md`
```markdown
# Narrative Generation Prompt

## System Context
You generate technical narrative text for Italian DVR (Documento di Valutazione Rischi) 
noise sections per D.Lgs. 81/2008 and ISO 9612.

## Assessment Data
{assessment_data}

## Report Structure
1. Premessa
2. Riferimenti aziendali
3. Metodologia
4. Mansioni e processi analizzati
5. Sorgenti di rumore individuate
6. Dati disponibili e origine
7. Calcolo dell'esposizione
8. Confronto con soglie
9. Misure di prevenzione e protezione
10. Programma di miglioramento
11. Conclusioni

## Style Requirements
- Technical formal Italian
- Include references to D.Lgs. 81/2008 articles
- Distinguish between measured/estimated/AI-suggested data
- Maintain audit trail clarity
```

#### `mitigation_prompt.md`
```markdown
# Mitigation Suggestion Prompt

## System Context
You recommend noise mitigation measures per Italian law D.Lgs. 81/2008.

## Risk Data
- LEX,8h levels: {lex_levels}
- Risk bands: {risk_bands}
- Affected roles: {roles}

## Mitigation Hierarchy (Italian law order)
1. Eliminazione rischio
2. Sostituzione
3. Misure tecniche
4. Misure organizzative
5. DPI (protezione individuale)

## Available PPE Types
- Archi anti-rumore (NRR values)
- Cuffie anti-rumore (NRR values)
- Inserti auricolari

## Output Format
{
  "engineer_controls": [...],
  "administrative_controls": [...],
  "ppe_recommendations": [...],
  "priority": [...],
  "effectiveness_estimates": {...}
}
```

---

## 6. AI Agent Responsibilities

### 6.1 Bootstrap Agent
- **Input**: ATECO code(s) + company description (free text)
- **Output**: Suggested processes, roles, noise sources with confidence scores
- **Knowledge Base Integration**: Query PAF noise sources catalog
- **Confirmation Flow**: Present suggestions for user approval before committing

### 6.2 Review Agent
- **Input**: Current assessment data
- **Tasks**:
  - Validate exposure durations match work phases
  - Check for missing critical data
  - Flag inconsistencies (e.g., LEX,8h < individual phase levels)
  - Suggest data quality improvements
- **Output**: Structured review report with issues and suggestions

### 6.3 Narrative Generation Agent
- **Input**: Complete assessment with approved data
- **Tasks**:
  - Generate each section of the DVR noise chapter
  - Apply correct Italian technical terminology
  - Include regulatory references (Art. 181, 185, 188 D.Lgs. 81/2008)
  - Mark data origin (measured/estimated/AI-suggested)
- **Output**: Complete narrative sections ready for DVR integration

### 6.4 Mitigation Suggestion Agent
- **Input**: Risk classification results
- **Tasks**:
  - Map risk bands to required mitigation levels
  - Suggest engineering controls from knowledge base
  - Recommend appropriate PPE with NRR values
  - Prioritize actions by effectiveness/effort ratio
- **Output**: Prioritized mitigation plan with expected risk reduction

### 6.5 Source Detection Agent
- **Input**: Free-text process/machine descriptions
- **Tasks**:
  - Match descriptions to PAF noise source catalog
  - Suggest typical noise levels for unmatched sources
  - Flag when actual measurements are advisable
- **Output**: Linked noise sources with confidence and data quality flags

---

## 7. Tools/Functions to Expose to AI

### 7.1 Noise Calculation Tools

```python
# Exposed to AI as callable functions
class NoiseCalculationTools:
    @tool
    def calculate_lex_8h(self, exposures: list[PhaseExposure]) -> NoiseExposureResult:
        """Calculate LEX,8h per ISO 9612"""
        pass
    
    @tool
    def classify_risk(self, lex_8h: float) -> str:
        """Classify risk band per D.Lgs. 81/2008 Art. 188"""
        pass
    
    @tool
    def estimate_uncertainty(self, origin: ExposureOrigin) -> float:
        """Return uncertainty in dB for data origin type"""
        pass
```

### 7.2 Assessment Context Tools

```python
class AssessmentContextTools:
    @tool
    def get_assessment(self, assessment_id: UUID) -> dict:
        """Get full assessment data"""
        pass
    
    @tool
    def get_ateco_info(self, ateco_code: str) -> dict:
        """Get ATECO code details and typical processes"""
        pass
    
    @tool
    def search_noise_sources(self, query: str, category: str = None) -> list[dict]:
        """Search PAF noise source catalog"""
        pass
    
    @tool
    def get_role_exposures(self, assessment_id: UUID, role_id: UUID) -> list[dict]:
        """Get exposure data for a specific role"""
        pass
```

### 7.3 Knowledge Base Tools

```python
class KnowledgeBaseTools:
    @tool
    def get_typical_noise_level(self, machine_type: str) -> dict:
        """Get typical dB(A) for machine category from PAF data"""
        pass
    
    @tool
    def get_ppe_recommendations(self, lex_8h: float) -> list[dict]:
        """Get recommended DPI for exposure level"""
        pass
    
    @tool
    def get_regulatory_limits(self) -> dict:
        """Get Italian noise exposure limits per D.Lgs. 81/2008"""
        pass
```

---

## 8. LLM Provider Implementation

### 8.1 Abstract Interface

```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self, 
        prompt: str, 
        system: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> LLMResponse:
        pass
    
    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: dict,
        system: str = None
    ) -> dict:
        pass
```

### 8.2 Provider Configuration

```python
# config/llm_config.py
class LLMConfig:
    provider: Literal["openai", "anthropic", "ollama"] = "openai"
    
    openai:
        model: str = "gpt-4o"
        api_key: str
        base_url: str = "https://api.openai.com/v1"
    
    anthropic:
        model: str = "claude-3-5-sonnet-20241022"
        api_key: str
    
    ollama:
        model: str = "glm-4.7:cloud"
        base_url: str = "http://localhost:11434"
```

---

## 9. Phased Implementation Plan

### Phase 3.1: Foundation (Week 1-2)
**Goal**: LLM provider abstraction + basic infrastructure

| Task | File(s) | Deliverable |
|------|---------|-------------|
| Create `LLMProvider` abstract class | `domain/services/llm_provider.py` | Base interface |
| Implement `OpenAIProvider` | `infrastructure/llm/openai_provider.py` | GPT-4o integration |
| Implement `AnthropicProvider` | `infrastructure/llm/anthropic_provider.py` | Claude integration |
| Create `AIOrchestrator` service | `domain/services/ai_orchestrator.py` | Central coordinator |
| Add AI database models | `infrastructure/database/models/ai_interaction.py` | Tables + ORM |
| Create `ai_routes.py` skeleton | `api/routes/ai_routes.py` | Basic endpoints |
| Write base prompt templates | `domain/services/prompts/templates/*.md` | 6 template files |

**Tests**: Unit tests for LLM provider abstraction, mock tests for orchestrator

### Phase 3.2: Bootstrap Agent (Week 3)
**Goal**: AI-guided initial assessment setup

| Task | File(s) | Deliverable |
|------|---------|-------------|
| Implement `BootstrapPromptBuilder` | `domain/services/prompts/bootstrap.py` | Prompt construction |
| Create `/ai/bootstrap` endpoint | `api/routes/ai_routes.py` | POST endpoint |
| Implement bootstrap agent logic | `domain/services/agents/bootstrap_agent.py` | Core logic |
| Integrate PAF noise source search | `infrastructure/external/paf_client.py` | Knowledge base |
| Add suggestion approval workflow | `domain/services/suggestion_manager.py` | Approve/reject flow |
| Create AI suggestion Pydantic schemas | `api/schemas/ai_suggestion.py` | Request/response models |

**API**: `POST /assessments/{id}/ai/bootstrap`  
**Tests**: Integration tests with mock LLM, template rendering tests

### Phase 3.3: Explainability Agent (Week 4)
**Goal**: AI explanations for calculations and risk decisions

| Task | File(s) | Deliverable |
|------|---------|-------------|
| Implement `ExplainPromptBuilder` | `domain/services/prompts/explain.py` | Explanation prompts |
| Create `/ai/explain` endpoint | `api/routes/ai_routes.py` | POST endpoint |
| Build explanation generation logic | `domain/services/agents/explain_agent.py` | Context-aware explanations |
| Add regulatory reference lookup | `domain/services/regulation_lookup.py` | D.Lgs. 81/2008 refs |
| Create multi-level explanation (beginner/technical/expert) | `domain/services/agents/explain_agent.py` | Tiered explanations |

**API**: `POST /assessments/{id}/ai/explain`  
**Tests**: Explanation quality tests, regulatory reference accuracy

### Phase 3.4: Narrative Generation Agent (Week 5-6)
**Goal**: Auto-generate DVR document text

| Task | File(s) | Deliverable |
|------|---------|-------------|
| Implement `NarrativePromptBuilder` | `domain/services/prompts/narrative.py` | Report generation |
| Create `/ai/generate-narrative` endpoint | `api/routes/ai_routes.py` | POST endpoint |
| Build narrative agent with section generation | `domain/services/agents/narrative_agent.py` | Per-section generation |
| Add narrative template customization | `infrastructure/database/models/narrative_template.py` | Customizable templates |
| Implement narrative versioning | `domain/services/narrative_versioning.py` | Track revisions |
| Create `report_generator.py` AI integration | `domain/services/report_generator.py` | Integration with existing |

**API**: `POST /assessments/{id}/ai/generate-narrative`  
**Tests**: Narrative quality tests, regulatory compliance checks

### Phase 3.5: Mitigation Suggestion Agent (Week 7)
**Goal**: AI-powered mitigation recommendations

| Task | File(s) | Deliverable |
|------|---------|-------------|
| Implement `MitigationPromptBuilder` | `domain/services/prompts/mitigation.py` | Recommendation prompts |
| Create `/ai/suggest-mitigations` endpoint | `api/routes/ai_routes.py` | POST endpoint |
| Build PPE database integration | `infrastructure/external/ppe_catalog.py` | DPI NRR values |
| Implement risk-to-mitigation mapping | `domain/services/risk_mitigation_mapper.py` | Business logic |
| Create mitigation effectiveness estimation | `domain/services/effectiveness_estimator.py` | Expected risk reduction |

**API**: `POST /assessments/{id}/ai/suggest-mitigations`  
**Tests**: Mitigation appropriateness tests per D.Lgs. 81/2008 hierarchy

### Phase 3.6: Review Agent + Integration (Week 8)
**Goal**: Data review + full system integration

| Task | File(s) | Deliverable |
|------|---------|-------------|
| Implement `ReviewPromptBuilder` | `domain/services/prompts/review.py` | Review prompts |
| Create `/ai/review` endpoint | `api/routes/ai_routes.py` | POST endpoint |
| Build review agent with validation logic | `domain/services/agents/review_agent.py` | Data consistency checks |
| Add interaction history logging | `infrastructure/repositories/ai_interaction_repo.py` | Audit trail |
| Implement suggestion bulk actions | `domain/services/suggestion_manager.py` | Batch approve/reject |
| Create comprehensive API tests | `tests/api/test_ai_routes.py` | Full integration tests |
| Performance optimization | `domain/services/ai_cache.py` | Response caching |

**APIs**: 
- `POST /assessments/{id}/ai/review`
- `GET /assessments/{id}/ai/suggestions`
- `POST /assessments/{id}/ai/suggestions/{id}/approve`

---

## 10. Safety & Compliance Rules

### 10.1 AI Safety Constraints
- **Never invent measured data**: All AI-suggested data must be marked as `AI_SUGGESTED` origin
- **Explicit assumptions**: AI must always state assumptions made
- **Human-in-the-loop**: Critical decisions require consultant approval
- **Audit trail**: Every AI interaction logged with full prompt/response
- **Confidence scoring**: All suggestions include confidence scores
- **Fallback mode**: System usable without AI (cached/local data)

### 10.2 Italian Regulatory Compliance
- All narrative references to D.Lgs. 81/2008 must be accurate
- PPE recommendations must include correct NRR values
- Risk classifications must match Art. 188 thresholds:
  - 80 dB(A): Under evaluation
  - 85 dB(A): Value action lower
  - 87 dB(A): Value action upper
  - 87 dB(A): Exposure limit value
- LEX,8h calculations must reference ISO 9612

### 10.3 Data Quality Labels
```
AI_SUGGESTED → consultant can APPROVE → becomes VALIDATED
AI_SUGGESTED → consultant can MODIFY → becomes CONSULTANT_ENTERED  
AI_SUGGESTED → consultant can REJECT → discarded
```

---

## 11. Configuration

### 11.1 Environment Variables
```bash
# LLM Provider
LLM_PROVIDER=openai  # or anthropic, ollama
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Local LLM fallback
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=glm-4.7:cloud

# AI Behavior
AI_MAX_TOKENS=4096
AI_TEMPERATURE=0.7
AI_CONFIDENCE_THRESHOLD=0.8
AI_CACHE_ENABLED=true
```

### 11.2 Feature Flags
```python
AI_BOOTSTRAP_ENABLED=true
AI_REVIEW_ENABLED=true
AI_NARRATIVE_ENABLED=true
AI_MITIGATION_ENABLED=true
AI_SOURCE_DETECTION_ENABLED=true
```

---

## 12. Testing Strategy

### 12.1 Unit Tests
- LLM provider abstraction (mock provider)
- Prompt template rendering
- Tool function output validation
- Schema validation

### 12.2 Integration Tests
- Full AI interaction flows with mock LLM
- Database model persistence
- API endpoint contracts

### 12.3 Compliance Tests
- Narrative output matches D.Lgs. 81/2008 format
- Mitigation hierarchy respected
- Risk band calculations verified

---

## 13. Dependencies for Phase 3

```python
# New dependencies to add
openai>=1.12.0
anthropic>=0.21.0
httpx>=0.27.0  # For async LLM calls
jinja2>=3.1.0  # For prompt templating
pydantic-settings>=2.0.0  # For config management

# Existing dependencies
fastapi>=0.109.0
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
pydantic>=2.5.0
```

---

## 14. File Manifest for Phase 3

### New Files
```
src/domain/services/
├── ai_orchestrator.py
├── llm_provider.py
├── agents/
│   ├── __init__.py
│   ├── bootstrap_agent.py
│   ├── review_agent.py
│   ├── narrative_agent.py
│   ├── explain_agent.py
│   └── mitigation_agent.py
├── prompts/
│   ├── __init__.py
│   ├── bootstrap.py
│   ├── review.py
│   ├── narrative.py
│   ├── explain.py
│   ├── mitigation.py
│   └── templates/
│       ├── bootstrap_prompt.md
│       ├── review_prompt.md
│       ├── narrative_prompt.md
│       ├── explain_prompt.md
│       ├── mitigation_prompt.md
│       └── source_detection_prompt.md
├── tools/
│   ├── __init__.py
│   ├── noise_tools.py
│   ├── assessment_tools.py
│   └── knowledge_base_tools.py
└── suggestion_manager.py

src/infrastructure/
├── llm/
│   ├── __init__.py
│   ├── base.py
│   ├── openai_provider.py
│   ├── anthropic_provider.py
│   └── ollama_provider.py
├── database/
│   └── models/
│       ├── ai_interaction.py
│       ├── ai_suggestion.py
│       └── narrative_template.py
└── external/
    ├── ppe_catalog.py
    └── regulation_db.py

src/api/
├── routes/
│   └── ai_routes.py
└── schemas/
    ├── ai_suggestion.py
    ├── bootstrap.py
    ├── explain.py
    ├── narrative.py
    └── mitigation.py

tests/
├── domain/services/
│   ├── test_ai_orchestrator.py
│   ├── test_bootstrap_agent.py
│   ├── test_narrative_agent.py
│   └── test_llm_provider.py
└── api/
    └── test_ai_routes.py
```

### Files to Modify
```
src/domain/services/report_generator.py  # Add AI narrative integration
src/api/routes/assessments.py              # Add AI-related methods
src/bootstrap/config.py                   # Add LLM config
src/infrastructure/database/models/       # Add AI-related fields
```

---

## 15. Success Criteria

| Criterion | Target |
|-----------|--------|
| Bootstrap generates valid suggestions | >80% acceptance rate |
| Narrative generation time | <30 seconds per section |
| Mitigation recommendations | 100% compliant with hierarchy |
| Explainability accuracy | Verified by HSE expert |
| AI interaction logging | 100% of interactions logged |
| System degradability | Fully functional without AI |

---

## 16. Next Steps After Phase 3

1. **Phase 4**: Real-time audio analysis integration (microphone input)
2. **Phase 5**: Multi-tenant shared knowledge base
3. **Phase 6**: Advanced CAD/acoustic simulation
4. **Phase 7**: Mobile app for field data collection
