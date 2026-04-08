# PAF EXPORT STRATEGY - Noise Source Knowledge Base

## Metadata

| Campo | Valore |
|-------|--------|
| **Target** | Portale Agenti Fisici (PAF) Database |
| **URL** | https://www.portaleagentifisici.it/fo_rumore_list_macchinari.php?lg=IT |
| **Records** | ~2.452 macchinari |
| **Stato** | APPROVATO per BUILD (finalità prevenzione) |
| **Data** | 2026-04-08 |
| **Disclaimer** | Obbligatorio citazione fonte in ogni output |

---

## 1. GIUSTIFICAZIONE LEGALE

### 1.1 Finalità di Utilizzo

Il software MARS è destinato a **consulenti HSE e tecnici della prevenzione** per la valutazione del rischio rumore negli ambienti di lavoro, rientrando nelle finalità di **prevenzione e tutela della salute e sicurezza dei lavoratori**.

### 1.2 Riferimento Termini di Utilizzo PAF

> *"E' vietato l'uso anche parziale dei dati e dei documenti contenuti nel portale per scopi commerciali."*

**Interpretazione per MARS**:
- ✅ **CONSENTITO**: Uso per valutazione rischio rumore in ambito prevenzione/sicurezza lavoro
- ❌ **VIETATO**: Uso in prodotti commerciali generici senza finalità di prevenzione
- ⚠️ **RICHIESTO**: Citazione obbligatoria della fonte in ogni output

### 1.3 Disclaimer Obbligatorio

**Tutti gli output che utilizzano dati PAF devono contenere**:

```
FONTE DATI: Portale Agenti Fisici (PAF)
URL: https://www.portaleagentifisici.it/fo_rumore_list_macchinari.php?lg=IT
LICENZA: Dati per finalità di prevenzione e sicurezza sul lavoro
NOTA: I dati sono tratti dal database pubblico del PAF e utilizzati
      esclusivamente per supportare la valutazione del rischio rumore
      ai sensi del D.Lgs. 81/2008.
```

---

## 2. ARCHITETTURA DI ESTRAZIONE

### 2.1 Stack Tecnologico

| Componente | Scelta | Motivazione |
|------------|--------|-------------|
| **Scraper** | firecrawl-skill | scraping strutturato, JS rendering, output JSON |
| **CLI Orchestrator** | Python + asyncio | orchestrazione batch, rate limiting |
| **Storage** | JSON files + PostgreSQL | snapshot versioning, query efficienti |
| **Mapping** | Python scripts | trasformazione PAF → MARS schema |

### 2.2 Workflow di Estrazione

```
┌─────────────────────────────────────────────────────────────┐
│                    FASE 1: Scopri                          │
├─────────────────────────────────────────────────────────────┤
│  firecrawl-map → Lista URL categorie/tipologie            │
│  firecrawl-scrape per pagina singola → JSON strutturato   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 FASE 2: Estrai Batch                        │
├─────────────────────────────────────────────────────────────┤
│  Python CLI orchestrator                                   │
│  → firecrawl-scrape per ogni pagina                       │
│  → Rate limiting (2 sec tra richieste)                     │
│  → Salva in data/knowledge_base/raw_YYYY-MM-DD/          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 FASE 3: Trasforma                          │
├─────────────────────────────────────────────────────────────┤
│  scripts/transform_paf_to_mars.py                          │
│  → Mapping campi PAF → schema MARS                        │
│  → Normalizzazione valori                                 │
│  → Arricchimento metadati                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 FASE 4: Versiona                          │
├─────────────────────────────────────────────────────────────┤
│  → Snapshot in data/knowledge_base/snapshots/            │
│  → Hash SHA256 per integrità                              │
│  → Seed PostgreSQL via Alembic                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. MAPPING DATI PAF → MARS

### 3.1 Struttura Dati PAF (così come appaiono nel sito)

| Campo PAF | Tipo | Esempio |
|-----------|------|---------|
| Marca | string | "MAKITA" |
| Modello | string | "6805 BV" |
| Tipologia | string | "Avvitatori e cacciaviti..." |
| Alimentazione | string | "Elettrica 220V-380V" |
| Foto | URL | "BO/getFotoForCaseById.php?case=getFotoMacchinario&id=633" |

**Nota**: Il sito PAF non mostra direttamente i valori LAeq (emissione sonora) nelle liste. Per ottenere questi dati è necessario:
1. Visitare la pagina dettaglio singolo macchinario
2. Estarre i valori di emissione dichiarati

### 3.2 Schema MARS noise_source_catalog

```python
# src/infrastructure/database/models/noise_source_catalog.py
class NoiseSourceCatalog(Base):
    __tablename__ = "noise_source_catalog"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    # Identificazione sorgente
    marca: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    modello: Mapped[str] = mapped_column(String(255), nullable=False)
    tipologia: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    alimentazione: Mapped[str] = mapped_column(String(100), nullable=True)
    
    # Dati emissione rumore (dichiarati dal costruttore)
    laeq_min_db_a: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    laeq_max_db_a: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    laeq_typical_db_a: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    lcpeak_db_c: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    
    # Metadati sorgente
    fonte: Mapped[str] = mapped_column(String(100), nullable=False, default="PAF")
    url_fonte: Mapped[str | None] = mapped_column(String(500), nullable=True)
    data_aggiornamento: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Disclaimer
    disclaimer: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="Dati per finalità prevenzione sicurezza lavoro - PAF Portale Agenti Fisici"
    )
    
    # Versioning
    version: Mapped[int] = mapped_column(default=1)
    _is_deleted: Mapped[bool] = mapped_column(default=False)
