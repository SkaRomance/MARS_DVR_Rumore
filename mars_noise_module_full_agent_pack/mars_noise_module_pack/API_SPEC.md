# API interne - Modulo Rumore

## Base path
`/api/v1/noise`

## Endpoints principali

### POST /assessments
Crea una nuova valutazione rumore.

### GET /assessments/{id}
Recupera valutazione completa.

### POST /assessments/{id}/bootstrap
Input:
- ateco_codes
- company_profile
- free_text_process_description
- prompt_mode

Output:
- processi suggeriti
- mansioni suggerite
- sorgenti rumorose suggerite
- confidenza per ciascun suggerimento

### POST /assessments/{id}/phases
Aggiunge o aggiorna fasi di lavoro.

### POST /assessments/{id}/machines
Aggiunge macchinari / attrezzature.

### POST /assessments/{id}/measurements/import
Importa misure da file o inserimento strutturato.

### POST /assessments/{id}/calculate
Esegue il calcolo LEX,8h e produce risultati.

### POST /assessments/{id}/generate-report
Genera:
- narrative summary
- sezione DVR rumore
- payload importabile nel DVR generale

### POST /assessments/{id}/ai/prompt
Input:
- prompt
- mode (`bootstrap`, `review`, `rewrite`, `explain`, `detect_sources`)
- context_scope

Output:
- proposta AI strutturata
- modifiche suggerite
- campi da confermare

### POST /assessments/{id}/export/general-dvr
Esporta il payload verso DVR generale.

## Integrazione col DVR generale

Il payload minimo da esportare deve includere:
- assessment_id
- version
- company_id
- roles[]
- exposures[]
- results[]
- mitigation_actions[]
- narrative_block
- attachments_index
- traceability_log
