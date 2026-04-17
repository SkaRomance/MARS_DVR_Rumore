"""Pydantic schemas for RAG API endpoints."""

from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000, description="Search query text")
    n_results: int = Field(default=5, ge=1, le=20, description="Number of results")
    category: str | None = Field(default=None, description="Filter by category (e.g. 'Rumore')")
    subcategory: str | None = Field(default=None, description="Filter by subcategory")


class RAGResultItem(BaseModel):
    text: str
    source_file: str
    category: str
    subcategory: str
    page_number: int
    relevance_score: float


class RAGQueryResponse(BaseModel):
    query: str
    results: list[RAGResultItem]
    total_found: int
    context: str | None = Field(default=None, description="Pre-built context string for LLM injection")


class RAGIndexResponse(BaseModel):
    pages_extracted: int
    chunks_indexed: int
    collection_stats: dict


class RAGStatsResponse(BaseModel):
    collection_name: str
    total_chunks: int
    chroma_dir: str
