# STRUCTURED PLAN - PHASE 1 (Foundations)

## Metadata

| Campo | Valore |
|-------|--------|
| **Fase** | 1 - Foundations |
| **Stato** | APPROVATO per BUILD |
| **Modello** | minimax-m2.7:cloud |
| **Data** | 2026-04-08 |
| **Branch Target** | feature/project-setup, feature/db-schema-v1, feature/schema-fixes, feature/catalog-ateco, feature/knowledge-base, feature/api-bootstrap |

---

## 1. MACRO-TASK 1.1: Setup Progetto

**Tempo stimato**: 1 ora  
**Branch**: `feature/project-setup`  
**Dipendenze**: Nessuna

### Sub-task dettagliati:

#### 1.1.1: Inizializza repository Git
```bash
cd /workspace
git init
git config user.name "MARS Team"
git config user.email "team@mars-software.it"
```
**Criterio**: `.git/config` esiste con user.name configurato

#### 1.1.2: Crea struttura cartelle
```bash
mkdir -p src/{api/{routes,schemas},domain/{entities,services,value_objects},infrastructure/{database,external,cache},application/use_cases,bootstrap}
mkdir -p tests/{unit,integration}
mkdir -p migrations/versions
mkdir -p data/{ateco,knowledge_base}
mkdir -p docs scripts
```
**Criterio**: 15+ directory create

#### 1.1.3: Crea .gitignore
```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
ENV/
env/
.pytest_cache/
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Environment
.env
.env.local

# Database
*.db
*.sqlite3
*.sql.gz

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Alembic
alembic.ini
alembic/
migrations/*.log

# Data files
data/*.xlsx
data/*.json
!data/ateco/.gitkeep
!data/knowledge_base/.gitkeep
EOF
```
**Criterio**: File .gitignore creato con contenuto valido

#### 1.1.4: Crea pyproject.toml
```toml
[project]
name = "mars-noise-module"
version = "0.1.0"
description = "Modulo DVR Rischio Rumore per MARS"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "PROPRIETARY" }
authors = [
    { name = "MARS Team", email = "team@mars-software.it" }
]
keywords = ["noise", "risk-assessment", "dvr", "hse", "italy"]
classifiers = [
    "Development Status :: 2 - Pre-Alpha",
    "Intended Audience :: Professionals",
    "Programming Language :: Python :: 3.11",
]

dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "numpy>=1.26.0",
    "scipy>=1.12.0",
    "python-multipart>=0.0.20",
    "jinja2>=3.1.0",
    "httpx>=0.28.0",
    "redis>=5.2.0",
    "pydantic[email]>=2.10.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
    "pre-commit>=4.0.0",
]
ai = [
    "openai>=1.58.0",
    "anthropic>=0.38.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```
**Criterio**: pyproject.toml valido, pass `ruff check pyproject.toml`

#### 1.1.5: Configura virtual environment
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows
pip install --upgrade pip
```
**Criterio**: .venv esiste, pip funziona

#### 1.1.6: Installa dipendenze base
```bash
pip install fastapi uvicorn pydantic pydantic-settings sqlalchemy asyncpg alembic numpy scipy python-multipart jinja2 httpx redis
```
**Criterio**: `pip list` mostra tutte le dipendenze installate

#### 1.1.7: Crea src/__init__.py e sottopacchetti
```bash
touch src/__init__.py
touch src/api/__init__.py
touch src/api/routes/__init__.py
touch src/api/schemas/__init__.py
touch src/domain/__init__.py
touch src/domain/entities/__init__.py
touch src/domain/services/__init__.py
touch src/domain/value_objects/__init__.py
touch src/infrastructure/__init__.py
touch src/infrastructure/database/__init__.py
touch src/infrastructure/external/__init__.py
touch src/infrastructure/cache/__init__.py
touch src/application/__init__.py
touch src/application/use_cases/__init__.py
touch src/bootstrap/__init__.py
```
**Criterio**: Tutti i file __init__.py esistono

#### 1.1.8: Crea .env.example
```bash
cat > .env.example << 'EOF'
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mars_noise
REDIS_URL=redis://localhost:6379/0

# AI
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# App
APP_ENV=development
LOG_LEVEL=INFO
API_V1_PREFIX=/api/v1/noise

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
EOF
```
**Criterio**: .env.example creato

#### 1.1.9: Commit iniziale
```bash
git add -A
git commit -m "feat: initial project setup - Phase 1.1

