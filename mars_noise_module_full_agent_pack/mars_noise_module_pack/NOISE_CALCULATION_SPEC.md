# Specifica tecnica - Calcolo rischio rumore

## Obiettivo
Supportare il calcolo tecnico della valutazione rumore con evidenza di:
- livello di esposizione giornaliera personale
- eventuale confronto con soglie normative
- origine e qualità del dato

## Grandezze principali

- Livello di pressione sonora equivalente ponderato A
- Tempo di esposizione per fase
- Esposizione normalizzata a 8 ore (LEX,8h)
- Livelli di picco, ove inseriti
- Valori d'azione inferiori
- Valori d'azione superiori
- Valore limite di esposizione

## Formula di lavoro (semplificazione implementativa)

Il modulo deve poter gestire n fasi espositive nella giornata lavorativa.

Per ogni fase i:
- `LAeq_i` = livello equivalente ponderato A della fase
- `T_i` = durata della fase in ore

Energia equivalente cumulata:
- somma delle energie pesate sul tempo

Normalizzazione a 8 ore:
- LEX,8h derivato dalla somma energetica rapportata a 8 ore

## Workflow di calcolo

1. Raccolta fasi di lavoro
2. Associazione a mansione / lavoratore tipo
3. Inserimento o stima LAeq per fase
4. Inserimento durata
5. Calcolo energia cumulata
6. Normalizzazione a 8h
7. Confronto con soglie
8. Suggerimento misure

## Tipi di dato gestiti

- `MEASURED`
- `MANUFACTURER_DECLARED`
- `KB_ESTIMATED`
- `CONSULTANT_ENTERED`
- `AI_SUGGESTED`

## Regole software

- Il calcolo deve essere ripetibile e versionato
- La formula applicata deve essere mostrata in modo trasparente
- Ogni risultato deve riportare gli input usati
- Il sistema deve consentire ricalcolo con scenari alternativi

## Output minimi

- LEX,8h per mansione
- Soglia superata sì/no
- Classe di priorità
- Elenco misure tecniche/organizzative suggerite
- Necessità di DPI uditivi / approfondimento strumentale
- Narrative summary pronta per DVR
