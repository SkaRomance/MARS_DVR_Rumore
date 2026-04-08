# STRUCTURED PLAN - PHASE 2 (Calculation Core)

## Metadata

| Campo | Valore |
|-------|--------|
| **Fase** | 2 - Calculation Core |
| **Stato** | APPROVATO per BUILD |
| **Modello** | minimax-m2.7:cloud |
| **Data** | 2026-04-08 |
| **Dipendenze** | Fase 1 completata |

---

## 1. OVERVIEW

Phase 2 implementa il cuore del calcolo per la valutazione del rischio rumore secondo:
- **D.Lgs. 81/2008** Art. 190-196
- **UNI EN ISO 9612:2011** (Misurazione esposizione rumore)
- **ISO 1999:2013** (Calcolo LCPeak)
- **ISO/IEC Guide 98-3** (Incertezza)

### Aree Funzionali

| Area | Complessità | Sub-task |
|------|-------------|----------|
| Calcolo LEX,8h | ALTA | 2.1-2.5 |
| LCPeak aggregato | MEDIA | 2.6-2.7 |
| Classificazione soglie | BASSA | 2.8 |
| Incertezza ±dB | ALTA | 2.9-2.11 |
| Correzioni K | MEDIA | 2.12-2.13 |
| Lavoratori sensibili | MEDIA | 2.14-2.15 |
| Report base | BASSA | 2.16 |

---

## 2. SPECIFICHE MATEMATICHE

### 2.1 Formula Principale LEX,8h (ISO 9612)

```
LEX,8h = LEX,A,8h = 10 × log10( Σi ( 10^(LAeq,i/10) × Ti / T0 ) )

Dove:
- LAeq,i = Livello equivalente della fase i [dB(A)]
- Ti = Durata della fase i [ore]
- T0 = Tempo di riferimento = 8 ore
```

### 2.2 Implementazione NumPy

```python
# src/domain/services/noise_calculation.py
import numpy as np
from dataclasses import dataclass
from typing import Protocol

class ExposureInput(Protocol):
    laeq_db_a: float
    duration_hours: float
    origin: str  # 'measured', 'calculated', 'estimated'

@dataclass
class ExposureResult:
    lex_8h: float
    lex_weekly: float | None
    lcpeak: float | None
    uncertainty: float | None
    confidence: float

def calculate_lex_8h(exposures: list[ExposureInput]) -> ExposureResult:
    """
    Calcola LEX,8h secondo ISO 9612.
    
    Args:
        exposures: Lista di esposizioni per fase lavorativa
        
    Returns:
        ExposureResult con LEX,8h e parametri derivati
        
    Raises:
        ValueError: Se input non valido
    """
    if not exposures:
        raise ValueError("Lista esposizioni vuota")
    
    # Valida input
    for exp in exposures:
        if exp.laeq_db_a < 0 or exp.laeq_db_a > 140:
            raise ValueError(f"LAeq {exp.laeq_db_a} fuori range [0, 140]")
        if exp.duration_hours <= 0 or exp.duration_hours > 24:
            raise ValueError(f"Durata {exp.duration_hours} non valida")
    
    # Calcolo somma pesata
    reference_time = 8.0  # ore
    total_dose = 0.0
    
    for exp in exposures:
        linear_laeq = 10 ** (exp.laeq_db_a / 10)
        dose = linear_laeq * exp.duration_hours
        total_dose += dose
    
    if total_dose <= 0:
        raise ValueError("Dose totale non valida")
    
    # LEX,8h finale
    lex_8h = 10 * np.log10(total_dose / reference_time)
    
    # Calcola incertezza combinata (ISO/IEC Guide 98-3)
    uncertainty = calculate_combined_uncertainty(exposures)
    
    # Calcola confidence score
    confidence = calculate_confidence(exposures)
    
    return ExposureResult(
        lex_8h=round(lex_8h, 1),
        lex_weekly=None,  # Calcolato se abbastanza dati
        lcpeak=None,
        uncertainty=uncertainty,
        confidence=confidence
    )
```

### 2.3 Calcolo Incertezza (ISO/IEC Guide 98-3)

