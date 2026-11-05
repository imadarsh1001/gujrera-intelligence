"""Hybrid document search interface with relevance filtering."""

from ..db.fts import DocumentSearchEngine, sanitize_fts_query, search_documents

__all__ = ["DocumentSearchEngine", "sanitize_fts_query", "search_documents"]