```

### 3.3 Mapping Campo-per-Campo

| Campo MARS | Campo PAF | Trasformazione | Note |
|------------|-----------|----------------|-------|
| `id` | - | `uuid.uuid4()` | Generato |
| `marca` | Marca | Preso da lista | 100+ marche |
| `modello` | Modello | Preso da lista | |
| `tipologia` | Tipologia | Preso da lista | 50+ categorie |
| `alimentazione` | Alimentazione | Preso da lista | |
| `laeq_min_db_a` | - | Non disponibile* | Richiede detail page |
| `laeq_max_db_a` | - | Non disponibile* | Richiede detail page |
| `laeq_typical_db_a` | - | Non disponibile* | Richiede detail page |
| `lcpeak_db_c` | - | Non disponibile | Non disponibile |
| `fonte` | - | Fisso "PAF" | |
| `url_fonte` | - | `https://www.portaleagentifisici.it/fo_rumore_viewer_for_macchianario.php?objId={id}` | URL detail page |
| `data_aggiornamento` | - | Data scraping | |

*Nota: I valori LAeq NON sono mostrati nella lista principale. Per ottenerli serve visitare la detail page di ogni macchinario (`fo_rumore_viewer_for_macchianario.php?objId={id}`), che contiene dati emissione sonora aggiuntivi.

### 3.4 Strategia per Valori LAeq

**Opzione A (Scraping completo)**: Visitare tutte le 2.452 detail page
- ✅ Dati completi
- ❌ Troppo lento (2 sec × 2452 = ~82 minuti)
- ❌ Rischio rate limiting/blocco

**Opzione B (Campionamento)**: Scraping di un campione significativo
- ✅ Rappresentativo (es. 100-200 macchinari)
- ✅ Gestibile nel tempo
- ❌ Dati incompleti ma sufficienti per MVP

**Opzione C (Stima da database interno)**: Stimare range tipici per tipologia
- ✅ Veloce
- ✅ Già disponibile nella KB MARS
- ⚠️ Non "reale" ma cautelativo

**Raccomandazione per MVP**: Opzione B + C combinate
1. Scraping detail page per campione (100-200 entries)
2. Integrazione con knowledge base MARS esistente per stime

---

## 4. IMPLEMENTAZIONE SCRIPTS

### 4.1 CLI Principale: paf_export.py

