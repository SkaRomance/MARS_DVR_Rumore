# Core Agential Protocol - Presidio Mobilita & Energia

Questo documento impone il comportamento obbligatorio per l'ambiente agenziale OpenCode. Ogni sessione deve rispettare queste regole per garantire qualita, tracciabilita e performance.

## 1. Architettura dei Modelli
- **Pianificazione (Strategia, Architettura, Ricerca)**: 
  - Modello Obbligatorio: `ollama/glm-5.1:cloud`
  - Modalità: Plan Mode attivo, massima potenza, analisi dipendenze.
- **Implementazione (Build, Vibe Coding, UI, Backend)**:
  - Modello Obbligatorio: `ollama/minimax-m2.7:cloud`
  - Modalità: Build Mode attivo, implementazione massiva, focus su test.

## 2. Gestione del Contesto e Loop
- **Stop-on-Incomplete**: Se una query non ha contesto sufficiente (es. interfacce non caricate, PRD non letto, variabili mancanti), l'agente DEVE fermarsi e chiedere chiarimenti all'utente prima di agire.
- **AgentLoop Protocol**: L'attivazione di subagents deve seguire un loop di feedback: 
  1. Tasking -> 2. Execution -> 3. Validation -> 4. Summary.
- **Context Compaction**: Ogni 10 messaggi, l'agente deve riassumere la cronologia e compattare il contesto per evitare il sovraccarico (Context Rot).

## 3. Workflow di Versionamento (Git)
- **Branching**: Ogni macro-task deve lavorare su un branch dedicato (es. `feature/risk-v2`, `fix/auth-leak`).
- **Atomic Commits**: Commit piccoli, descrittivi e frequenti. 
- **Auto-Flow**: Dopo ogni modifica significativa:
  1. Review automatica del codice.
  2. Commit con messaggio standard.
  3. Push sul repository remoto.

## 4. Feedback Interfaccia (UI)
- **Task Progress**: L'agente deve simulare o utilizzare strumenti di interfaccia per mostrare una barra di completamento del task (es. `[████░░░░░░] 40%`) nel footer o nel log di ogni risposta.

## 5. Attivazione
Per attivare questo protocollo, carica questo file nel contesto agenziale all'inizio di ogni sessione.
