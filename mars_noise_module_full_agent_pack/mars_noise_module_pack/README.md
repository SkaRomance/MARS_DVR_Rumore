# MARS - Modulo DVR Rumore

Pacchetto documentale per progettazione e sviluppo del modulo **valutazione e generazione DVR sul rischio specifico rumore** per il software consulenti di MARS.

## Contenuto del pacchetto

- `README.md` - guida rapida al pacchetto
- `CONTEXT.md` - contesto di dominio, perimetro prodotto e vincoli
- `PRD.md` - product requirements document completo
- `DATA_SOURCES_RESEARCH.md` - ricerca sulle banche dati pubbliche e modalità di collegamento
- `NOISE_CALCULATION_SPEC.md` - specifica calcolo LEX,8h e logiche tecniche
- `DATA_MODEL.md` - schema dati logico e struttura tabelle
- `API_SPEC.md` - API interne per integrazione con DVR generale
- `AI_PROMPTING_DESIGN.md` - design dell'interazione AI via prompt
- `IMPLEMENTATION_ROADMAP.md` - roadmap di sviluppo
- `GOVERNANCE_AND_COMPLIANCE.md` - governance, auditabilità, logging e responsabilità
- `agents/` - tutti gli agents.md e i file init per modalità PLAN e BUILD
- `templates/` - template di input e output
- `configs/` - configurazioni operative per OpenCode CLI / Ollama

## Obiettivo del modulo

Consentire:
1. riconoscimento iniziale di processi, mansioni, attrezzature e sorgenti di rumore;
2. pre-valutazione assistita tramite ATECO, processi standard e knowledge base pubbliche;
3. valutazione personalizzabile con dati misurati o stimati;
4. generazione del DVR rumore importabile nel DVR generale;
5. uso dell'assistente AI per configurazione, raffinamento e spiegazione tecnica.

## Stack operativo previsto

- **Mod Plan**: `glm 5.1 cloud`
- **Mod Build**: `minimax 2.7:cloud`
- **Run locale/orchestrazione**: `ollama`, `opencode cli`
- **Assistente tecnico-documentale**: agents senior specializzati

## Nota importante

Questo pacchetto è pensato come base di lavoro tecnica e organizzativa.
La valutazione finale del rischio e la firma del DVR restano in capo al professionista abilitato / datore di lavoro secondo la normativa applicabile.
