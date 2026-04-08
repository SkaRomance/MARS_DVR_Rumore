# Context File - Modulo Rumore MARS

## Missione

Costruire un modulo specialistico per il rischio rumore che:
- lavori dentro il software consulenti MARS;
- sia interoperabile con il DVR generale;
- supporti raccolta dati, stima, misura, calcolo, generazione elaborato e revisione consulenziale;
- sfrutti basi dati pubbliche e regole di inferenza per una precompilazione intelligente;
- sia pilotabile anche da prompt AI.

## Problema da risolvere

I consulenti oggi compilano la valutazione rumore in modo frammentato:
- raccolta dati manuale;
- fonti informative disperse;
- difficoltà nel collegare ATECO, lavorazioni, macchine e fattori di rischio;
- poca riusabilità dei dati nel DVR generale;
- difficoltà a spiegare in modo semplice ma tecnicamente corretto le misure richieste.

## Valore per MARS

Il modulo:
- aumenta la profondità tecnica del software consulenti;
- riduce il tempo di prima impostazione;
- migliora la qualità documentale;
- crea una knowledge base riutilizzabile su processi, macchinari e sorgenti rumorose;
- rende l'assistente AI realmente operativo su un rischio specifico.

## Obiettivi funzionali

1. Import nel DVR generale dei dati rumore.
2. Mappatura automatica ATECO -> processi -> mansioni -> attrezzature -> fattori di rischio.
3. Distinzione fra:
   - dati stimati da knowledge base;
   - dati dichiarati dal consulente;
   - dati misurati strumentalmente.
4. Personalizzazione completa dei dati e delle ipotesi.
5. Tracciabilità di ogni modifica.
6. Prompt AI per:
   - setup iniziale;
   - revisione tecnica;
   - spiegazione normativa;
   - generazione narrativa del capitolo DVR.

## Vincoli

- Nessuna decisione automatica “chiusa” senza audit trail.
- Tutte le inferenze devono essere etichettate come:
  - suggerite da knowledge base;
  - confermate dal consulente;
  - derivate da misura.
- Il modulo deve poter funzionare anche senza integrazione live, con cache/versioning locale delle basi dati.
- Deve essere predisposto per aggiornamenti periodici e controllati.

## Utenti target

- Consulente HSE senior
- Tecnico della prevenzione
- RSPP esterno
- Datore di lavoro assistito
- Revisore qualità / compliance interno MARS

## Esito atteso

Un sottosistema verticale, solido, auditabile e pronto a essere esteso anche ad altri rischi specifici.
