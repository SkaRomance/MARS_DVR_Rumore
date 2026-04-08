# Workflow OpenCode CLI

## Modalità PLAN
1. carica `CONTEXT.md`
2. carica `PRD.md`
3. carica agent pack `agents/plan/glm51-cloud/agents.md`
4. fai spawn degli agenti senior di analisi e architettura
5. consolida output in tasks e architecture notes

## Modalità BUILD
1. carica `CONTEXT.md`
2. carica `PRD.md`
3. carica `DATA_MODEL.md`, `API_SPEC.md`, `NOISE_CALCULATION_SPEC.md`
4. carica agent pack `agents/build/minimax27-cloud/agents.md`
5. fai spawn agenti coding/test/review
6. genera branch, tasks e patch

## Regola
Mai consentire a build agents di modificare requisiti senza passare dai plan agents.
