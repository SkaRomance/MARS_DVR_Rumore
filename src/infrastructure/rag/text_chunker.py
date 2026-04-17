"""Text chunker for RAG pipeline.

Splits extracted document pages into overlapping chunks
suitable for embedding and retrieval.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A text chunk with metadata for vector storage."""

    id: str
    text: str
    source_file: str
    category: str
    subcategory: str
    page_number: int
    chunk_index: int
    token_count: int = 0

    def __post_init__(self):
        self.token_count = self._estimate_tokens()

    def _estimate_tokens(self) -> int:
        return max(1, len(self.text) // 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "source_file": self.source_file,
            "category": self.category,
            "subcategory": self.subcategory,
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
            "token_count": self.token_count,
        }


class TextChunker:
    """Split document text into overlapping chunks."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_pages(self, pages: list[dict[str, Any]]) -> list[Chunk]:
        """Split extracted pages into chunks."""
        chunks = []
        chunk_counter = 0

        for page in pages:
            text = page["text"]
            if len(text) < self.min_chunk_size:
                continue

            page_chunks = self._split_text(text)

            for i, chunk_text in enumerate(page_chunks):
                chunk_id = f"{page['source_file']}::p{page['page_number']}::c{i}"
                chunk = Chunk(
                    id=chunk_id,
                    text=chunk_text,
                    source_file=page["source_file"],
                    category=page["category"],
                    subcategory=page["subcategory"],
                    page_number=page["page_number"],
                    chunk_index=i,
                )
                chunks.append(chunk)
                chunk_counter += 1

        logger.info("Created %d chunks from %d pages", chunk_counter, len(pages))
        return chunks

    def _split_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks, preferring paragraph boundaries."""
        paragraphs = re.split(r"\n\s*\n", text)

        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            else:
                if current_chunk and len(current_chunk) >= self.min_chunk_size:
                    chunks.append(current_chunk)

                if len(para) > self.chunk_size:
                    sub_chunks = self._split_long_paragraph(para)
                    chunks.extend(sub_chunks[:-1])
                    current_chunk = sub_chunks[-1] if sub_chunks else ""
                else:
                    overlap_text = self._get_overlap(current_chunk)
                    current_chunk = overlap_text + "\n\n" + para if overlap_text else para

        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append(current_chunk)

        return chunks

    def _split_long_paragraph(self, text: str) -> list[str]:
        """Split a paragraph that exceeds chunk_size on sentence boundaries."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        current = ""

        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= self.chunk_size:
                current = current + " " + sentence if current else sentence
            else:
                if current:
                    chunks.append(current)
                overlap = self._get_overlap(current)
                current = overlap + " " + sentence if overlap else sentence

        if current:
            chunks.append(current)

        return chunks

    def _get_overlap(self, text: str) -> str:
        """Get the tail of text for overlap with next chunk."""
        if not text or len(text) <= self.chunk_overlap:
            return ""
        overlap_text = text[-self.chunk_overlap :]
        first_space = overlap_text.find(" ")
        if first_space > 0:
            overlap_text = overlap_text[first_space + 1 :]
        return overlap_text