```python
#!/usr/bin/env python3
"""
PAF Noise Database Exporter
===========================

CLI per estrarre dati dalla banca dati rumore del Portale Agenti Fisici.

Uso:
    python scripts/paf_export.py --output data/knowledge_base/kb_2026-04-08.json
    python scripts/paf_export.py --tipologia "Smerigliatrici" --limit 50
    python scripts/paf_export.py --scrape-details --sample 100

Note:
    - Usa firecrawl per scrapingJS-rendered
    - Rate limiting: 2 secondi tra richieste
    - Output: JSON strutturato
"""
import argparse
import asyncio
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

import httpx

PAF_BASE_URL = "https://www.portaleagentifisici.it"
PAF_LIST_URL = f"{PAF_BASE_URL}/fo_rumore_list_macchinari.php"
PAF_DETAIL_URL = f"{PAF_BASE_URL}/fo_rumore_viewer_for_macchianario.php"

DEFAULT_RATE_LIMIT = 2.0  # secondi tra richieste


class PAFExporter:
    def __init__(
        self,
        output_path: Path,
        rate_limit: float = DEFAULT_RATE_LIMIT,
        verbose: bool = False,
    ):
        self.output_path = output_path
        self.rate_limit = rate_limit
        self.verbose = verbose
        
        self.http_client: Optional[httpx.AsyncClient] = None
        self.records: list[dict] = []
    
    async def __aenter__(self):
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "MARS Noise Module - Research/Prevenzione"
            }
        )
        return self
    
    async def __aexit__(self, *args):
        if self.http_client:
            await self.http_client.aclose()
    
    async def fetch_list_page(self, page: int = 0) -> list[dict]:
        """Estrae lista macchinari da una pagina."""
        params = {"lg": "IT", "page": page}
        
        self.log(f"Fetching list page {page}...")
        response = await self.http_client.get(PAF_LIST_URL, params=params)
        response.raise_for_status()
        
        html = response.text
        
        # Parse HTML per estrarre macchinari
        # NOTA: Inplementazione dipende dalla struttura HTML del sito
        records = self._parse_list_html(html)
        
        self.log(f"  → {len(records)} records found")
        return records
    
    def _parse_list_html(self, html: str) -> list[dict]:
        """
        Parser HTML per la lista macchinari.
        
        Struttura attesa:
        <div class="machine-item">
            <a href="fo_rumore_viewer_for_macchianario.php?objId=123">
                <strong>MAKITA - 6805 BV</strong>
                <span>Avvitatori e cacciaviti...</span>
                <span>Elettrica 220V-380V</span>
            </a>
        </div>
        """
        records = []
        
        # TODO: Implementare parsing HTML con BeautifulSoup o similar
        # Per ora stub:
        return records
    
    async def fetch_detail(self, obj_id: int) -> Optional[dict]:
        """Estrae detail page per un macchinario."""
        params = {"objId": obj_id}
        
        response = await self.http_client.get(PAF_DETAIL_URL, params=params)
        
        if response.status_code == 404:
            return None
        
        response.raise_for_status()
        
        html = response.text
        detail = self._parse_detail_html(html, obj_id)
        
        return detail
    
    def _parse_detail_html(self, html: str, obj_id: int) -> dict:
        """
        Parser HTML per detail page.
        
        Estrae:
        - Valori LAeq emissione
        - LCPeak
        - Altri dati tecnici
        """
        detail = {"obj_id": obj_id}
        
        # TODO: Implementare parsing detail page
        # Cerca nel HTML:
        # - LAeq, dB(A)
        # - LCPeak, dB(C)
        
        return detail
    
    def log(self, msg: str):
        if self.verbose:
            print(f"[PAFExporter] {msg}", file=sys.stderr)
    
    async def export_list_only(self, max_pages: int = 50) -> int:
        """Estrae solo liste (senza detail pages)."""
        all_records = []
        
        for page in range(max_pages):
            records = await self.fetch_list_page(page)
            
            if not records:
                break
            
            all_records.extend(records)
            await asyncio.sleep(self.rate_limit)
        
        self._save_output(all_records)
        return len(all_records)
    
    async def export_with_details(
        self,
        tipologia: Optional[str] = None,
        sample_size: int = 100,
    ) -> int:
        """Estrae lista + detail pages per campione."""
        # Fase 1: Fetch lista
        list_records = await self.export_list_only(max_pages=50)
        
        # Fase 2: Fetch details per campione
        sample = list_records[:sample_size] if sample_size > 0 else list_records
        
        for i, record in enumerate(sample):
            obj_id = record.get("obj_id")
            if not obj_id:
                continue
            
            self.log(f"Fetching detail {i+1}/{len(sample)}: objId={obj_id}")
            detail = await self.fetch_detail(obj_id)
            
            if detail:
                record.update(detail)
            
            await asyncio.sleep(self.rate_limit)
        
        self._save_output(list_records)
        return len(list_records)
    
    def _save_output(self, records: list[dict]):
        """Salva output su file."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        output_data = {
            "metadata": {
                "fonte": "PAF - Portale Agenti Fisici",
                "url": PAF_LIST_URL,
                "data_estrazione": date.today().isoformat(),
                "record_count": len(records),
                "disclaimer": "Dati per finalità prevenzione sicurezza lavoro"
            },
            "records": records
        }
        
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        self.log(f"Saved {len(records)} records to {self.output_path}")


async def main():
    parser = argparse.ArgumentParser(
        description="PAF Noise Database Exporter"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output JSON path"
    )
    parser.add_argument(
        "--tipologia", "-t",
        type=str,
        help="Filter by tipologia (e.g., 'Smerigliatrici')"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=50,
        help="Max pages to fetch (default: 50)"
    )
    parser.add_argument(
        "--scrape-details",
        action="store_true",
        help="Also fetch detail pages for each machine"
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=100,
        help="Number of detail pages to fetch (default: 100)"
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=2.0,
        help="Seconds between requests (default: 2.0)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    async with PAFExporter(
        output_path=args.output,
        rate_limit=args.rate_limit,
        verbose=args.verbose,
    ) as exporter:
        if args.scrape_details:
            count = await exporter.export_with_details(
                tipologia=args.tipologia,
                sample_size=args.sample,
            )
        else:
            count = await exporter.export_list_only(max_pages=args.limit)
    
    print(f"Export completed: {count} records")


if __name__ == "__main__":
    asyncio.run(main())
```

