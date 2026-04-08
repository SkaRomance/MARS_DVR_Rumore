# Data Model - Modulo Rumore MARS

## Entità principali

### company
- id
- name
- vat_number
- ateco_primary
- ateco_secondary[]

### unit_site
- id
- company_id
- name
- address

### process
- id
- company_id
- name
- category
- standard_source
- confidence

### work_phase
- id
- process_id
- name
- description
- typical_duration
- noise_relevance_score

### job_role
- id
- company_id
- name
- description

### machine_asset
- id
- company_id
- manufacturer
- model
- category
- serial_number
- source_type

### noise_source_catalog
- id
- label
- source_family
- typical_range_min
- typical_range_max
- source_reference

### role_phase_exposure
- id
- job_role_id
- work_phase_id
- machine_asset_id nullable
- noise_source_catalog_id nullable
- duration_hours
- laeq_value
- value_origin
- confidence_level

### measurement_session
- id
- company_id
- site_id
- date
- operator
- instrument
- calibration_info
- report_file_id

### measurement_point
- id
- measurement_session_id
- linked_role_phase_exposure_id
- laeq
- peak
- notes

### noise_assessment
- id
- company_id
- site_id
- version
- status
- created_by
- approved_by
- methodology_note

### noise_assessment_result
- id
- noise_assessment_id
- job_role_id
- lex8h
- peak_value
- threshold_band
- action_required
- medical_surveillance_flag
- dpi_flag

### mitigation_action
- id
- noise_assessment_result_id
- type
- priority
- description
- owner
- due_date

### source_registry
- id
- source_name
- source_url
- source_type
- license_note
- retrieved_at
- version_tag

## Relazioni logiche
- company -> unit_site
- company -> job_role
- company -> process
- process -> work_phase
- company -> machine_asset
- job_role + work_phase -> role_phase_exposure
- assessment -> results
- result -> mitigation_action

## Regole chiave
- ogni valore numerico deve avere `value_origin`
- ogni suggerimento AI deve essere distinguibile da un dato validato
- assessment e result devono essere versionati
