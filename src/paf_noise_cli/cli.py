from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("paf_noise_cli")

DEFAULT_BASE_URL = "http://www.portaleagentifisici.it"
LIST_PATH = "/fo_rumore_list_macchinari.php"
DETAIL_PATH = "/fo_rumore_viewer_for_macchianario.php"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36 paf-noise-cli/0.1.0"
)

OBJ_ID_RE = re.compile(r"fo_rumore_viewer_for_macchianario\.php\?objId=(\d+)", re.IGNORECASE)
PAGE_RE = re.compile(r"fo_rumore_list_macchinari\.php\?[^\"'#>]*?\bpage=(\d+)", re.IGNORECASE)
TOTAL_COUNT_RE = re.compile(r"Banca dati - macchinari:\s*([\d.]+)", re.IGNORECASE)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
KEY_VALUE_RE = re.compile(r"^(?P<label>[^:]{1,120}):\s*(?P<value>.+?)\s*$")
YEAR_RE = re.compile(r"Costruito nel\s+(\d{4})", re.IGNORECASE)
NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
DB_VALUE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(dBA|dBC|dB)", re.IGNORECASE)
METRIC_RE = re.compile(
    r"(?P<label>L_Aeq|L_Ceq|L_WA|L_picco|P_peak)"
    r"(?P<gap>.{0,80}?)"
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>dBA|dBC|dB)",
    re.IGNORECASE | re.DOTALL,
)
FOOTER_MARKERS = (
    "Diritti Valori Innovazione",
    "Newsletter",
    "LOADING TIME:",
    "Made by MIRIGOO",
)


FIELD_MAP = {
    "marca": "brand",
    "modello": "model",
    "tipologia": "typology",
    "peso": "weight",
    "potenza": "power",
    "alimentazione": "power_source",
    "cilindrata": "displacement",
    "norma_di_riferimento": "reference_standard",
    "referente": "referent",
    "stato_di_manutenzione": "maintenance_status",
    "lavoro_effettuato": "work_performed",
    "condizioni_ambiente": "environment",
    "tipo_terreno_strada": "terrain_type",
    "condizioni_terreno_strada": "terrain_conditions",
    "velocita_di_avanzamento": "travel_speed",
    "materiale_lavorato": "material_processed",
    "lavoro_effettuato_es_perforazione_roccia_levigatura_legno_etc": "work_activity_detail",
    "condizioni_misura": "measurement_conditions",
    "presenza_superfici_riflettenti": "reflective_surfaces",
}

METRIC_TOKEN_PATTERNS = (
    (re.compile(r"L\s*_?\s*\{?\s*Aeq\s*\}?", re.IGNORECASE), "L_Aeq"),
    (re.compile(r"L\s*_?\s*\{?\s*Ceq\s*\}?", re.IGNORECASE), "L_Ceq"),
    (re.compile(r"L\s*_?\s*\{?\s*WA\s*\}?", re.IGNORECASE), "L_WA"),
    (re.compile(r"L\s*_?\s*\{?\s*picco\s*\}?", re.IGNORECASE), "L_picco"),
    (re.compile(r"P\s*_?\s*\{?\s*peak\s*\}?", re.IGNORECASE), "P_peak"),
)


@dataclass(frozen=True)
class CliConfig:
    base_url: str
    timeout_seconds: float
    retries: int
    delay_seconds: float
    user_agent: str = DEFAULT_USER_AGENT


@dataclass(frozen=True)
class ListPageInfo:
    total_count: int | None
    max_page: int
    obj_ids: list[int]


@dataclass(frozen=True)
class MetricObservation:
    metric: str
    value: float
    unit: str
    raw: str


@dataclass(frozen=True)
class MeasurementSection:
    heading: str
    lines: list[str]
    metrics: list[MetricObservation] = field(default_factory=list)
    octave_bands: dict[str, float] = field(default_factory=dict)


