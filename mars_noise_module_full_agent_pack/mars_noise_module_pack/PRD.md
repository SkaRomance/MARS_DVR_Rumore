# PRD - Modulo DVR Rischio Rumore MARS

## 1. Visione prodotto

Realizzare un modulo verticale per la valutazione del rischio rumore capace di assistere il consulente dall'inquadramento iniziale dell'azienda fino alla generazione del capitolo specialistico del DVR e alla sua integrazione nel DVR generale.

## 2. Problema

La valutazione rumore richiede:
- conoscenza normativa;
- conoscenza tecnica di processi e attrezzature;
- raccolta dati coerente;
- calcolo corretto dei livelli di esposizione;
- narrativa documentale aderente alla realtà aziendale.

I software attuali spesso separano troppo:
- anagrafica aziendale;
- processi;
- macchine;
- misure;
- elaborato finale.

## 3. Obiettivi

### Obiettivi di business
- Aumentare il valore percepito del software consulenti MARS
- Ridurre tempo medio di istruttoria del rischio rumore
- Aumentare il tasso di riuso dati nel DVR generale
- Rendere MARS differenziante sul mercato dei software HSE

### Obiettivi utente
- Avviare una valutazione partendo da ATECO e processi tipici
- Ottenere suggerimenti su sorgenti rumorose e mansioni esposte
- Importare o registrare misure fonometriche
- Calcolare LEX,8h e picchi
- Generare testo tecnico modificabile
- Riesportare tutto nel DVR generale

## 4. Scope MVP

### Incluso nell'MVP
- Anagrafica valutazione rumore
- Motore di riconoscimento iniziale ATECO/processi
- Catalogo sorgenti di rumore / macchinari
- Inserimento tempi di esposizione
- Inserimento dati misurati o stimati
- Calcolo base LEX,8h
- Classificazione soglie
- Misure di prevenzione/protezione suggerite
- Generazione capitolo DVR rumore
- Export verso DVR generale
- Prompt AI guidati

### Escluso dall'MVP
- Analisi realtime da file audio
- Integrazione diretta con fonometri IoT certificati
- CAD/layout acustico
- Simulazioni avanzate ambientali 3D

## 5. User stories

### HSE Consultant
Come consulente, voglio partire dal codice ATECO e dalle lavorazioni aziendali per ottenere una prima bozza di processi e sorgenti rumorose, così da risparmiare tempo di setup.

### Senior Consultant
Come consulente senior, voglio sovrascrivere ogni stima automatica con dati di misura e note tecniche, così da mantenere controllo completo del documento.

### Document Specialist
Come redattore DVR, voglio importare il capitolo rumore nel DVR generale con riferimenti coerenti a mansioni, DPI, sorveglianza sanitaria e piano di miglioramento.

### AI-assisted User
Come utente che usa l'assistente AI, voglio poter scrivere un prompt naturale come “azienda metalmeccanica con taglio plasma, piegatura e compressore centrale” e ottenere una bozza strutturata della valutazione.

## 6. Funzioni principali

1. Setup valutazione
2. Riconoscimento processi e attrezzature
3. Mappatura mansioni-esposizioni
4. Import/registrazione misure
5. Calcolo esposizione
6. Raccomandazioni normative e tecniche
7. Generazione testo DVR
8. Integrazione DVR generale
9. Versioning e audit trail

## 7. Requisiti funzionali

### RF-01 - Creazione valutazione
Il sistema deve consentire la creazione di una nuova valutazione rumore collegata a:
- azienda
- unità produttiva
- reparto
- processo
- mansione

### RF-02 - Inquadramento ATECO
Il sistema deve poter associare uno o più codici ATECO all'azienda e proporre:
- processi tipici
- attrezzature comuni
- mansioni standard
- sorgenti di rumore potenziali

### RF-03 - Catalogo attrezzature
Il sistema deve avere un catalogo di:
- macchinari
- utensili
- impianti
- mezzi di movimentazione
- sorgenti ausiliarie
con campi per potenza sonora / livelli noti / note

### RF-04 - Input dati
Il sistema deve accettare:
- stime da knowledge base
- dati manuali del consulente
- misure strumentali
- allegati (relazioni fonometriche, foto, manuali macchina)

### RF-05 - Calcolo
Il sistema deve calcolare:
- LEX,8h
- eventuali normalizzazioni temporali
- confronto con valori d'azione inferiori, superiori e limite
- indicatori sintetici di priorità

### RF-06 - Prompt AI
Il sistema deve permettere:
- prompt libero
- prompt guidato
- revisione AI dei dati
- generazione narrativa del capitolo
- spiegazione tecnica delle soglie e misure suggerite

### RF-07 - Export
Il sistema deve esportare:
- sezione specialistica rumore
- dati strutturati per il DVR generale
- misure e allegati
- log delle ipotesi usate

## 8. Requisiti non funzionali

- Auditabilità completa
- Versionamento
- Logging per origine dato
- Multi-tenant
- Sicurezza ruoli/permessi
- Performance adeguata su dataset medi
- Tracciabilità normativa
- Explainability AI

## 9. Acceptance criteria

- Da ATECO + prompt + processi l'utente ottiene una bozza iniziale in meno di 5 minuti
- Ogni sorgente di rischio è modificabile manualmente
- Ogni valore è etichettato per origine dato
- Il capitolo esportato è coerente con il DVR generale
- Il consulente può rigenerare il testo mantenendo i dati approvati

## 10. KPI di prodotto

- Tempo medio di setup iniziale
- Percentuale campi precompilati confermati
- Tempo medio di generazione capitolo
- Numero revisioni AI -> approvazione
- Tasso di riuso dati nel DVR generale