```python
def calculate_combined_uncertainty(exposures: list[ExposureInput]) -> float:
    """
    Calcola incertezza estesa secondo ISO/IEC Guide 98-3.
    
    u_c = sqrt( Σ_i (u_i)^2 )
    
    dove u_i sono le incertezze tipo di ogni sorgente:
    - Misura strumentale: 1.5 dB (tipico fonometro Classe I)
    - Stima da catalogo: 3.0 dB
    - Dichiarazione costruttore: 2.0 dB
    """
    uncertainty_values = {
        'measured': 1.5,
        'calculated': 2.0,
        'estimated': 3.0,
        'manufacturer_declared': 2.0,
    }
    
    sum_squared = 0.0
    for exp in exposures:
        u_i = uncertainty_values.get(exp.origin, 3.0)
        sum_squared += u_i ** 2
    
    combined = np.sqrt(sum_squared)
    
    # Incertezza estesa con k=2 (95% confidence)
    extended = 2 * combined
    
    return round(extended, 2)
```

### 2.4 Correzioni K (ISO 1999)

```python
@dataclass
class KCorrections:
    k_impulse: float = 0.0   # Presenza di componenti impulsive
    k_tone: float = 0.0      # Presenza di componenti tonali
    k_background: float = 0.0  # Rumore di fondo
    
def calculate_k_impulse(laeq: float, lpeak: float) -> float:
    """
    K_impulse = 0 per LAeq - Lpeak < 3 dB
    K_impulse = 3 dB per LAeq - Lpeak >= 3 dB e < 10 dB
    K_impulse = 6 dB per LAeq - Lpeak >= 10 dB
    """
    delta = laeq - lpeak
    if delta < 3:
        return 0.0
    elif delta < 10:
        return 3.0
    else:
        return 6.0

def calculate_k_tone(laeq_third_octave: list[float]) -> float:
    """
    K_tone = 0 dB se nessuna componente tonale significativa
    K_tone = 2 dB se tonalità modesta
    K_tone = 4 dB se tonalità marcata
    """
    # Cerca picchi in terzi di ottava
    max_idx = np.argmax(laeq_third_octave)
    max_val = laeq_third_octave[max_idx]
    
    # Adjacent average
    neighbors = []
    if max_idx > 0:
        neighbors.append(laeq_third_octave[max_idx - 1])
    if max_idx < len(laeq_third_octave) - 1:
        neighbors.append(laeq_third_octave[max_idx + 1])
    
    if not neighbors:
        return 0.0
    
    avg_neighbor = np.mean(neighbors)
    tonal_excess = max_val - avg_neighbor
    
    if tonal_excess < 3:
        return 0.0
    elif tonal_excess < 6:
        return 2.0
    else:
        return 4.0

def calculate_k_background(laeq_main: float, laeq_background: float) -> float:
    """
    K_background = 0 dB se LAeq_background < LAeq_main - 10 dB
    K_background calcolato altrimenti
    """
    delta = laeq_main - laeq_background
    if delta < 10:
        return 0.0
    else:
        return 10 - delta  # Valore negativo viene applicato come sottrazione
```

### 2.5 Formula Completa LEX,8h con Correzioni K

```
LEX,A,8h,corretto = LEX,A,8h + K_total

Dove:
K_total = K_impulse + K_tone + K_background

Valori massimi applicabili:
- K_impulse ≤ +6 dB
- K_tone ≤ +4 dB
- K_background ≤ -10 dB (mai positivo)
```

---

## 3. SUB-TASK IMPLEMENTATIVI

### 3.1 Sub-task 2.1: Crea dominio calcolo noise_calculation.py

**File**: `src/domain/services/noise_calculation.py`

