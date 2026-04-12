"""Tests for RAG pipeline - Text chunking and RAG service retrieval."""

import os
import pytest
import tempfile
from pathlib import Path
from src.infrastructure.rag.text_chunker import TextChunker, Chunk
from src.infrastructure.rag.rag_service import RAGService


class TestTextChunker:
    def test_chunk_basic(self):
        chunker = TextChunker(chunk_size=200, chunk_overlap=50, min_chunk_size=20)
        pages = [
            {
                "text": "This is a test document. " * 50,
                "source_file": "test.pdf",
                "category": "Test",
                "subcategory": "Unit",
                "page_number": 1,
            }
        ]
        chunks = chunker.chunk_pages(pages)
        assert len(chunks) > 0
        for c in chunks:
            assert c.id.startswith("test.pdf::p1::c")
            assert c.category == "Test"
            assert len(c.text) > 0

    def test_chunk_short_page_skipped(self):
        chunker = TextChunker(min_chunk_size=500)
        pages = [
            {
                "text": "Too short",
                "source_file": "short.pdf",
                "category": "Test",
                "subcategory": "Unit",
                "page_number": 1,
            }
        ]
        chunks = chunker.chunk_pages(pages)
        assert len(chunks) == 0

    def test_chunk_metadata(self):
        chunker = TextChunker(chunk_size=500, min_chunk_size=20)
        pages = [
            {
                "text": "A" * 1000,
                "source_file": "meta.pdf",
                "category": "Rumore",
                "subcategory": "Normativa",
                "page_number": 5,
            }
        ]
        chunks = chunker.chunk_pages(pages)
        assert len(chunks) >= 1
        assert chunks[0].category == "Rumore"
        assert chunks[0].subcategory == "Normativa"
        assert chunks[0].page_number == 5

    def test_chunk_to_dict(self):
        chunk = Chunk(
            id="test::p1::c0",
            text="sample text",
            source_file="test.pdf",
            category="Test",
            subcategory="Unit",
            page_number=1,
            chunk_index=0,
        )
        d = chunk.to_dict()
        assert d["id"] == "test::p1::c0"
        assert d["token_count"] > 0


class TestRAGService:
    def _make_rag(self, tmp_path, name):
        return RAGService(
            chroma_dir=str(tmp_path / name),
            collection_name=name,
        )

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_index_and_query(self, tmp_path):
        rag = self._make_rag(tmp_path, "test_idx_query")
        pages = [
            {
                "text": "Il D.Lgs 81/2008 stabilisce i valori limite di esposizione al rumore per i lavoratori. "
                "Il valore limite di esposizione giornaliero e LEX,8h = 87 dB(A). "
                "Il valore superiore di azione e LEX,8h = 85 dB(A). "
                "Il valore inferiore di azione e LEX,8h = 80 dB(A).",
                "source_file": "normativa.pdf",
                "category": "Rumore",
                "subcategory": "Normativa",
                "page_number": 1,
            },
            {
                "text": "Le vibrazioni trasmesse al sistema braccio-mano sono valutate "
                "secondo la norma ISO 5349. Il valore limite giornaliero di esposizione "
                "e A(8) = 5 m/s2.",
                "source_file": "hav_norm.pdf",
                "category": "HAV",
                "subcategory": "Normativa",
                "page_number": 1,
            },
        ]
        total = await rag.index_documents(pages)
        assert total > 0

        results = await rag.query("valori limite rumore lavoratori", n_results=2)
        assert len(results) > 0

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_query_with_category_filter(self, tmp_path):
        rag = self._make_rag(tmp_path, "test_filter")
        pages = [
            {
                "text": "Articolo 189 del D.Lgs 81/2008: obblighi del datore di lavoro per il rumore.",
                "source_file": "rumore.pdf",
                "category": "Rumore",
                "subcategory": "Normativa",
                "page_number": 10,
            },
            {
                "text": "Radiazioni ionizzanti: limiti di dose per lavoratori esposti categoria A e B.",
                "source_file": "ionizzanti.pdf",
                "category": "Ionizzanti",
                "subcategory": "Normativa",
                "page_number": 5,
            },
        ]
        await rag.index_documents(pages)
        results = await rag.query(
            "obblighi datore lavoro", n_results=1, category_filter="Rumore"
        )
        assert len(results) > 0
        assert results[0]["metadata"]["category"] == "Rumore"

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_build_context(self, tmp_path):
        rag = self._make_rag(tmp_path, "test_ctx")
        pages = [
            {
                "text": "Contesto di test per la costruzione del context RAG con le informazioni normative.",
                "source_file": "test.pdf",
                "category": "Rumore",
                "subcategory": "Doc",
                "page_number": 1,
            }
        ]
        await rag.index_documents(pages)
        results = await rag.query("informazioni normative", n_results=1)
        context = rag.build_context(results, max_chars=500)
        assert "Doc 1" in context
        assert "Rumore" in context

    @pytest.mark.slow
    def test_get_stats(self, tmp_path):
        rag = self._make_rag(tmp_path, "test_stats")
        stats = rag.get_stats()
        assert "collection_name" in stats
        assert stats["total_chunks"] >= 0
