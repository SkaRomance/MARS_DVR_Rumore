"""RAG Service - Retrieval-Augmented Generation pipeline.

ChromaDB vector store with built-in embedding (all-MiniLM-L6-v2) for document retrieval,
then injects retrieved context into LLM prompts.
"""

import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.infrastructure.rag.text_chunker import Chunk, TextChunker

logger = logging.getLogger(__name__)

CHROMA_PERSIST_DIR = "data/chroma_db"
COLLECTION_NAME = "paf_hse_documents"


class RAGService:
    """RAG pipeline: chunk, store, retrieve, augment.

    Uses ChromaDB's built-in all-MiniLM-L6-v2 embedding model for both
    indexing and querying. If an Ollama embedding endpoint becomes available,
    it can be swapped in via get_embeddings on the OllamaProvider.
    """

    def __init__(
        self,
        chroma_dir: str = CHROMA_PERSIST_DIR,
        collection_name: str = COLLECTION_NAME,
    ):
        self._chroma_dir = chroma_dir
        self._collection_name = collection_name
        self._chunker = TextChunker()
        self._client: chromadb.ClientAPI | None = None
        self._collection = None

    def _get_client(self) -> chromadb.ClientAPI:
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=self._chroma_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._client

    def _get_collection(self):
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    async def index_documents(self, pages: list[dict[str, Any]]) -> int:
        """Chunk pages and store in ChromaDB (uses built-in embedding).

        Returns:
            Number of chunks indexed.
        """
        chunks = self._chunker.chunk_pages(pages)
        if not chunks:
            logger.warning("No chunks to index")
            return 0

        collection = self._get_collection()

        batch_size = 500
        total_indexed = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c.text for c in batch]
            ids = [c.id for c in batch]
            metadatas = [
                {
                    "source_file": c.source_file,
                    "category": c.category,
                    "subcategory": c.subcategory,
                    "page_number": c.page_number,
                    "chunk_index": c.chunk_index,
                }
                for c in batch
            ]

            collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
            )

            total_indexed += len(batch)
            logger.info(
                "Indexed batch %d/%d (%d chunks)",
                i // batch_size + 1,
                (len(chunks) + batch_size - 1) // batch_size,
                len(batch),
            )

        logger.info("Total chunks indexed: %d", total_indexed)
        return total_indexed

    async def query(
        self,
        query_text: str,
        n_results: int = 5,
        category_filter: str | None = None,
        subcategory_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query the vector store for relevant documents.

        Returns:
            List of retrieved chunks with text and metadata.
        """
        collection = self._get_collection()

        where_filter: dict[str, Any] | None = None
        if category_filter or subcategory_filter:
            conditions = []
            if category_filter:
                conditions.append({"category": category_filter})
            if subcategory_filter:
                conditions.append({"subcategory": subcategory_filter})
            if len(conditions) == 1:
                where_filter = conditions[0]
            else:
                where_filter = {"$and": conditions}

        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        retrieved = []
        if results and results.get("documents"):
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            dists = results["distances"][0]

            for doc, meta, dist in zip(docs, metas, dists):
                retrieved.append(
                    {
                        "text": doc,
                        "metadata": meta,
                        "distance": dist,
                        "relevance_score": 1.0 - dist,
                    }
                )

        return retrieved

    def build_context(
        self, retrieved: list[dict[str, Any]], max_chars: int = 4000
    ) -> str:
        """Build a context string from retrieved documents for LLM injection."""
        context_parts = []
        total_chars = 0

        for i, item in enumerate(retrieved):
            meta = item["metadata"]
            source = meta.get("source_file", "unknown")
            page = meta.get("page_number", "?")
            cat = meta.get("category", "")
            score = item.get("relevance_score", 0)

            header = f"[Doc {i + 1}] Fonte: {source} (pag. {page}) - {cat} (rilevanza: {score:.2f})"
            text = item["text"]

            entry = header + "\n" + text
            if total_chars + len(entry) > max_chars:
                remaining = max_chars - total_chars - len(header) - 3
                if remaining > 100:
                    entry = header + "\n" + text[:remaining] + "..."
                else:
                    break

            context_parts.append(entry)
            total_chars += len(entry)

        return "\n\n---\n\n".join(context_parts)

    def get_stats(self) -> dict[str, Any]:
        """Get ChromaDB collection stats."""
        try:
            collection = self._get_collection()
            count = collection.count()
            return {
                "collection_name": self._collection_name,
                "total_chunks": count,
                "chroma_dir": self._chroma_dir,
            }
        except Exception as e:
            return {"error": str(e)}

    def reset_collection(self) -> bool:
        """Delete and recreate the collection (for re-indexing)."""
        try:
            client = self._get_client()
            client.delete_collection(self._collection_name)
            self._collection = None
            logger.info("Collection '%s' deleted", self._collection_name)
            return True
        except Exception as e:
            logger.error("Failed to reset collection: %s", e)
            return False