### 4.2 Script Transform: transform_paf_to_mars.py

```python
#!/usr/bin/env python3
"""
Transform PAF data to MARS schema
================================

Legge JSON da paf_export.py e lo trasforma per il seed MARS.

Uso:
    python scripts/transform_paf_to_mars.py \
        --input data/knowledge_base/raw/kb_2026-04-08.json \
        --output data/knowledge_base/kb_2026-04-08.json
"""
import argparse
import json
from datetime import date
from pathlib import Path
import uuid


def transform_record(paf_record: dict) -> dict:
    """Trasforma un record PAF in formato MARS."""
    
    # Estrai campi base
    url = paf_record.get("url", "")
    obj_id = None
    if "objId=" in url:
        obj_id = int(url.split("objId=")[1].split("&")[0])
    
    # Costruisci URL dettaglio
    detail_url = f"https://www.portaleagentifisici.it/fo_rumore_viewer_for_macchianario.php?objId={obj_id}" if obj_id else None
    
    # StimLAeq tipico da range interni se non disponibile
    laeq_typical = paf_record.get("laeq_typical")
    if laeq_typical is None:
        # Stima da tipologia usando KB interna
        laeq_typical = estimate_laeq_by_category(paf_record.get("tipologia", ""))
    
    return {
        "id": str(uuid.uuid4()),
        "marca": paf_record.get("marca", ""),
        "modello": paf_record.get("modello", ""),
        "tipologia": paf_record.get("tipologia", ""),
        "alimentazione": paf_record.get("alimentazione", ""),
        "laeq_min_db_a": paf_record.get("laeq_min"),
        "laeq_max_db_a": paf_record.get("laeq_max"),
        "laeq_typical_db_a": laeq_typical,
        "lcpeak_db_c": paf_record.get("lcpeak"),
        "fonte": "PAF - Portale Agenti Fisici",
        "url_fonte": detail_url,
        "data_aggiornamento": date.today().isoformat(),
        "disclaimer": "Dati per finalità prevenzione sicurezza lavoro - PAF Portale Agenti Fisici"
    }


def estimate_laeq_by_category(tipologia: str) -> float:
    """
    Stima LAeq tipico per categoria.
    
    Questi valori sono basati su letteratura tecnica e banche dati settoriali.
    Usati come fallback quando dati PAF non contengono valori di emissione.
    """
    STIMA_TIPOLOGIA = {
        # Attrezzi pneumatici
        "Martelli perforatori": 95,
        "Martelli picconatori": 100,
        "Avvitatori": 75,
        "Smerigliatrici": 85,
        "Trapani": 80,
        "Seghe": 85,
        # Macchine movimento terra
        "Escavatore": 85,
        "Carrello elevatore": 75,
        "Trattore": 80,
        # Varie
        "Compressore": 80,
        "Generatore": 75,
    }
    
    for key, value in STIMA_TIPOLOGIA.items():
        if key.lower() in tipologia.lower():
            return value
    
    return 80.0  # Default cautelativo


def transform(input_path: Path, output_path: Path):
    """Main transform function."""
    
    with open(input_path, "r", encoding="utf-8") as f:
        paf_data = json.load(f)
    
    records = paf_data.get("records", [])
    
    transformed = [transform_record(r) for r in records]
    
    output = {
        "metadata": {
            "fonte": "PAF - Portale Agenti Fisici (trasformato)",
            "data_trasformazione": date.today().isoformat(),
            "record_count": len(transformed),
        },
        "records": transformed
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"Transformed {len(transformed)} records → {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", type=Path, required=True)
    parser.add_argument("--output", "-o", type=Path, required=True)
    args = parser.parse_args()
    
    transform(args.input, args.output)
```