@dataclass
class MachineRecord:
    obj_id: int
    source_url: str
    page_title: str | None
    machine: dict[str, str] = field(default_factory=dict)
    machine_numeric: dict[str, float | int] = field(default_factory=dict)
    declared_values: dict[str, Any] = field(default_factory=dict)
    related_risks: list[str] = field(default_factory=list)
    context: dict[str, str] = field(default_factory=dict)
    context_details: dict[str, str] = field(default_factory=dict)
    conditions: dict[str, str] = field(default_factory=dict)
    measured_power: dict[str, Any] = field(default_factory=dict)
    measurements: list[MeasurementSection] = field(default_factory=list)
    other_sections: dict[str, list[str]] = field(default_factory=dict)
    raw_lines: list[str] = field(default_factory=list)
    raw_text: str = ""


class VisibleTextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "article",
        "aside",
        "blockquote",
        "caption",
        "div",
        "dl",
        "dt",
        "dd",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "section",
        "table",
        "tbody",
        "thead",
        "tfoot",
        "tr",
        "ul",
    }
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
    CELL_TAGS = {"td", "th"}
    SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "br":
            self._parts.append("\n")
        elif tag in self.HEADING_TAGS:
            level = max(int(tag[1]) - 1, 1)
            self._parts.append("\n" + ("#" * level) + " ")
        elif tag in self.CELL_TAGS:
            self._parts.append(" ")
        elif tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self.CELL_TAGS:
            self._parts.append(" | ")
        elif tag in self.BLOCK_TAGS or tag in self.HEADING_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._parts.append(data)

    def get_lines(self) -> list[str]:
        text = "".join(self._parts)
        lines: list[str] = []
        for raw_line in text.splitlines():
            line = normalize_space(unescape(raw_line))
            if line:
                lines.append(line)
        return lines