- Add project structure (15+ directories)
- Add pyproject.toml with all dependencies
- Add .gitignore, .env.example
- Add __init__.py markers for all packages"
```
**Criterio**: Git log mostra il commit iniziale

---

## 2. MACRO-TASK 1.2: Database Schema

**Tempo stimato**: 4 ore  
**Branch**: `feature/db-schema-v1`  
**Dipendenze**: 1.1 completato

### Sub-task dettagliati:

#### 1.2.1: Configura Alembic
```bash
alembic init migrations
```
**Criterio**: alembic.ini e migrations/ existono

#### 1.2.2: Crea env.py per async SQLAlchemy
```python
# migrations/env.py (OVERWRITE)
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from src.infrastructure.database.base import Base
from src.infrastructure.database.models import *  # noqa

target_metadata = Base.metadata

async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

asyncio.run(run_async_migrations())
```
**Criterio**: `python -c "from migrations.env import run_async_migrations; print('OK')"`

#### 1.2.3: Crea base.py con metadata
```python
# src/infrastructure/database/base.py
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
```
**Criterio**: Importabile

#### 1.2.4: Crea file con ENUM types
```python
# src/infrastructure/database/enums.py
from sqlalchemy import TypeDecorator, String
import enum

class ValueOrigin(enum.Enum):
    measured = "measured"
    calculated = "calculated"
    estimated = "estimated"
    imported = "imported"
    ai_suggested = "ai_suggested"
    validated = "validated"
    default_value = "default_value"

class ThresholdBand(enum.Enum):
    negligible = "negligible"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class ActionType(enum.Enum):
    administrative = "administrative"
    technical = "technical"
    ppe = "ppe"
    medical = "medical"
    training = "training"
    engineering = "engineering"

class EntityStatus(enum.Enum):
    active = "active"
    inactive = "inactive"
    archived = "archived"
```
**Criterio**: Importabile da Python

#### 1.2.5: Crea tabella company
```python
# src/infrastructure/database/models/company.py
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.infrastructure.database.base import Base
from src.infrastructure.database.enums import EntityStatus

class Company(Base):
    __tablename__ = "company"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ateco_primary_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[EntityStatus] = mapped_column(
        String(20), default=EntityStatus.active.value
    )
```
**Criterio**: `python -c "from src.infrastructure.database.models.company import Company; print(Company.__tablename__)`

#### 1.2.6-1.2.14: Crea tabelle rimanenti
Seguire pattern 1.2.5 per:
- unit_site (FK company)
- process (FK company)
- work_phase (FK process)
- job_role (FK company)
- machine_asset (FK company)
- noise_source_catalog (no FK)
- role_phase_exposure (FK job_role, FK work_phase, FK noise_source_catalog)
- measurement_session (FK noise_assessment)
- measurement_point (FK measurement_session)
- noise_assessment (FK company)
- noise_assessment_result (FK noise_assessment, FK job_role)
- mitigation_action (FK noise_assessment)

**Criterio**: Tutte le tabelle importabili

#### 1.2.15: Crea indici performance
```python
# Add after table definitions in each model file
__table_args__ = (
    Index("idx_noise_assessment_result_lex", "lex_8h"),
    Index("idx_assessment_version", "id", "version"),
    Index("idx_noise_source_catalog_category", "category"),
)
```
**Criterio**: Query plan mostra utilizzo indici

#### 1.2.16: Crea trigger audit trail
```sql
-- migrations/versions/001_initial_schema.sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_company_updated_at
    BEFORE UPDATE ON company
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```
**Criterio**: UPDATE triggers updated_at automatically

---

## 3. MACRO-TASK 1.3: Schema Fixes

**Tempo stimato**: 2 ore  
**Branch**: `feature/schema-fixes`  
**Dipendenze**: 1.2 completato

### Sub-task dettagliati:

#### 1.3.1: Aggiungi LCpeak a noise_assessment_result
```python
# Add to noise_assessment_result model
lcpeak_db_c: Mapped[float | None] = mapped_column(
    Numeric(5, 1), nullable=True, comment="Peak C-weighted level in dB(C)"
)
```
**Criterio**: Colonna esiste con comment

#### 1.3.2: Aggiungi lex_weekly
```python
# Add to noise_assessment_result model
lex_weekly_db_a: Mapped[float | None] = mapped_column(
    Numeric(5, 1), nullable=True, comment="Weekly LEX in dB(A)"
)
```
**Criterio**: Colonna esiste

#### 1.3.3: Aggiungi exposure_type
```python
# Add to role_phase_exposure model
exposure_type: Mapped[ValueOrigin] = mapped_column(
    String(20), nullable=False, default=ValueOrigin.estimated.value
)
```
**Criterio**: Valori validi: measured, calculated, estimated

