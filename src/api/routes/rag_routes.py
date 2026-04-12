"""RAG API routes - Document retrieval and indexing management."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.schemas.rag import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGResultItem,
    RAGIndexResponse,
    RAGStatsResponse,
)
from src.infrastructure.auth.dependencies import get_current_user, require_role
from src.infrastructure.database.models.user import User, UserRole
from src.infrastructure.rag.rag_service import RAGService
from src.infrastructure.rag.pdf_extractor import PDFExtractor

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(
    request: RAGQueryRequest,
    current_user: User = Depends(get_current_user),
):
    """Query the RAG vector store for relevant HSE documents."""
    rag = RAGService()

    try:
        results = await rag.query(
            query_text=request.query,
            n_results=request.n_results,
            category_filter=request.category,
            subcategory_filter=request.subcategory,
        )
    except Exception as e:
        logger.error("RAG query failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RAG query failed",
        )

    items = [
        RAGResultItem(
            text=r["text"][:1000],
            source_file=r["metadata"].get("source_file", ""),
            category=r["metadata"].get("category", ""),
            subcategory=r["metadata"].get("subcategory", ""),
            page_number=r["metadata"].get("page_number", 0),
            relevance_score=r.get("relevance_score", 0),
        )
        for r in results
    ]

    context = rag.build_context(results) if results else None

    return RAGQueryResponse(
        query=request.query,
        results=items,
        total_found=len(items),
        context=context,
    )


@router.post("/index", response_model=RAGIndexResponse)
async def rag_reindex(
    reset: bool = False,
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Re-index all PAF library documents into ChromaDB. Admin only."""
    rag = RAGService()

    if reset:
        rag.reset_collection()

    extractor = PDFExtractor()

    try:
        pages = await asyncio.to_thread(extractor.extract_to_dicts)
    except Exception as e:
        logger.error("PDF extraction failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF extraction failed",
        )

    try:
        chunks_indexed = await rag.index_documents(pages)
    except Exception as e:
        logger.error("Indexing failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document indexing failed",
        )

    stats = rag.get_stats()

    return RAGIndexResponse(
        pages_extracted=len(pages),
        chunks_indexed=chunks_indexed,
        collection_stats=stats,
    )


@router.get("/stats", response_model=RAGStatsResponse)
async def rag_stats(
    current_user: User = Depends(get_current_user),
):
    """Get ChromaDB collection statistics."""
    rag = RAGService()
    stats = rag.get_stats()

    if "error" in stats:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=stats["error"],
        )

    return RAGStatsResponse(
        collection_name=stats["collection_name"],
        total_chunks=stats["total_chunks"],
        chroma_dir=stats["chroma_dir"],
    )