class NoiseDatabaseClient:
    def __init__(self, config: CliConfig) -> None:
        self._config = config
        self.base_url = config.base_url
        self._lock = threading.Lock()
        self._last_request_time = 0.0

    def fetch(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self._config.retries + 1):
            self._respect_delay()
            request = Request(
                url,
                headers={
                    "User-Agent": self._config.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.6,en;q=0.4",
                    "Cache-Control": "no-cache",
                },
            )
            try:
                with urlopen(request, timeout=self._config.timeout_seconds) as response:
                    payload = response.read()
                    return decode_response_bytes(payload, response.headers.get_content_charset())
            except (HTTPError, URLError, TimeoutError, OSError) as err:
                last_error = err
                if attempt == self._config.retries:
                    break
                backoff_seconds = self._config.delay_seconds * attempt
                LOGGER.warning(
                    "tentativo %s/%s fallito per %s: %s; ritento tra %.1fs",
                    attempt,
                    self._config.retries,
                    url,
                    err,
                    backoff_seconds,
                )
                time.sleep(backoff_seconds)
        raise RuntimeError(f"impossibile scaricare {url}: {last_error}") from last_error

    def _respect_delay(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._config.delay_seconds:
                time.sleep(self._config.delay_seconds - elapsed)
            self._last_request_time = time.monotonic()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 1
    try:
        return args.handler(args)
    except KeyboardInterrupt:
        LOGGER.error("interrotto dall'utente")
        return 130
    except Exception as err:  # noqa: BLE001
        LOGGER.error("%s", err)
        if args.verbose:
            raise
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paf-noise",
        description="Esporta la banca dati rumore del Portale Agenti Fisici.",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="aumenta il livello di log")

    subparsers = parser.add_subparsers(dest="command")

    discover_parser = subparsers.add_parser("discover", help="scansiona la lista paginata e salva gli objId")
    discover_parser.add_argument(
        "-v", "--verbose", action="count", default=argparse.SUPPRESS, help="aumenta il livello di log"
    )
    add_network_options(discover_parser)
    discover_parser.add_argument("--start-page", type=int, default=1, help="prima pagina da leggere")
    discover_parser.add_argument("--end-page", type=int, help="ultima pagina da leggere; default: autodetect")
    discover_parser.add_argument(
        "--output",
        type=Path,
        default=Path("exports") / "paf_noise_manifest.json",
        help="file JSON con metadati e lista objId",
    )
    discover_parser.set_defaults(handler=handle_discover)

    export_parser = subparsers.add_parser("export", help="scarica le schede e produce JSONL/CSV")
    export_parser.add_argument(
        "-v", "--verbose", action="count", default=argparse.SUPPRESS, help="aumenta il livello di log"
    )
    add_network_options(export_parser)
    export_parser.add_argument("--start-page", type=int, default=1, help="prima pagina da leggere")
    export_parser.add_argument("--end-page", type=int, help="ultima pagina da leggere; default: autodetect")
    export_parser.add_argument("--workers", type=int, default=2, help="numero di download concorrenti per le schede")
    export_parser.add_argument("--limit", type=int, help="limita il numero di schede esportate")
    export_parser.add_argument("--skip-existing", action="store_true", help="salta i dettagli già salvati in raw/")
    export_parser.add_argument("--save-html", action="store_true", help="salva anche l'HTML grezzo di ogni scheda")
    export_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("exports") / "paf_rumore",
        help="cartella di output",
    )
    export_parser.set_defaults(handler=handle_export)

    parse_parser = subparsers.add_parser("parse-html", help="parsa una scheda HTML salvata localmente")
    parse_parser.add_argument(
        "-v", "--verbose", action="count", default=argparse.SUPPRESS, help="aumenta il livello di log"
    )
    parse_parser.add_argument("html_file", type=Path, help="file HTML della scheda")
    parse_parser.add_argument("--obj-id", type=int, default=0, help="objId da associare al record")
    parse_parser.add_argument("--url", default="", help="URL sorgente da riportare nell'output")
    parse_parser.add_argument(
        "--output",
        type=Path,
        help="se presente salva il JSON del record su file, altrimenti stampa su stdout",
    )
    parse_parser.set_defaults(handler=handle_parse_html)

    return parser


def add_network_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, help="base URL del portale; default: http://www.portaleagentifisici.it"
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="timeout per richiesta HTTP")
    parser.add_argument("--retries", type=int, default=3, help="numero massimo di tentativi per richiesta")
    parser.add_argument("--delay", type=float, default=0.5, help="attesa minima tra richieste HTTP")


def handle_discover(args: argparse.Namespace) -> int:
    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client = NoiseDatabaseClient(build_config(args))
    manifest = discover_manifest(client, start_page=args.start_page, end_page=args.end_page)
    write_json(output_path, manifest)
    LOGGER.info("manifest salvato in %s con %s objId", output_path, len(manifest["obj_ids"]))
    return 0


def handle_export(args: argparse.Namespace) -> int:
    output_dir: Path = args.output_dir
    raw_dir = output_dir / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.save_html:
        raw_dir.mkdir(parents=True, exist_ok=True)

    client = NoiseDatabaseClient(build_config(args))
    manifest = discover_manifest(client, start_page=args.start_page, end_page=args.end_page)
    obj_ids = manifest["obj_ids"]
    if args.limit is not None:
        obj_ids = obj_ids[: args.limit]

    jsonl_path = output_dir / "machines.jsonl"
    csv_path = output_dir / "machines_summary.csv"
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, {**manifest, "selected_obj_ids": obj_ids})

    records: list[MachineRecord] = []
    total = len(obj_ids)
    LOGGER.info("inizio export di %s schede", total)
    with ThreadPoolExecutor(max_workers=max(args.workers, 1)) as executor:
        future_map = {
            executor.submit(
                fetch_and_parse_record,
                client=client,
                obj_id=obj_id,
                raw_dir=raw_dir,
                save_html=args.save_html,
                skip_existing=args.skip_existing,
            ): obj_id
            for obj_id in obj_ids
        }
        completed = 0
        for future in as_completed(future_map):
            obj_id = future_map[future]
            completed += 1
            record = future.result()
            records.append(record)
            LOGGER.info("[%s/%s] objId=%s", completed, total, obj_id)

    records.sort(key=lambda item: item.obj_id)
    write_jsonl(jsonl_path, records)
    write_summary_csv(csv_path, records)
    LOGGER.info("export completato: %s e %s", jsonl_path, csv_path)
    return 0


