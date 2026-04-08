# Ricerca banche dati e fonti collegabili - Modulo Rumore

## Obiettivo
Creare una base dati aggiornabile che supporti:
- classificazione ATECO
- processi tipici
- macchinari
- sorgenti di rumore
- livelli sonori noti o stimabili
- riferimenti tecnici e normativi

## Fonti prioritarie

### 1. ISTAT / ATECO
Uso:
- classificazione attività economiche
- mappatura iniziale settore -> processi standard

Modalità:
- import periodico da dataset ufficiali o tabelle pubblicate
- salvataggio in cache locale versionata
- mantenimento tabella `ateco_codes`

### 2. INAIL
Uso:
- linee guida
- pubblicazioni tecniche
- banche dati prevenzionali e buone prassi
- riferimenti su attrezzature, comparti, esposizioni, misure di prevenzione

Modalità:
- ingestion documentale controllata
- parser di documenti PDF/HTML autorizzati
- knowledge indexing con metadati di fonte
- nessuna “scrittura” su sistemi esterni

### 3. Ministero del Lavoro / normativa consolidata
Uso:
- aggiornamenti normativi
- rinvii legislativi
- eventuali interpelli/indirizzi ufficiali

Modalità:
- monitoraggio periodico pagine istituzionali
- registrazione versione norma

### 4. UNI / ISO (metadati, non riproduzione integrale se licenziata)
Uso:
- riferimenti metodologici
- norma tecnica applicata

Modalità:
- memorizzazione metadati di riferimento
- link al repertorio
- nessuna duplicazione illegittima del testo integrale

### 5. Manuali costruttore / dati macchina
Uso:
- emissioni acustiche dichiarate
- potenza sonora
- pressione sonora in postazione

Modalità:
- archivio documenti caricabili dal consulente
- estrazione assistita campi chiave
- catalogazione per marca/modello

### 6. Open data / banche dati macchinari e sicurezza prodotto
Uso:
- metadati macchina
- categorie e famiglie di attrezzature
- eventuali certificazioni / schede

Modalità:
- ingestion API se disponibili
- scraping solo se ammesso da termini d'uso
- preferenza assoluta per dataset open o esportabili

### 7. Knowledge base interna MARS
Uso:
- consolidamento pattern ricorrenti
- apprendimento supervisionato da casi reali validati
- benchmark interno per comparti

Modalità:
- solo dati confermati e anonimizzati
- etichettatura per confidenza e origine

## Strategia tecnica di collegamento

### Livello 1 - Static import
Per dataset relativamente stabili:
- ATECO
- classificazioni processi
- mapping comparti

### Livello 2 - Scheduled sync
Per fonti aggiornabili:
- pagine tecniche INAIL
- repertori documentali
- fonti istituzionali

### Livello 3 - Human-in-the-loop ingestion
Per dati difficili da strutturare:
- manuali macchina
- relazioni fonometriche
- schede tecniche PDF

## Regole di qualità dati

Ogni record deve avere:
- `source_name`
- `source_url`
- `source_type`
- `retrieved_at`
- `effective_from`
- `confidence_level`
- `human_validated`
- `license_note`

## Strategia di aggiornamento

- sync mensile per fonti istituzionali
- sync trimestrale per mapping ATECO-processi
- aggiornamento on-demand per manuali e relazioni caricate
- changelog obbligatorio per ogni revisione knowledge base

## Warning progettuale

Il sistema deve evitare di presentare come “dato ufficiale misurato” ciò che è solo:
- stima comparto
- dato costruttore
- inferenza AI
- analogia con casi simili
