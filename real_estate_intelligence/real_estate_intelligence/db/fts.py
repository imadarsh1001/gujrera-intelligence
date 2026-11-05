"""Full-Text Search (FTS5) manager for extracted document content."""

import sqlite3
from typing import Any, Dict, List


def init_fts(con: sqlite3.Connection) -> None:
    """Initialize SQLite FTS5 virtual table for document pages/chunks."""
    con.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(
            doc_uid_hash UNINDEXED,
            project_id UNINDEXED,
            doc_type UNINDEXED,
            file_name UNINDEXED,
            page_number UNINDEXED,
            content,
            tokenize = 'porter unicode61'
        );
    """)
    con.commit()


def index_page_text(
    con: sqlite3.Connection,
    doc_uid_hash: str,
    project_id: int,
    doc_type: str,
    file_name: str,
    page_number: int,
    content: str,
) -> None:
    """Index an extracted text page into FTS5."""
    if not content or not content.strip():
        return
    con.execute(
        """
        INSERT INTO document_fts (doc_uid_hash, project_id, doc_type, file_name, page_number, content)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (doc_uid_hash, project_id, doc_type, file_name, page_number, content.strip()),
    )


def sanitize_fts_query(query: str) -> str:
    """Sanitize user query for SQLite FTS5 MATCH syntax."""
    safe_query = query.replace('"', '""')
    if " " in safe_query and not safe_query.startswith('"'):
        # Convert space-separated words to AND search
        terms = [f'"{t.strip()}"' for t in safe_query.split() if t.strip()]
        return " ".join(terms) if terms else '""'
    return f'"{safe_query}"'


def _execute_fts_search(
    con: sqlite3.Connection,
    match_expr: str,
    project_id: int | None = None,
    doc_type: str | None = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    sql = """
        SELECT 
            doc_uid_hash,
            project_id,
            doc_type,
            file_name,
            page_number,
            snippet(document_fts, 5, '<b>', '</b>', '...', 25) AS snippet,
            bm25(document_fts) AS rank
        FROM document_fts
        WHERE document_fts MATCH ?
    """
    params: List[Any] = [match_expr]
    if project_id is not None:
        sql += " AND project_id = ?"
        params.append(project_id)
    if doc_type is not None:
        sql += " AND doc_type = ?"
        params.append(doc_type)

    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    cur = con.execute(sql, params)
    results = []
    for row in cur.fetchall():
        results.append({
            "doc_uid_hash": row["doc_uid_hash"],
            "project_id": row["project_id"],
            "doc_type": row["doc_type"],
            "file_name": row["file_name"],
            "page_number": row["page_number"],
            "snippet": row["snippet"],
            "rank": round(float(row["rank"]), 4),
        })
    return results


def search_documents(
    con: sqlite3.Connection,
    query: str,
    project_id: int | None = None,
    doc_type: str | None = None,
    limit: int = 10,
    auto_sanitize: bool = True,
) -> List[Dict[str, Any]]:
    """Hybrid full-text search with BM25 ranking, snippets, query sanitization, and fallback."""
    if not query or not query.strip():
        return []

    if auto_sanitize:
        safe_query = sanitize_fts_query(query)
        try:
            return _execute_fts_search(con, safe_query, project_id, doc_type, limit)
        except sqlite3.OperationalError:
            # Fallback to simple sanitized terms if syntax error occurs
            fallback_query = query.replace("*", "").replace("-", " ").strip()
            if not fallback_query:
                return []
            try:
                return _execute_fts_search(con, fallback_query, project_id, doc_type, limit)
            except sqlite3.OperationalError:
                return []
    else:
        return _execute_fts_search(con, query, project_id, doc_type, limit)


class DocumentSearchEngine:
    """High-level search interface over indexed documents."""

    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def search(
        self,
        query: str,
        project_id: int | None = None,
        doc_type: str | None = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search across all indexed PDF documents with relevance ranking."""
        return search_documents(
            con=self.con,
            query=query,
            project_id=project_id,
            doc_type=doc_type,
            limit=limit,
            auto_sanitize=True,
        )
