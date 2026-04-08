"""Script to convert ATECO 2007 XLSX to JSON.

Usage:
    python scripts/convert_ateco.py --input data/ateco/ateco2007.xlsx --output data/ateco/ateco2007.json
"""

import argparse
import json
import hashlib
from pathlib import Path
import openpyxl


def convert_ateco(xlsx_path: str, output_path: str) -> int:
    """Convert ATECO 2007 XLSX to JSON structure.

    Args:
        xlsx_path: Path to ISTAT ATECO 2007 XLSX file
        output_path: Path to output JSON file

    Returns:
        Number of records converted
    """
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active

    ateco_data = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] and isinstance(row[0], str):
            code = str(row[0]).strip()
            description = row[1] if len(row) > 1 and row[1] else ""
            category = row[2] if len(row) > 2 and row[2] else None
            section = row[3] if len(row) > 3 and row[3] else None

            ateco_data.append(
                {
                    "codice": code,
                    "descrizione": str(description).strip() if description else "",
                    "categoria": str(category).strip() if category else None,
                    "sezione": str(section).strip() if section else None,
                }
            )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ateco_data, f, ensure_ascii=False, indent=2)

    return len(ateco_data)


def calculate_hash(json_path: str) -> str:
    """Calculate SHA256 hash of JSON file."""
    with open(json_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Convert ATECO 2007 XLSX to JSON")
    parser.add_argument("--input", "-i", required=True, help="Input XLSX path")
    parser.add_argument("--output", "-o", required=True, help="Output JSON path")
    args = parser.parse_args()

    count = convert_ateco(args.input, args.output)
    print(f"Convertiti {count} record ATECO → {args.output}")

    json_hash = calculate_hash(args.output)
    hash_path = args.output + ".sha256"
    with open(hash_path, "w") as f:
        f.write(json_hash)
    print(f"Hash SHA256: {json_hash}")
    print(f"Hash salvato: {hash_path}")


if __name__ == "__main__":
    main()