#### 1.3.4-1.3.10: Aggiungi altri campi mancanti
- workers_count_exposed: INT
- representative_workers: ARRAY[TEXT]
- measurement_protocol: VARCHAR (es. "UNI EN ISO 9612:2011")
- instrument_class: VARCHAR(5) (es. "I" o "II")
- uncertainty_value: DECIMAL(4,2)
- background_noise_db_a: DECIMAL(5,1)

**Criterio**: Tutte le colonne importabili

#### 1.3.11: Crea entità dpi_hearing_protection
```python
# src/infrastructure/database/models/dpi_hearing_protection.py
class DPIHearingProtection(Base):
    __tablename__ = "dpi_hearing_protection"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(255), nullable=False)
    nrr_db: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
    snr_db: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
    certification: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```
**Criterio**: Importabile

#### 1.3.12: Crea entità health_surveillance
```python
# src/infrastructure/database/models/health_surveillance.py
class HealthSurveillance(Base):
    __tablename__ = "health_surveillance"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    exam_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    exam_type: Mapped[str] = mapped_column(String(100), nullable=False)
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
```
**Criterio**: Importabile

#### 1.3.13: Crea entità training_session
```python
# src/infrastructure/database/models/training_session.py
class TrainingSession(Base):
    __tablename__ = "training_session"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    attendees: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    duration_hours: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
```
**Criterio**: Importabile

---

## 4. MACRO-TASK 1.4: Catalogo ATECO

**Tempo stimato**: 2 ore  
**Branch**: `feature/catalog-ateco`  
**Dipendenze**: 1.2 completato

### Sub-task dettagliati:

#### 1.4.1: Download ATECO ISTAT
```bash
mkdir -p data/ateco
# Download from ISTAT or use provided XLSX
curl -L "https://www.istat.it/storage/codici-unita-amministrative/ATECO-2007.xlsx" \
    -o data/ateco/ateco2007.xlsx
```
**Criterio**: File scaricato (~2MB)

#### 1.4.2: Crea script conversione
```python
# scripts/convert_ateco.py
import json
import openpyxl
from pathlib import Path

def convert_ateco(xlsx_path: str, output_path: str):
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    
    ateco_data = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0]:
            ateco_data.append({
                "codice": str(row[0]),
                "descrizione": row[1],
                "categoria": row[2] if len(row) > 2 else None,
                "sezione": row[3] if len(row) > 3 else None,
            })
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ateco_data, f, ensure_ascii=False, indent=2)
    
    return len(ateco_data)

if __name__ == "__main__":
    count = convert_ateco(
        "data/ateco/ateco2007.xlsx",
        "data/ateco/ateco2007.json"
    )
    print(f"Convertiti {count} record ATECO")
```
**Criterio**: Script eseguibile senza errori

#### 1.4.3: Genera JSON e hash
```bash
python scripts/convert_ateco.py
sha256sum data/ateco/ateco2007.json > data/ateco/ateco2007.sha256
```
**Criterio**: JSON valido (~800KB), hash generato

#### 1.4.4: Crea migration seed ATECO
```python
# migrations/versions/002_seed_ateco.py
from alembic import op
import json
from pathlib import Path

def load_ateco_data():
    with open("data/ateco/ateco2007.json", "r") as f:
        return json.load(f)

def upgrade():
    data = load_ateco_data()
    for item in data:
        op.execute(
            f"""
            INSERT INTO ateco_catalog (code, description, category, section)
            VALUES ('{item['codice']}', '{item['descrizione']}', 
                    '{item.get('categoria', '')}', '{item.get('sezione', '')}')
            ON CONFLICT (code) DO NOTHING
            """
        )

def downgrade():
    op.execute("TRUNCATE TABLE ateco_catalog")
```
**Criterio**: Migration.apply() popola tabella

#### 1.4.5: Verifica seed
```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM ateco_catalog;"
```
**Atteso**: ~6,300+ righe

---

## 5. MACRO-TASK 1.5: Knowledge Base Rumore

**Tempo stimato**: 3 ore  
**Branch**: `feature/knowledge-base`  
**Dipendenze**: 1.3 completato

### Sub-task dettagliati:

#### 1.5.1: Crea modello noise_source_catalog
```python
# src/domain/entities/noise_source.py
from dataclasses import dataclass
from datetime import date
from uuid import UUID

@dataclass
class NoiseSourceEntry:
    id: UUID
    marca: str
    modello: str
    tipologia: str
    alimentazione: str
    laeq_min: float | None
    laeq_max: float | None
    laeq_typical: float | None
    lcpeak: float | None
    fonte: str
    url_fonte: str | None
    data_aggiornamento: date
    disclaimer: str
```
**Criterio**: Dataclass importabile

#### 1.5.2: Crea script estrazione PAF (prototype)
```python
# scripts/paf_scraper.py
"""
Prototype per estrazione dati PAF.
用法: python scripts/paf_scraper.py --tipologia "Smerigliatrici" --output data/knowledge_base/smerigliatrici.json
"""
import argparse
import json
import time
import httpx
from pathlib import Path

PAF_BASE_URL = "https://www.portaleagentifisici.it"

async def scrape_page(tipologia: str, page: int = 0) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{PAF_BASE_URL}/fo_rumore_list_macchinari.php"
        params = {"lg": "IT", "page": page}
        if tipologia:
            params["tipologia"] = tipologia
        
        response = await client.get(url, params=params)
        response.raise_for_status()
        
        # Parse HTML e estrai dati
        # (implementazione completa dipende dalla struttura HTML)
        return []

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tipologia", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    
    all_data = []
    for page in range(50):  # Max 50 pagine
        data = await scrape_page(args.tipologia, page)
        if not data:
            break
        all_data.extend(data)
        time.sleep(1)  # Rate limiting
        print(f"Pagina {page}: {len(data)} records")
    
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    print(f"Total: {len(all_data)} records salvati in {args.output}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```
**Criterio**: Script sintatticamente valido

#### 1.5.3-1.5.5: Batch processing e mapping
```python
# scripts/paf_batch.py
"""
Esegue batch extraction per tutte le tipologie.
"""
import asyncio
import json
from pathlib import Path
from scripts.paf_scraper import scrape_page

TIPOLOGIE = [
    "Smerigliatrici",
    "Trapani",
    "Martelli perforatori",
    # ... 50+ categorie
]

async def main():
    all_sources = []
    for tipologia in TIPOLOGIE:
        print(f"Processing: {tipologia}")
        data = await scrape_page(tipologia)
        all_sources.extend(data)
        await asyncio.sleep(2)  # Rate limiting
    
    output = Path("data/knowledge_base/kb_2026-04-08.json")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_sources, f, ensure_ascii=False, indent=2)
    
    print(f"Completato: {len(all_sources)} sorgenti")

if __name__ == "__main__":
    asyncio.run(main())
```
**Criterio**: Esegue senza errori

#### 1.5.6: Crea snapshot versionato
```bash
mkdir -p data/knowledge_base/snapshots
cp data/knowledge_base/kb_2026-04-08.json \
   data/knowledge_base/snapshots/kb_2026-04-08_v1.json
sha256sum data/knowledge_base/kb_2026-04-08.json > \
         data/knowledge_base/snapshots/kb_2026-04-08_v1.sha256
```
**Criterio**: Snapshot creato

#### 1.5.7: Seed PostgreSQL
```python
# migrations/versions/003_seed_noise_sources.py
from alembic import op
import json

def load_sources():
    with open("data/knowledge_base/kb_2026-04-08.json") as f:
        return json.load(f)

def upgrade():
    sources = load_sources()
    for src in sources:
        op.execute(f"""
            INSERT INTO noise_source_catalog (
                marca, modello, tipologia, alimentazione,
                laeq_min, laeq_max, laeq_typical,
                fonte, url_fonte, data_aggiornamento, disclaimer
            ) VALUES (
                '{src['marca']}', '{src['modello']}', '{src['tipologia']}',
                '{src['alimentazione']}',
                {src.get('laeq_min')}, {src.get('laeq_max')},
                {src.get('laeq_typical')},
                'PAF', '{src.get('url', '')}', '2026-04-08',
                'Dati per finalità prevenzione sicurezza lavoro - PAF Portale Agenti Fisici'
            )
        """)
```
**Criterio**: Popola tabella

---

## 6. MACRO-TASK 1.6: API Bootstrap

**Tempo stimato**: 3 ore  
**Branch**: `feature/api-bootstrap`  
**Dipendenze**: 1.1 completato

### Sub-task dettagliati:

#### 1.6.1: Crea FastAPI app main
```python
# src/bootstrap/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.api.routes import assessments, health
from src.bootstrap.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    pass

app = FastAPI(
    title="MARS Noise Module API",
    description="Modulo DVR Rischio Rumore",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(assessments.router, prefix=settings.api_v1_prefix, tags=["Assessments"])

@app.get("/")
async def root():
    return {"message": "MARS Noise Module API", "version": "0.1.0"}
```
**Criterio**: App importabile

