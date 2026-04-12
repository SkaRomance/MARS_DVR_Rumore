"""PDF document extractor for RAG pipeline.

Extracts text from PDF files in the paf_library directory,
preserving metadata (category, subcategory, filename, page).
"""

import fitz
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PAF_LIBRARY_ROOT = Path(__file__).resolve().parents[3] / "paf_library"

CATEGORY_MAP = {
    "campi_elettromagnetici": "Campi Elettromagnetici",
    "Circolari": "Circolari",
    "hav": "HAV - Vibrazioni Avambraccio/Mano",
    "ionizzanti": "Radiazioni Ionizzanti",
    "ionizzanti_norm": "Radiazioni Ionizzanti (Normativa)",
    "iperbariche": "Camere Iperbariche",
    "Linee_Guida": "Linee Guida",
    "microclima": "Microclima",
    "Normativa": "Normativa Generale",
    "ria": "RIA - Radiazioni Ottiche Artificiali",
    "ro_artificiali": "RO Artificiali",
    "ro_naturali": "RO Naturali",
    "rumore": "Rumore",
    "ultrasuoni": "Ultrasuoni",
    "wbv": "WBV - Vibrazioni Corpo Intero",
}

SUBCATEGORY_MAP = {
    "documentazione": "Documentazione",
    "normativa": "Normativa",
    "prevenzione_e_protezione": "Prevenzione e Protezione",
    "valutazione": "Valutazione",
}


@dataclass
class ExtractedPage:
    """A single extracted page from a PDF document."""

    source_file: str
    category: str
    subcategory: str
    page_number: int
    text: str
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.text)


@dataclass
class ExtractedDocument:
    """All extracted pages from a single PDF file."""

    filename: str
    category: str
    subcategory: str
    pages: list[ExtractedPage] = field(default_factory=list)
    total_chars: int = 0

    def add_page(self, page: ExtractedPage):
        self.pages.append(page)
        self.total_chars += page.char_count


class PDFExtractor:
    """Extract text from PDF files in the PAF library."""

    def __init__(self, library_root: Path | None = None):
        self.library_root = library_root or PAF_LIBRARY_ROOT

    def extract_all(self) -> list[ExtractedDocument]:
        """Extract text from all PDFs in the library."""
        documents = []

        for pdf_path in sorted(self.library_root.rglob("*.pdf")):
            try:
                doc = self._extract_single(pdf_path)
                if doc and doc.total_chars > 0:
                    documents.append(doc)
                    logger.info(
                        "Extracted %s: %d pages, %d chars",
                        doc.filename,
                        len(doc.pages),
                        doc.total_chars,
                    )
            except Exception as e:
                logger.error("Failed to extract %s: %s", pdf_path.name, e)

        logger.info("Total documents extracted: %d", len(documents))
        return documents

    def _extract_single(self, pdf_path: Path) -> ExtractedDocument | None:
        """Extract text from a single PDF file."""
        relative = pdf_path.relative_to(self.library_root)
        parts = relative.parts

        category_key = parts[0] if len(parts) > 0 else "unknown"
        subcategory_key = parts[1] if len(parts) > 1 else "generic"

        category = CATEGORY_MAP.get(
            category_key, category_key.replace("_", " ").title()
        )
        subcategory = SUBCATEGORY_MAP.get(
            subcategory_key, subcategory_key.replace("_", " ").title()
        )

        doc = ExtractedDocument(
            filename=str(relative),
            category=category,
            subcategory=subcategory,
        )

        with fitz.open(str(pdf_path)) as pdf:
            for page_num in range(len(pdf)):
                page = pdf[page_num]
                text = page.get_text("text").strip()

                if text and len(text) > 20:
                    extracted = ExtractedPage(
                        source_file=str(relative),
                        category=category,
                        subcategory=subcategory,
                        page_number=page_num + 1,
                        text=text,
                    )
                    doc.add_page(extracted)

        return doc if doc.pages else None

    def extract_to_dicts(self) -> list[dict[str, Any]]:
        """Extract all documents and return as list of dicts (for serialization)."""
        result = []
        for doc in self.extract_all():
            for page in doc.pages:
                result.append(
                    {
                        "source_file": page.source_file,
                        "category": page.category,
                        "subcategory": page.subcategory,
                        "page_number": page.page_number,
                        "text": page.text,
                        "char_count": page.char_count,
                    }
                )
        return result