```python
"""Noise exposure calculation services."""
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class ExposureOrigin(Enum):
    MEASURED = "measured"
    CALCULATED = "calculated"
    ESTIMATED = "estimated"
    IMPORTED = "imported"
    AI_SUGGESTED = "ai_suggested"
    VALIDATED = "validated"
    DEFAULT_VALUE = "default_value"

@dataclass
class PhaseExposure:
    laeq_db_a: float
    duration_hours: float
    origin: ExposureOrigin = ExposureOrigin.ESTIMATED
    lcpeak_db_c: Optional[float] = None
    background_noise_db_a: Optional[float] = None

@dataclass
class NoiseExposureResult:
    lex_8h: float
    lex_weekly: Optional[float] = None
    lcpeak_aggregated: Optional[float] = None
    uncertainty_db: Optional[float] = None
    confidence_score: float
    k_impulse: float = 0.0
    k_tone: float = 0.0
    k_background: float = 0.0
    risk_band: str = "negligible"

def calculate_lex_8h(exposures: list[PhaseExposure]) -> NoiseExposureResult:
    """Main calculation entry point."""
    pass

def calculate_lex_weekly(daily_lex: list[float]) -> float:
    """LEX,weekly = 10 × log10( Σ_daily 10^(LEX,d/10) / N_days)"""
    pass
```

**Criterio**: Test `pytest tests/unit/test_noise_calculation.py::test_lex_8h_basic` passa

---

### 3.2 Sub-task 2.2: Implementa calcolo base LEX,8h

```python
def calculate_lex_8h(exposures: list[PhaseExposure]) -> NoiseExposureResult:
    if not exposures:
        raise ValueError("Empty exposure list")
    
    reference_time = 8.0
    total_dose = 0.0
    max_lcpeak = 0.0
    
    for exp in exposures:
        linear_laeq = 10 ** (exp.laeq_db_a / 10)
        total_dose += linear_laeq * exp.duration_hours
        
        if exp.lcpeak_db_c and exp.lcpeak_db_c > max_lcpeak:
            max_lcpeak = exp.lcpeak_db_c
    
    lex_8h = 10 * np.log10(total_dose / reference_time)
    
    return NoiseExposureResult(
        lex_8h=round(lex_8h, 1),
        lcpeak_aggregated=max_lcpeak if max_lcpeak > 0 else None,
        uncertainty_db=calculate_combined_uncertainty(exposures),
        confidence_score=calculate_confidence(exposures),
        risk_band=classify_risk_band(lex_8h)
    )
```

**Criterio**: Test con dati metalmeccanico passa (83.2 dB(A) atteso)

---

### 3.3 Sub-task 2.3: Implementa calcolo LEX,weekly

```python
def calculate_lex_weekly(daily_lex: list[float]) -> float:
    if not daily_lex:
        raise ValueError("Empty daily lex list")
    
    n_days = len(daily_lex)
    total_weekly_dose = sum(10 ** (lex / 10) for lex in daily_lex)
    
    lex_weekly = 10 * np.log10(total_weekly_dose / n_days)
    return round(lex_weekly, 1)
```

**Criterio**: Test con 5 giorni noti passa

---

### 3.4 Sub-task 2.4: Implementa LCPeak aggregato

```python
def calculate_lcpeak_aggregated(exposures: list[PhaseExposure]) -> float | None:
    """LCPeak massimo tra tutte le fasi (non è una media)."""
    peaks = [exp.lcpeak_db_c for exp in exposures if exp.lcpeak_db_c is not None]
    if not peaks:
        return None
    return max(peaks)
```

**Criterio**: Test con martello demolitore (138 dB(C)) passa

---

### 3.5 Sub-task 2.5: Implementa classificazione soglie

```python
RISK_BANDS = {
    (0, 80): "negligible",
    (80, 85): "low",
    (85, 87): "medium",
    (87, float('inf')): "high",
}

PEAK_BANDS = {
    (0, 135): "acceptable",
    (135, 137): "high",
    (137, 140): "very_high",
    (140, float('inf')): "critical",
}

def classify_risk_band(lex_8h: float) -> str:
    for (low, high), band in RISK_BANDS.items():
        if low <= lex_8h < high:
            return band
    return "critical"

def classify_peak_risk(lcpeak: float) -> str:
    for (low, high), risk in PEAK_BANDS.items():
        if low <= lcpeak < high:
            return risk
    return "critical"
```

**Criterio**: Test 83.2 dB(A) → "low", 95.8 dB(A) → "high"

---

### 3.6 Sub-task 2.6: Implementa calcolo incertezza

