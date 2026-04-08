# PAF Noise CLI

CLI Python standard-library only per esportare la banca dati rumore del Portale Agenti Fisici.

## Cosa fa

- Scansiona la lista paginata dei macchinari.
- Estrae tutti gli `objId` delle schede.
- Scarica ogni scheda macchinario.
- Produce `manifest.json`, `machines.jsonl` e `machines_summary.csv`.

Il JSONL mantiene anche `raw_text` e `raw_lines`, così il dato resta disponibile anche quando il parser trova varianti non previste nel markup.

## Requisiti

- Python 3.11+
- Nessuna dipendenza esterna

## Utilizzo

Scopri gli ID presenti nella banca dati:

```bash
.\run_paf_noise.ps1 discover --output .\exports\manifest.json -v
```

Esegui l'export completo:

```bash
.\run_paf_noise.ps1 export --output-dir .\exports\paf_rumore --save-html --workers 2 -v
```

Esegui un export parziale per test:

```bash
.\run_paf_noise.ps1 export --limit 25 --output-dir .\exports\smoke --save-html -v
```

Parsa una scheda HTML già salvata:

```bash
.\run_paf_noise.ps1 parse-html .\exports\paf_rumore\raw\638.html --obj-id 638
```

## Opzioni utili

- `--start-page` / `--end-page`: limita le pagine della lista da leggere
- `--limit`: limita il numero di schede dettagliate da scaricare
- `--workers`: download concorrenti delle schede
- `--delay`: attesa minima tra richieste
- `--base-url`: URL base del portale; di default usa `http://www.portaleagentifisici.it`
- `--timeout`: timeout HTTP
- `--retries`: tentativi per richiesta
- `--skip-existing`: riusa gli HTML già salvati in `raw/`
- `--save-html`: conserva l'HTML grezzo delle schede

## Test

```bash
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
