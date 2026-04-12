# MARS DVR Rumore - Session Resume Info
# Generated: 11/04/2026

## Project State

### Phase 4 Completata
- Commit: 292e304 su branch phase3-ai-integration
- Pushato su origin/phase3-ai-integration
- Server avviato su porta 8083

### Files Modificati/Creati in Phase 4
- migrations/versions/006_add_docx_models.py
- src/api/routes/export_routes.py
- src/api/schemas/export.py
- src/bootstrap/database.py
- src/domain/services/docx_generator.py
- src/domain/services/template_service.py
- src/domain/services/docx_templates/base_dvr.docx
- src/domain/services/prompts/templates/source_detection_prompt.md
- src/infrastructure/database/models/ (5 nuovi: job_role, mitigation_measure, document_template, print_settings, assessment_document)
- static/ (frontend WYSIWYG - 12 files)
- Bug fix: ai_routes action/status schema

### OpenCode Config Issue
Problema: glm-5.1:cloud funziona in Plan Mode ma da "unauthorized" in Build Mode.

Soluzione applicata:
1. Creato C:\Users\Salvatore Romano\Desktop\MARS_DVR_Rumore\.opencode\opencode.json
   - model: ollama/glm-5.1:cloud
   - baseURL: http://127.0.0.1:11434/v1
   - apiKey: {env:OLLAMA_API_KEY}

2. OLLAMA_API_KEY e' a livello utente: c0af5bcc7f154afe9d3aa3d2a43b9eae.VLY7IQJuF08uL1xbgh9dINT4

### Server Status
- Server FastAPI su porta 8083 (background job)
- Endpoint testati e funzionanti

### Prossimi Step
1. Chiudere COMPLETAMENTE opencode (tutte le istanze)
2. Riaprire opencode
3. Testare glm-5.1:cloud in Build Mode
4. Se ancora unauthorized, aggiornare anche:
   C:\Users\Salvatore Romano\Desktop\MARS_DVR_Rumore\mars_noise_module_full_agent_pack\mars_noise_module_pack\.opencode\opencode.jsonc
   - cambiare baseURL da https://ollama.com/v1 a http://127.0.0.1:11434/v1

## Comandi Utility

# Verificare se server e' attivo
Invoke-RestMethod -Uri "http://127.0.0.1:8083/health" -Method Get

# Kill tutti i processi python relativi al server
Get-Process | Where-Object {$_.CommandLine -match "uvicorn|python.*mars"} | Stop-Process -Force

# Riavviare server
cd C:\Users\Salvatore Romano\Desktop\MARS_DVR_Rumore
Start-Process powershell -ArgumentList "-Command","python -m uvicorn src.bootstrap.main:app --port 8083 --host 127.0.0.1" -WindowStyle Hidden

# Test API
Invoke-RestMethod -Uri "http://127.0.0.1:8083/api/v1/noise/print-settings" -Method Get
Invoke-RestMethod -Uri "http://127.0.0.1:8083/static/index.html" -Method Get