```python
EXPOSURE_UNCERTAINTY = {
    ExposureOrigin.MEASURED: 1.5,
    ExposureOrigin.CALCULATED: 2.0,
    ExposureOrigin.ESTIMATED: 3.0,
    ExposureOrigin.IMPORTED: 2.5,
    ExposureOrigin.AI_SUGGESTED: 4.0,
    ExposureOrigin.VALIDATED: 1.0,
    ExposureOrigin.DEFAULT_VALUE: 5.0,
}

def calculate_combined_uncertainty(exposures: list[PhaseExposure]) -> float:
    sum_squared = sum(
        EXPOSURE_UNCERTAINTY[exp.origin] ** 2 for exp in exposures
    )
    combined = np.sqrt(sum_squared)
    extended = 2 * combined  # k=2 per 95% confidence
    return round(extended, 2)
```

**Criterio**: Test con 3 measured → ~3.5 dB

---

### 3.7 Sub-task 2.7: Implementa correzioni K complete

```python
def calculate_k_corrections(exposures: list[PhaseExposure]) -> KCorrections:
    k_total = KCorrections()
    
    for exp in exposures:
        if exp.lcpeak_db_c:
            k_impulse = calculate_k_impulse(exp.laeq_db_a, exp.lcpeak_db_c)
            k_total.k_impulse = max(k_total.k_impulse, k_impulse)
        
        # K_background se disponibile
        if exp.background_noise_db_a:
            k_bg = calculate_k_background(exp.laeq_db_a, exp.background_noise_db_a)
            k_total.k_background += k_bg
    
    return k_total

def apply_k_corrections(lex_8h: float, k: KCorrections) -> float:
    """LEX finale con correzioni K applicate."""
    k_total = k.k_impulse + k.k_tone + k.k_background
    return lex_8h + k_total
```

**Criterio**: Test con presenza impulse (+3 dB) passa

---

### 3.8 Sub-task 2.8: Gestione lavoratori sensibili

```python
@dataclass
class SensitiveWorkerFactors:
    is_pregnant: bool = False
    is_minor: bool = False
    is_ototoxic_exposed: bool = False
    is_vibration_exposed: bool = False

def calculate_sensitive_adjustment(factors: SensitiveWorkerFactors) -> float:
    """
    Per lavoratori sensibili, si applica un aggiustamento
    secondo Allegato VIII D.Lgs. 81/2008.
    
    Ritorno: dB di correzione aggiuntiva (positiva = più conservativo)
    """
    adjustment = 0.0
    
    if factors.is_pregnant:
        adjustment += 3.0  # Protezione extra per nascituro
    
    if factors.is_minor:
        adjustment += 3.0  # Minori hanno soglia più bassa
    
    if factors.is_ototoxic_exposed:
        adjustment += 3.0  # Effetto sinergico rumore+ototossici
    
    if factors.is_vibration_exposed:
        adjustment += 2.0  # Effetto sinergico rumore+vibrazioni
    
    return adjustment
```

**Criterio**: Lavoratore incinta + ototossico → +6 dB

---

### 3.9 Sub-task 2.9: Crea validazioni input

```python
def validate_laeq(laeq: float) -> None:
    if laeq < 0:
        raise ValueError(f"LAeq negativo non valido: {laeq}")
    if laeq > 140:
        raise ValueError(f"LAeq troppo alto (max 140 dB): {laeq}")

def validate_duration(duration: float) -> None:
    if duration <= 0:
        raise ValueError(f"Durata deve essere > 0: {duration}")
    if duration > 24:
        raise ValueError(f"Durata non può superare 24h: {duration}")

def validate_lcpeak(lcpeak: float) -> None:
    if lcpeak < 100:
        raise ValueError(f"LCPeak troppo basso: {lcpeak}")
    if lcpeak > 170:
        raise ValueError(f"LCPeak troppo alto: {lcpeak}")
```

**Criterio**: Test con -10 dB(A) → ValueError

---

### 3.10 Sub-task 2.10: Crea test unitari completi