#### 1.6.2: Crea config
```python
# src/bootstrap/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/mars_noise"
    redis_url: str = "redis://localhost:6379/0"
    app_env: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1/noise"
    cors_origins: list[str] = ["http://localhost:3000"]
    
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```
**Criterio**: Settings importabile

#### 1.6.3: Crea schema Pydantic AssessmentCreate
```python
# src/api/schemas/assessment.py
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

class AssessmentCreate(BaseModel):
    company_id: UUID
    ateco_code: str = Field(..., pattern=r"^[0-9]{2}\.[0-9]{2}\.[0-9]{2}$")
    description: Optional[str] = None

class AssessmentResponse(BaseModel):
    id: UUID
    company_id: UUID
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
```
**Criterio**: Schema importabile

#### 1.6.4: Implementa CRUD assessments
```python
# src/api/routes/assessments.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from src.api.schemas.assessment import AssessmentCreate, AssessmentResponse
from src.infrastructure.database.session import get_db
from src.application.use_cases.assessment import AssessmentUseCases

router = APIRouter()

@router.post("/", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    data: AssessmentCreate,
    db: AsyncSession = Depends(get_db),
):
    use_cases = AssessmentUseCases(db)
    assessment = await use_cases.create(data)
    return assessment

@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    use_cases = AssessmentUseCases(db)
    assessment = await use_cases.get_by_id(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment
```
**Criterio**: Endpoint funziona con 201 Created

#### 1.6.5: Implementa bootstrap
```python
# src/application/use_cases/assessment.py
class AssessmentUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, data: AssessmentCreate) -> NoiseAssessment:
        assessment = NoiseAssessment(
            company_id=data.company_id,
            status="draft",
            version=1,
        )
        self.db.add(assessment)
        await self.db.commit()
        await self.db.refresh(assessment)
        return assessment
    
    async def bootstrap(self, assessment_id: UUID, ateco_code: str):
        # AI-powered bootstrap logic
        pass
```
**Criterio**: Create funziona

#### 1.6.6: Test API
```bash
uvicorn src.bootstrap.main:app --reload --port 8000 &
sleep 3
curl -X POST http://localhost:8000/api/v1/noise/assessments \
    -H "Content-Type: application/json" \
    -d '{"company_id": "550e8400-e29b-41d4-a716-446655440000", "ateco_code": "25.11.00"}'
```
**Atteso**: 201 Created con JSON

---

## Dipendenze Tra Macro-task

```
1.1 (Setup)
  │
  ├── 1.2 (Schema DB) ──► 1.3 (Schema Fixes)
  │                          │
  │                          ├── 1.4 (ATECO)
  │                          │     │
  │                          │     └── 1.5 (Knowledge Base)
  │                          │
  └── 1.6 (API Bootstrap)
```

---

## Criteri di Accettazione Complessivi

| # | Criterio | Verifica |
|---|----------|----------|
| 1 | Git repository inizializzato | `git log` mostra commit |
| 2 | 15+ directory create | `find . -type d` |
| 3 | pyproject.toml valido | `ruff check pyproject.toml` |
| 4 | Tutte le 15+ tabelle importabili | `python -c "from src.infrastructure.database.models import *"` |
| 5 | ENUM 4 tipi importabili | `python -c "from src.infrastructure.database.enums import *"` |
| 6 | Indici creati | `\d noise_assessment_result` in psql |
| 7 | ATECO seed: 6300+ rows | `SELECT COUNT(*) FROM ateco_catalog` |
| 8 | KB snapshot esiste | `ls data/knowledge_base/snapshots/` |
| 9 | API risponde su /health | `curl localhost:8000/health` |
| 10 | POST /assessments crea record | `curl POST ...` risponde 201 |

---

## Risk Assessment

| Rischio | Gravità | Probabilità | Mitigazione |
|---------|---------|-------------|-------------|
| Dipendenze Python non compatibili | Alta | Media | Verifica compatibility matrix |
| Alembic migration fallisce | Alta | Bassa | Test in ambiente dev prima |
| ATECO XLSX formato cambia | Media | Bassa | Version pinning, backup local |
| PAF rate limiting blocks scraping | Alta | Alta | Throttle 2sec, retry with backoff |
| API startup slow | Media | Media | Add startup event logging |

---

**Documento creato**: 2026-04-08  
**Stato**: Ready for BUILD execution