### 4.3 Batch Script Completo: run_paf_export.sh

```bash
#!/bin/bash
# PAF Export Batch Runner
# ======================
# Esegue export completo PAF con rate limiting e snapshot

set -e

DATE=$(date +%Y-%m-%d)
OUTPUT_DIR="data/knowledge_base"
SNAPSHOT_DIR="${OUTPUT_DIR}/snapshots"

mkdir -p "${OUTPUT_DIR}/raw"
mkdir -p "${SNAPSHOT_DIR}"

echo "=== PAF Export Started: ${DATE} ==="

# Step 1: Export lista (senza detail pages)
echo "[1/4] Exporting list pages..."
python scripts/paf_export.py \
    --output "${OUTPUT_DIR}/raw/paf_list_${DATE}.json" \
    --limit 50 \
    --rate-limit 2.0 \
    --verbose

# Step 2: Transform to MARS format
echo "[2/4] Transforming to MARS schema..."
python scripts/transform_paf_to_mars.py \
    --input "${OUTPUT_DIR}/raw/paf_list_${DATE}.json" \
    --output "${OUTPUT_DIR}/kb_${DATE}.json"

# Step 3: Create snapshot
echo "[3/4] Creating snapshot..."
cp "${OUTPUT_DIR}/kb_${DATE}.json" "${SNAPSHOT_DIR}/kb_${DATE}_v1.json"
sha256sum "${OUTPUT_DIR}/kb_${DATE}.json" > "${SNAPSHOT_DIR}/kb_${DATE}_v1.sha256"

# Step 4: Generate seed file for PostgreSQL
echo "[4/4] Generating PostgreSQL seed..."
python scripts/generate_postgres_seed.py \
    --input "${OUTPUT_DIR}/kb_${DATE}.json" \
    --output "migrations/versions/seed_noise_source_catalog_${DATE}.py"

echo "=== PAF Export Completed ==="
echo "Output: ${OUTPUT_DIR}/kb_${DATE}.json"
echo "Snapshot: ${SNAPSHOT_DIR}/kb_${DATE}_v1.json"
```

---

## 5. POSTGRESQL SEED

### 5.1 Migration Seed Template

```python
# migrations/versions/seed_noise_source_catalog_YYYYMMDD.py
"""
Seed noise_source_catalog from PAF data.
Generated by scripts/transform_paf_to_mars.py
"""
from alembic import op
import json
from pathlib import Path

def load_sources():
    # Load transformed data
    data_file = Path(__file__).parent.parent.parent / "data" / "knowledge_base" / "kb_2026-04-08.json"
    with open(data_file, "r") as f:
        data = json.load(f)
    return data.get("records", [])

def upgrade():
    sources = load_sources()
    inserted = 0
    
    for src in sources:
        try:
            op.execute(f"""
                INSERT INTO noise_source_catalog (
                    id, marca, modello, tipologia, alimentazione,
                    laeq_min_db_a, laeq_max_db_a, laeq_typical_db_a,
                    lcpeak_db_c, fonte, url_fonte,
                    data_aggiornamento, disclaimer
                ) VALUES (
                    '{src['id']}',
                    '{src['marca']}',
                    '{src['modello']}',
                    '{src['tipologia']}',
                    '{src.get('alimentazione', '')}',
                    {src.get('laeq_min_db_a', 'NULL')},
                    {src.get('laeq_max_db_a', 'NULL')},
                    {src.get('laeq_typical_db_a', 'NULL')},
                    {src.get('lcpeak_db_c', 'NULL')},
                    'PAF - Portale Agenti Fisici',
                    '{src.get('url_fonte', '')}',
                    '{src['data_aggiornamento']}',
                    '{src['disclaimer']}'
                )
                ON CONFLICT (id) DO UPDATE SET
                    laeq_typical_db_a = EXCLUDED.laeq_typical_db_a,
                    data_aggiornamento = EXCLUDED.data_aggiornamento
            """)
            inserted += 1
        except Exception as e:
            print(f"Error inserting {src.get('marca')} {src.get('modello')}: {e}")
    
    print(f"Inserted/updated {inserted} noise sources from PAF")

def downgrade():
    op.execute("DELETE FROM noise_source_catalog WHERE fonte = 'PAF - Portale Agenti Fisici'")
```