```python
# tests/unit/test_noise_calculation.py
import pytest
from src.domain.services.noise_calculation import (
    calculate_lex_8h, PhaseExposure, ExposureOrigin
)

class TestNoiseCalculation:
    
    def test_lex_8h_metalmeccanico(self):
        """Test caso positivo: metalmeccanico"""
        exposures = [
            PhaseExposure(laeq_db_a=85, duration_hours=4.0, 
                         origin=ExposureOrigin.MEASURED),
            PhaseExposure(laeq_db_a=90, duration_hours=2.0,
                         origin=ExposureOrigin.CALCULATED),
            PhaseExposure(laeq_db_a=60, duration_hours=2.0,
                         origin=ExposureOrigin.MEASURED),
        ]
        result = calculate_lex_8h(exposures)
        
        assert 82.5 <= result.lex_8h <= 83.5  # Atteso ~83.2
        assert result.risk_band == "low"
    
    def test_lex_8h_edilizia(self):
        """Test caso positivo: edilizia (supera soglia)"""
        exposures = [
            PhaseExposure(laeq_db_a=105, duration_hours=2.0,
                         origin=ExposureOrigin.MEASURED,
                         lcpeak_db_c=138),
            PhaseExposure(laeq_db_a=95, duration_hours=3.0,
                         origin=ExposureOrigin.MEASURED),
            PhaseExposure(laeq_db_a=70, duration_hours=3.0,
                         origin=ExposureOrigin.MEASURED),
        ]
        result = calculate_lex_8h(exposures)
        
        assert 95.0 <= result.lex_8h <= 96.0  # Atteso ~95.8
        assert result.risk_band == "high"
        assert result.lcpeak_aggregated == 138.0
    
    def test_lex_8h_invalid_negative(self):
        """Test caso negativo: LAeq negativo"""
        with pytest.raises(ValueError, match="negativo"):
            calculate_lex_8h([PhaseExposure(laeq_db_a=-10, duration_hours=1.0)])
    
    def test_lex_8h_empty(self):
        """Test caso negativo: lista vuota"""
        with pytest.raises(ValueError, match="Empty"):
            calculate_lex_8h([])
    
    def test_lex_8h_single_exposure(self):
        """Test edge case: singola esposizione 8h"""
        exposures = [
            PhaseExposure(laeq_db_a=80, duration_hours=8.0,
                         origin=ExposureOrigin.MEASURED),
        ]
        result = calculate_lex_8h(exposures)
        
        assert result.lex_8h == 80.0
    
    def test_lex_weekly_calculation(self):
        """Test LEX,weekly"""
        daily_lex = [80, 82, 81, 83, 80]
        result = calculate_lex_weekly(daily_lex)
        
        assert 81.5 <= result <= 82.5
```

**Criterio**: `pytest tests/unit/test_noise_calculation.py -v` → tutti pass

---

### 3.11 Sub-task 2.11: Crea test integrazione calcolo API

```python
# tests/integration/test_noise_calculation_api.py
import pytest
from httpx import AsyncClient
from src.bootstrap.main import app

@pytest.mark.asyncio
async def test_calculate_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/noise/assessments/calc",
            json={
                "exposures": [
                    {"laeq_db_a": 85, "duration_hours": 4.0, "origin": "measured"},
                    {"laeq_db_a": 90, "duration_hours": 2.0, "origin": "calculated"},
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "lex_8h" in data
        assert "risk_band" in data
```

---

### 3.12 Sub-task 2.12: Implementa endpoint POST /calculate

```python
# src/api/routes/calculation.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import list

router = APIRouter()

class ExposureRequest(BaseModel):
    laeq_db_a: float = Field(..., ge=0, le=140)
    duration_hours: float = Field(..., gt=0, le=24)
    origin: str = Field(default="estimated")
    lcpeak_db_c: float | None = Field(default=None, ge=100, le=170)
    background_noise_db_a: float | None = Field(default=None, ge=0, le=140)

class CalculationRequest(BaseModel):
    assessment_id: UUID
    exposures: list[ExposureRequest]
    apply_k_corrections: bool = False

class CalculationResponse(BaseModel):
    lex_8h: float
    lex_weekly: float | None
    lcpeak_aggregated: float | None
    uncertainty_db: float
    confidence_score: float
    risk_band: str
    k_impulse: float = 0.0
    k_tone: float = 0.0
    k_background: float = 0.0

@router.post("/calculate", response_model=CalculationResponse)
async def calculate_noise_exposure(
    request: CalculationRequest,
    db: AsyncSession = Depends(get_db),
):
    exposures = [PhaseExposure(**exp.model_dump()) for exp in request.exposures]
    result = calculate_lex_8h(exposures)
    return CalculationResponse(**result.__dict__)
```

