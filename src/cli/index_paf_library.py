"""CLI script to index PAF library documents into ChromaDB.

Usage:
    python -m src.cli.index_paf_library [--reset] [--stats]
"""

import asyncio
import argparse
import logging
import sys

from src.infrastructure.rag.pdf_extractor import PDFExtractor
from src.infrastructure.rag.rag_service import RAGService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_index(reset: bool = False):
    """Run the full indexing pipeline."""
    rag = RAGService()

    if reset:
        logger.info("Resetting collection...")
        rag.reset_collection()

    logger.info("Extracting PDFs from paf_library/...")
    extractor = PDFExtractor()
    pages = extractor.extract_to_dicts()
    logger.info("Extracted %d pages", len(pages))

    if not pages:
        logger.error("No pages extracted. Check paf_library/ directory.")
        sys.exit(1)

    logger.info("Indexing into ChromaDB...")
    total = await rag.index_documents(pages)
    logger.info("Indexing complete: %d chunks indexed", total)

    stats = rag.get_stats()
    logger.info("ChromaDB stats: %s", stats)


def show_stats():
    """Show current ChromaDB stats."""
    rag = RAGService()
    stats = rag.get_stats()
    print(f"Collection: {stats.get('collection_name')}")
    print(f"Total chunks: {stats.get('total_chunks', 0)}")
    print(f"Storage: {stats.get('chroma_dir')}")


def main():
    parser = argparse.ArgumentParser(description="Index PAF library into ChromaDB")
    parser.add_argument(
        "--reset", action="store_true", help="Reset collection before indexing"
    )
    parser.add_argument("--stats", action="store_true", help="Show collection stats")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        asyncio.run(run_index(reset=args.reset))


if __name__ == "__main__":
    main()