def handle_parse_html(args: argparse.Namespace) -> int:
    html = args.html_file.read_text(encoding="utf-8")
    record = parse_detail_page(
        obj_id=args.obj_id,
        url=args.url or str(args.html_file),
        html=html,
    )
    payload = json.dumps(asdict(record), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


def build_config(args: argparse.Namespace) -> CliConfig:
    return CliConfig(
        base_url=args.base_url.rstrip("/"),
        timeout_seconds=args.timeout,
        retries=args.retries,
        delay_seconds=args.delay,
    )


def discover_manifest(
    client: NoiseDatabaseClient,
    *,
    start_page: int,
    end_page: int | None,
) -> dict[str, Any]:
    first_page = fetch_list_page(client, start_page)
    first_info = parse_list_page(first_page)
    max_page = end_page or first_info.max_page or start_page

    discovered_ids = set(first_info.obj_ids)
    total_count = first_info.total_count
    pages = {
        start_page: {
            "obj_ids": sorted(first_info.obj_ids),
        }
    }
    for page in range(start_page + 1, max_page + 1):
        html = fetch_list_page(client, page)
        info = parse_list_page(html)
        discovered_ids.update(info.obj_ids)
        pages[page] = {"obj_ids": sorted(info.obj_ids)}

    return {
        "base_url": client.base_url,
        "list_url_template": build_list_url(client.base_url, page="{page}"),
        "detail_url_template": build_detail_url(client.base_url, obj_id="{objId}"),
        "total_count": total_count,
        "start_page": start_page,
        "end_page": max_page,
        "obj_ids": sorted(discovered_ids),
        "pages": pages,
    }


def fetch_and_parse_record(
    *,
    client: NoiseDatabaseClient,
    obj_id: int,
    raw_dir: Path,
    save_html: bool,
    skip_existing: bool,
) -> MachineRecord:
    url = build_detail_url(client.base_url, obj_id=obj_id)
    html_path = raw_dir / f"{obj_id}.html"
    if save_html and skip_existing and html_path.exists():
        html = html_path.read_text(encoding="utf-8")
    else:
        html = client.fetch(url)
        if save_html:
            html_path.write_text(html, encoding="utf-8")
    return parse_detail_page(obj_id=obj_id, url=url, html=html)


def fetch_list_page(client: NoiseDatabaseClient, page: int) -> str:
    return client.fetch(build_list_url(client.base_url, page=page))


def build_list_url(base_url: str, *, page: int | str) -> str:
    query = urlencode({"lg": "IT", "page": page})
    return f"{base_url}{LIST_PATH}?{query}"


def build_detail_url(base_url: str, *, obj_id: int | str) -> str:
    query = urlencode({"objId": obj_id})
    return f"{base_url}{DETAIL_PATH}?{query}"


def parse_list_page(html: str) -> ListPageInfo:
    total_match = TOTAL_COUNT_RE.search(html)
    total_count = parse_int(total_match.group(1).replace(".", "")) if total_match else None
    obj_ids = sorted({int(match) for match in OBJ_ID_RE.findall(html)})
    page_numbers = [int(match) for match in PAGE_RE.findall(html)]
    max_page = max(page_numbers, default=1)
    return ListPageInfo(total_count=total_count, max_page=max_page, obj_ids=obj_ids)


def parse_detail_page(*, obj_id: int, url: str, html: str) -> MachineRecord:
    page_title = extract_html_title(html)
    lines = extract_relevant_lines(html)
    record = MachineRecord(
        obj_id=obj_id, source_url=url, page_title=page_title, raw_lines=lines, raw_text="\n".join(lines)
    )

    declared_idx = find_line_index(lines, lambda line: "Valori dichiarati ai sensi della norma" in line)
    risks_idx = find_line_index(
        lines, lambda line: "Questo macchinario potrebbe avere anche dei rischi derivanti da" in line
    )
    comparto_idx = find_line_index(lines, lambda line: "COMPARTO:" in line)
    condizioni_idx = find_line_index(lines, lambda line: line.lstrip("# ").strip() == "Condizioni")
    power_idx = find_line_index(lines, lambda line: "LIVELLO DI POTENZA ACUSTICA MISURATA" in line)
    measurement_indices = [
        index
        for index, line in enumerate(lines)
        if line.startswith("### MISURA") or line.startswith("## MISURA") or line.startswith("# MISURA")
    ]

    machine_end = min_non_negative(declared_idx, risks_idx, comparto_idx, len(lines))
    parse_machine_metadata(lines[:machine_end], record)

    if declared_idx != -1:
        declared_end = min_non_negative(risks_idx, comparto_idx, len(lines))
        parse_declared_values(lines[declared_idx:declared_end], record)

    if risks_idx != -1:
        record.related_risks = parse_related_risks(lines[risks_idx])

    if comparto_idx != -1:
        context_end = min_non_negative(condizioni_idx, power_idx, len(lines))
        parse_context_block(lines[comparto_idx:context_end], record)

    if condizioni_idx != -1:
        conditions_end = min_non_negative(power_idx, *(measurement_indices or [len(lines)]), len(lines))
        parse_key_value_block(lines[condizioni_idx + 1 : conditions_end], record.conditions)

    if power_idx != -1:
        power_end = min_non_negative(*(measurement_indices or [len(lines)]), len(lines))
        parse_measured_power(lines[power_idx:power_end], record)

    if measurement_indices:
        section_endpoints = measurement_indices[1:] + [len(lines)]
        for section_start, section_end in zip(measurement_indices, section_endpoints, strict=True):
            section = build_measurement_section(lines[section_start:section_end])
            record.measurements.append(section)

    extra_sections = extract_generic_sections(
        lines,
        measurement_indices,
        ignored_indices={declared_idx, comparto_idx, condizioni_idx, power_idx},
    )
    record.other_sections.update(extra_sections)
    return record


def extract_generic_sections(
    lines: list[str],
    measurement_indices: list[int],
    *,
    ignored_indices: set[int],
) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    heading_indices = [
        index
        for index, line in enumerate(lines)
        if line.startswith("#") and index not in ignored_indices and index not in measurement_indices
    ]
    if not heading_indices:
        return sections
    endpoints = heading_indices[1:] + [len(lines)]
    for heading_index, section_end in zip(heading_indices, endpoints, strict=True):
        heading = lines[heading_index].lstrip("# ").strip()
        if heading in {"Scheda Macchinario", "Condizioni"}:
            continue
        body = [line for line in lines[heading_index + 1 : section_end] if line]
        if body:
            sections[heading] = body
    return sections


def parse_machine_metadata(lines: list[str], record: MachineRecord) -> None:
    for line in lines:
        year_match = YEAR_RE.search(line)
        if year_match:
            year = int(year_match.group(1))
            record.machine["construction_year_raw"] = line
            record.machine_numeric["construction_year"] = year
            continue
        parsed = parse_key_value_line(line)
        if not parsed:
            continue
        key, value = parsed
        record.machine[key] = value
        maybe_add_numeric_value(key, value, record.machine_numeric)


def parse_declared_values(lines: list[str], record: MachineRecord) -> None:
    if not lines:
        return
    block_text = "\n".join(lines)
    record.declared_values["raw_text"] = block_text
    first_line = lines[0]
    declared_norm = first_line.split("norma", 1)[-1].strip()
    if declared_norm:
        record.declared_values["declared_standard"] = declared_norm

    header_idx = find_line_index(lines, lambda line: "Livello pressione acustica" in line)
    if header_idx > 0:
        standard_title = " ".join(line for line in lines[1:header_idx] if line)
        if standard_title:
            record.declared_values["declared_standard_title"] = standard_title

    if "Nessun dato dichiarato" in block_text:
        record.declared_values["none_declared"] = True
        return

    numeric_lines: list[str] = []
    note_lines: list[str] = []
    for line in lines[header_idx + 1 if header_idx != -1 else 1 :]:
        if not any(char.isdigit() for char in line):
            continue
        lowered = line.lower()
        if "valore di picco" in lowered or "note" in lowered:
            note_lines.append(line)
            continue
        if (
            line.startswith("L_")
            or line.startswith("L{")
            or "dBA" not in line
            and "dBC" not in line
            and "dB" not in line
        ):
            continue
        numeric_lines.append(line)

    if len(numeric_lines) >= 1:
        first_match = DB_VALUE_RE.search(numeric_lines[0])
        if first_match:
            record.declared_values["laeq_dba"] = parse_float(first_match.group(1))
    if len(numeric_lines) >= 2:
        second_match = DB_VALUE_RE.search(numeric_lines[1])
        if second_match:
            record.declared_values["lwa_dba"] = parse_float(second_match.group(1))
    if note_lines:
        cleaned_note = normalize_space(" ".join(line.strip(" |") for line in note_lines))
        if cleaned_note:
            record.declared_values["note"] = cleaned_note


def parse_related_risks(line: str) -> list[str]:
    _, _, tail = line.partition(":")
    cleaned = normalize_space(tail)
    if not cleaned:
        return []
    return [item.strip() for item in re.split(r"[|/,;]+", cleaned) if item.strip()]


def parse_context_block(lines: list[str], record: MachineRecord) -> None:
    if not lines:
        return
    first_line = lines[0].lstrip("# ").strip()
    record.context.update(parse_inline_context_values(first_line))
    parse_key_value_block(lines[1:], record.context_details)


def parse_measured_power(lines: list[str], record: MachineRecord) -> None:
    if not lines:
        return
    first_line = lines[0]
    if "Norma di riferimento:" in first_line:
        _, _, tail = first_line.partition("Norma di riferimento:")
        record.measured_power["reference_standard"] = normalize_space(tail)
    for line in lines[1:]:
        if line.startswith("*"):
            continue
        metric_match = re.search(r"L\s*_\{?\s*WA\s*\}?\s*(\d+(?:[.,]\d+)?)\s*(dBA|dB)", line, re.IGNORECASE)
        if metric_match:
            record.measured_power["lwa"] = parse_float(metric_match.group(1))
            record.measured_power["unit"] = metric_match.group(2)
        uncertainty_match = re.search(r"±\s*(\d+(?:[.,]\d+)?)", line)
        if uncertainty_match:
            record.measured_power["uncertainty"] = parse_float(uncertainty_match.group(1))
        if line:
            record.measured_power.setdefault("raw_lines", []).append(line)


def build_measurement_section(lines: list[str]) -> MeasurementSection:
    heading = lines[0].lstrip("# ").strip() if lines else "MISURA"
    body = [line for line in lines[1:] if line and not line.startswith("*")]
    metrics = extract_metrics("\n".join(body))
    octave_bands = extract_octave_bands(body)
    return MeasurementSection(heading=heading, lines=body, metrics=metrics, octave_bands=octave_bands)


def parse_key_value_block(lines: list[str], target: dict[str, str]) -> None:
    for line in lines:
        parsed = parse_key_value_line(line)
        if not parsed:
            continue
        key, value = parsed
        target[key] = value


def parse_key_value_line(line: str) -> tuple[str, str] | None:
    match = KEY_VALUE_RE.match(line)
    if not match:
        return None
    label = slugify_label(match.group("label"))
    value = normalize_space(match.group("value"))
    if not label or not value:
        return None
    canonical = FIELD_MAP.get(label, label)
    return canonical, value


def parse_inline_context_values(line: str) -> dict[str, str]:
    pattern = re.compile(
        r"(COMPARTO|ACCESSORIO|LAVORO EFFETTUATO):\s*(.*?)(?=(?:COMPARTO|ACCESSORIO|LAVORO EFFETTUATO):|$)"
    )
    context: dict[str, str] = {}
    for raw_label, raw_value in pattern.findall(line):
        label = slugify_label(raw_label)
        context[label] = normalize_space(raw_value)
    return context


def extract_metrics(text: str) -> list[MetricObservation]:
    normalized_text = text
    for pattern, replacement in METRIC_TOKEN_PATTERNS:
        normalized_text = pattern.sub(replacement, normalized_text)

    metrics: list[MetricObservation] = []
    seen: set[tuple[str, float, str]] = set()
    for match in METRIC_RE.finditer(normalized_text):
        metric = match.group("label")
        value = parse_float(match.group("value"))
        unit = match.group("unit")
        key = (metric, value, unit)
        if key in seen:
            continue
        seen.add(key)
        metrics.append(
            MetricObservation(
                metric=metric,
                value=value,
                unit=unit,
                raw=normalize_space(match.group(0)),
            )
        )
    return metrics


def extract_octave_bands(lines: list[str]) -> dict[str, float]:
    for index, line in enumerate(lines):
        if "63 HZ" not in line.upper():
            continue
        if index + 1 >= len(lines):
            break
        values_line = lines[index + 1]
        values = [parse_float(item) for item in NUMBER_RE.findall(values_line)]
        if len(values) < 8:
            continue
        bands = ["63_hz", "125_hz", "250_hz", "500_hz", "1000_hz", "2000_hz", "4000_hz", "8000_hz"]
        return {band: value for band, value in zip(bands, values[:8], strict=True)}
    return {}


def extract_relevant_lines(html: str) -> list[str]:
    parser = VisibleTextExtractor()
    parser.feed(html)
    raw_lines = parser.get_lines()
    start_index = find_line_index(raw_lines, lambda line: "Scheda Macchinario" in line)
    if start_index == -1:
        start_index = 0
    trimmed = raw_lines[start_index:]
    end_index = find_line_index(trimmed, lambda line: any(marker in line for marker in FOOTER_MARKERS))
    if end_index != -1:
        trimmed = trimmed[:end_index]

    cleaned: list[str] = []
    for line in trimmed:
        if should_skip_line(line):
            continue
        cleaned.append(line)
    return cleaned


def should_skip_line(line: str) -> bool:
    lower = line.lower()
    if lower in {"image", "newsletter", "eventi", "news"}:
        return True
    if lower.startswith("image:"):
        return True
    if line in {"*", "* * *", "|"}:
        return True
    return False


def maybe_add_numeric_value(key: str, value: str, target: dict[str, float | int]) -> None:
    if key == "weight":
        number = first_number(value)
        if number is not None:
            target["weight_kg"] = number
    elif key == "power":
        number = first_number(value)
        if number is not None:
            target["power_kw"] = number
    elif key == "displacement":
        number = first_number(value)
        if number is not None:
            target["displacement_cc"] = number


def first_number(value: str) -> float | None:
    match = NUMBER_RE.search(value)
    if not match:
        return None
    return parse_float(match.group(0))


def extract_html_title(html: str) -> str | None:
    match = TITLE_RE.search(html)
    if not match:
        return None
    return normalize_space(unescape(match.group(1)))


def decode_response_bytes(payload: bytes, content_charset: str | None) -> str:
    encodings = [encoding for encoding in [content_charset, "utf-8", "cp1252", "latin-1"] if encoding]
    for encoding in encodings:
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[MachineRecord]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def write_summary_csv(path: Path, records: list[MachineRecord]) -> None:
    columns = [
        "obj_id",
        "brand",
        "model",
        "typology",
        "construction_year",
        "weight_kg",
        "power_kw",
        "power_source",
        "displacement_cc",
        "reference_standard",
        "declared_laeq_dba",
        "declared_lwa_dba",
        "declared_note",
        "related_risks",
        "comparto",
        "accessorio",
        "work_performed",
        "environment",
        "measured_power_lwa",
        "measured_power_unit",
        "measured_power_uncertainty",
        "first_measurement_laeq",
        "first_measurement_lceq",
        "first_measurement_peak",
        "source_url",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow(flatten_record(record))


def flatten_record(record: MachineRecord) -> dict[str, Any]:
    metric_index = {metric.metric: metric for metric in (record.measurements[0].metrics if record.measurements else [])}
    peak_metric = metric_index.get("P_peak") or metric_index.get("L_picco")
    return {
        "obj_id": record.obj_id,
        "brand": record.machine.get("brand", ""),
        "model": record.machine.get("model", ""),
        "typology": record.machine.get("typology", ""),
        "construction_year": record.machine_numeric.get("construction_year", ""),
        "weight_kg": record.machine_numeric.get("weight_kg", ""),
        "power_kw": record.machine_numeric.get("power_kw", ""),
        "power_source": record.machine.get("power_source", ""),
        "displacement_cc": record.machine_numeric.get("displacement_cc", ""),
        "reference_standard": record.machine.get("reference_standard", ""),
        "declared_laeq_dba": record.declared_values.get("laeq_dba", ""),
        "declared_lwa_dba": record.declared_values.get("lwa_dba", ""),
        "declared_note": record.declared_values.get("note", ""),
        "related_risks": ", ".join(record.related_risks),
        "comparto": record.context.get("comparto", ""),
        "accessorio": record.context.get("accessorio", ""),
        "work_performed": record.context_details.get("work_performed", "")
        or record.context.get("lavoro_effettuato", ""),
        "environment": record.context_details.get("environment", ""),
        "measured_power_lwa": record.measured_power.get("lwa", ""),
        "measured_power_unit": record.measured_power.get("unit", ""),
        "measured_power_uncertainty": record.measured_power.get("uncertainty", ""),
        "first_measurement_laeq": metric_index.get("L_Aeq").value if metric_index.get("L_Aeq") else "",
        "first_measurement_lceq": metric_index.get("L_Ceq").value if metric_index.get("L_Ceq") else "",
        "first_measurement_peak": peak_metric.value if peak_metric else "",
        "source_url": record.source_url,
    }


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def slugify_label(label: str) -> str:
    cleaned = normalize_space(label).lower()
    cleaned = (
        cleaned.replace("à", "a")
        .replace("è", "e")
        .replace("é", "e")
        .replace("ì", "i")
        .replace("ò", "o")
        .replace("ù", "u")
    )
    cleaned = cleaned.replace("/", " ")
    cleaned = re.sub(r"[^a-z0-9 ]+", "", cleaned)
    return re.sub(r"\s+", "_", cleaned).strip("_")


def parse_float(value: str) -> float:
    return float(value.replace(",", "."))


def parse_int(value: str) -> int:
    return int(value)


def find_line_index(lines: list[str], predicate: Any) -> int:
    for index, line in enumerate(lines):
        if predicate(line):
            return index
    return -1


def min_non_negative(*values: int) -> int:
    candidates = [value for value in values if value >= 0]
    return min(candidates) if candidates else -1


def configure_logging(verbose: int) -> None:
    level = logging.WARNING
    if verbose == 1:
        level = logging.INFO
    elif verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


if __name__ == "__main__":
    raise SystemExit(main())