---

### 3.13 Sub-task 2.13: Crea use case calcolo

```python
# src/application/use_cases/noise_calculation.py
class NoiseCalculationUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def calculate_exposure(
        self, assessment_id: UUID, exposures: list[PhaseExposure]
    ) -> NoiseExposureResult:
        """Calcola esposizione e salva risultati."""
        result = calculate_lex_8h(exposures)
        
        # Salva in noise_assessment_result
        db_result = NoiseAssessmentResult(
            assessment_id=assessment_id,
            lex_8h=result.lex_8h,
            lcpeak=result.lcpeak_aggregated,
            uncertainty_db=result.uncertainty_db,
            risk_band=result.risk_band,
        )
        self.db.add(db_result)
        await self.db.commit()
        
        return result
```

---

### 3.14 Sub-task 2.14: Documentazione normative

```python
# docs/CALCULATION_SPEC.md
"""
Specifica Calcoli Rumore - MARS Noise Module
==========================================

Riferimenti:
- D.Lgs. 81/2008 Art. 190-196
- UNI EN ISO 9612:2011
- ISO 1999:2013
- ISO/IEC Guide 98-3

Formula Principale LEX,A,8h
----------------------------
LEX,A,8h = 10 × log10( Σi ( 10^(LAeq,i/10) × Ti / T0 ) )

Dove:
- LAeq,i = Livello equivalente fase i [dB(A)]
- Ti = Durata fase i [ore]
- T0 = Tempo riferimento = 8 ore

Soglie di Riferimento (Art. 188 D.Lgs. 81/2008)
-----------------------------------------------
| Parametro       | Inf 80 | 80-85 | 85-87 | > 87    |
|-----------------|--------|-------|-------|---------|
| LEX,8h dB(A)    | OK     | Info  | DPI   | Azione  |
| LCPeak dB(C)    | < 135  | 135+  | 137+  | 140+    |

Obblighi per Soglia
-------------------
< 80 dB(A): Valutazione, nessun obbligo specifico
80-85 dB(A): Informazione, formazione, DPI disponibili
85-87 dB(A): DPI obbligatori, sorveglianza sanitaria
> 87 dB(A): Azioni immediate, misure urgenti
"""
```

---

### 3.15 Sub-task 2.15: Implementa Report Base

```python
# src/application/use_cases/report_generator.py
from jinja2 import Template

REPORT_TEMPLATE = """
VALUTAZIONE RISCHIO RUMORE
=========================

Soggetto: {{ company_name }}
Unità Produttiva: {{ unit_site_name }}
Data Valutazione: {{ assessment_date }}

SINTESI RISULTATI
-----------------
LEX,8h: {{ lex_8h }} dB(A)
LCPicco: {{ lcpeak }} dB(C)
Classe Rischio: {{ risk_band }}
Incertezza: ±{{ uncertainty }} dB

ESPOSIZIONE PER MANSIONE
------------------------
{% for role in roles %}
- {{ role.name }}: LEX={{ role.lex_8h }} dB(A)
{% endfor %}

MISURE DI PREVENZIONE E PROTEZIONE
---------------------------------
{% for action in actions %}
- [{{ action.priority }}] {{ action.description }}
{% endfor %}

LEGAL REFERENCE: D.Lgs. 81/2008 Art. 190-196
"""

def generate_report(assessment: NoiseAssessment, results: list) -> str:
    template = Template(REPORT_TEMPLATE)
    return template.render(
        company_name=assessment.company.name,
        unit_site_name=assessment.unit_site.name,
        assessment_date=assessment.created_at.date(),
        lex_8h=results.lex_8h,
        lcpeak=results.lcpeak_aggregated or "N/D",
        risk_band=results.risk_band.upper(),
        uncertainty=results.uncertainty_db or "N/D",
        roles=[...],
        actions=[...],
    )
```