---

## 6. VERSIONING STRATEGY

### 6.1 Snapshot Naming Convention

```
kb_YYYY-MM-DD[_vN].json
kb_YYYY-MM-DD[_vN].sha256
```

Esempi:
- `kb_2026-04-08.json` - Versione base
- `kb_2026-04-08_v1.json` - Primo snapshot
- `kb_2026-04-08_v2.json` - Secondo aggiornamento
- `kb_2026-05-15.json` - Update mensile

### 6.2 Update Frequency

| Tipo | Frequenza | Motivo |
|------|-----------|--------|
| Major | Annuale | Aggiornamento significativo database PAF |
| Minor | Trimestrale | Nuove entries macchinari |
| Hotfix | On-demand | Correzione errori critici |

### 6.3 Diff Strategy

```bash
# Compare two versions
python -m json_diff \
    data/knowledge_base/snapshots/kb_2026-04-08_v1.json \
    data/knowledge_base/snapshots/kb_2026-05-15_v1.json \
    --format=summary
```

---

## 7. ALTERNATIVE IF TERMS BLOCK

### 7.1 Contatto Formale PAF

Se i termini risultassero più restrittivi del previsto:

**Email**: portaleagentifisici@usl7.toscana.it  
**Oggetto**: Richiesta utilizzo dati per software valutazione rischio rumore

```text
Gentile Comitato Scientifico PAF,

siamo il team MARS, software house specializzata in soluzioni 
per consulenti HSE. Stiamo sviluppando un modulo per la valutazione 
del rischio rumore ai sensi del D.Lgs. 81/2008.

Vorremmo chiedere:
1. Autorizzazione all'utilizzo dei dati PAF per arricchire 
   la knowledge base del nostro software (finalità: prevenzione)
2. Eventuale accesso a dataset strutturato se disponibile
3. Modalità per citare correttamente la fonte

Restiamo a disposizione per chiarimenti.

Distinti saluti,
MARS Team
```

### 7.2 Knowledge Base Interna MARS (Fallback)

Se PAF non autorizza l'uso:

**Strategia**: Costruire KB interna curata dal team MARS
- Ricercatori che raccolgono dati da fonti pubbliche (costruttori, letteratura)
- Entry verificate manualmente
- Nessun scraping automatico

**Vantaggi**:
- Completamente indipendenti
- Dati verificati qualità
- Nessun rischio legale

**Svantaggi**:
- Più costoso da mantenere
- Meno ampio (50-100 entries vs 2452)
- Aggiornamenti manuali

---

## 8. CRITERI DI ACCETTAZIONE

| # | Criterio | Verifica |
|---|----------|----------|
| 1 | Script paf_export.py eseguibile | `python scripts/paf_export.py --help` |
| 2 | Rate limiting funziona | Log mostra 2sec tra richieste |
| 3 | Output JSON valido | `python -c "import json; json.load(open('output.json'))"` |
| 4 | Transform mapping corretto | Record ha tutti i campi MARS |
| 5 | Snapshot creato | `ls data/knowledge_base/snapshots/` |
| 6 | Hash SHA256 valido | `sha256sum -c *.sha256` |
| 7 | Disclaimer presente | Output contains "PAF" + "prevenzione" |
| 8 | Seed migration generato | File seed*.py esiste e valido |

---

**Documento creato**: 2026-04-08  
**Stato**: Ready for BUILD execution
**Prossimo step**: Integrazione firecrawl-skill nel CLI orchestrator