---

## 4. TEST MATRIX

### 4.1 Test Calcolo Base

| ID | Input | Atteso | Verifica |
|----|-------|--------|----------|
| TC-01 | 85dB/4h + 90dB/2h + 60dB/2h | 83.2 dB(A) | ±0.5 dB |
| TC-02 | 105dB/2h (peak=138) + 95dB/3h + 70dB/3h | 95.8 dB(A) | ±0.5 dB |
| TC-03 | 80dB/8h | 80.0 dB(A) | Esatto |
| TC-04 | 90dB/4h + 90dB/4h | 93.0 dB(A) | ±0.5 dB |
| TC-05 | 70dB/8h | 70.0 dB(A) | Esatto |

### 4.2 Test Validazioni

| ID | Input | Atteso | Verifica |
|----|-------|--------|----------|
| TV-01 | LAeq=-10 | ValueError | Exception |
| TV-02 | LAeq=150 | ValueError | Exception |
| TV-03 | Durata=0 | ValueError | Exception |
| TV-04 | Durata=25 | ValueError | Exception |
| TV-05 | LCPeak=90 | ValueError | Exception |

### 4.3 Test Classificazione

| ID | LEX,8h | Risk Band | LCPeak | Peak Risk |
|----|--------|-----------|--------|-----------|
| TCR-01 | 75 | negligible | 130 | acceptable |
| TCR-02 | 82 | low | 135 | high |
| TCR-03 | 86 | medium | 137 | very_high |
| TCR-04 | 90 | high | 140 | critical |

### 4.4 Test Incertezza

| ID | Origins | Incertezza Estesa |
|----|---------|-------------------|
| TI-01 | 3× measured | ~3.5 dB |
| TI-02 | 3× estimated | ~6.9 dB |
| TI-03 | mixed | ~4.5 dB |

---

## 5. CRITERI DI ACCETTAZIONE

| # | Criterio | Verifica |
|---|----------|----------|
| 1 | Test metalmeccanico passa (83.2±0.5) | `pytest TC-01` |
| 2 | Test edilizia passa (95.8±0.5) | `pytest TC-02` |
| 3 | Test negativi sollevano ValueError | `pytest TV-*` |
| 4 | Classificazione 80-85 → low | `pytest TCR-02` |
| 5 | Incertezza calcolata correttamente | `pytest TI-*` |
| 6 | API /calculate risponde 200 | `curl POST /calc` |
| 7 | Report generato con template | Verifica output |

---

## 6. DEPENDENCIES

```
Fase 1 completata
      │
      └── src/domain/services/noise_calculation.py (2.1)
                    │
                    ├── test_noise_calculation.py (2.10)
                    │
                    ├── calculate_lex_8h (2.2-2.5)
                    │         │
                    │         ├── calculate_lex_weekly (2.3)
                    │         ├── calculate_lcpeak (2.4)
                    │         └── classify_risk_band (2.5)
                    │
                    ├── calculate_combined_uncertainty (2.6)
                    │         │
                    │         └── EXPOSURE_UNCERTAINTY dict
                    │
                    ├── calculate_k_corrections (2.7)
                    │         │
                    │         ├── k_impulse
                    │         ├── k_tone
                    │         └── k_background
                    │
                    └── calculate_sensitive_adjustment (2.8)
                              │
                              └── SensitiveWorkerFactors
```

---

## 7. RISCHI E MITIGAZIONI

| Rischio | Gravità | Probabilità | Mitigazione |
|---------|---------|-------------|-------------|
| Errori arrotondamento | Alta | Bassa | Usare numpy, test precision |
| Formula ISO 9612 sbagliata | Critica | Bassa | Review da specialist, test matrix |
| Overflow per esposizioni lunghe | Media | Bassa | Check su total_dose |
| Division by zero | Alta | Bassa | Validazione input pre-check |

---

**Documento creato**: 2026-04-08  
**Stato**: Ready for BUILD execution
