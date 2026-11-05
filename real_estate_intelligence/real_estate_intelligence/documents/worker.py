"""Decoupled asynchronous worker for heavy PDF processing and FTS indexing.

Operates over the document_jobs SQLite queue to guarantee that heavy binary extraction
never blocks the primary tabular ingestion pipeline or web interfaces.
"""

import sqlite3
from pathlib import Path
from typing import Dict, Optional, Union

from ..config import DEFAULT_DB_PATH
from ..db.database import get_connection, init_schema
from ..db.fts import index_page_text
from .parser import extract_pdf_pages


class DocumentWorker:
    """Processes queued document jobs asynchronously and updates FTS indexes."""

    def __init__(
        self,
        con_or_path: Optional[Union[sqlite3.Connection, Path, str]] = None,
        base_runs_dir: Optional[Path] = None,
        prune_binaries: bool = False,
    ):
        if isinstance(con_or_path, sqlite3.Connection):
            self.con = con_or_path
            self._owns_con = False
        elif isinstance(con_or_path, (Path, str)):
            self.con = get_connection(Path(con_or_path))
            self._owns_con = True
        else:
            self.con = get_connection(DEFAULT_DB_PATH)
            self._owns_con = True

        init_schema(self.con)

        self.base_runs_dir = Path(base_runs_dir) if base_runs_dir else Path.cwd()
        self.prune_binaries = prune_binaries

    def process_next_job(self) -> Optional[Dict[str, Union[int, str, bool]]]:
        """Fetch and execute the next pending document job in the queue."""
        cur = self.con.cursor()
        job = cur.execute(
            """
            SELECT id, run_id, project_id, uid_hash, doc_type, file_path, attempts, max_attempts
            FROM document_jobs
            WHERE status = 'PENDING' AND attempts < max_attempts
            ORDER BY id ASC LIMIT 1
            """
        ).fetchone()

        if not job:
            return None

        job_id = job["id"]
        pid = job["project_id"]
        uid_hash = job["uid_hash"]
        doc_type = job["doc_type"]
        rel_path = job["file_path"]
        attempts = job["attempts"] + 1

        # Mark as PROCESSING
        self.con.execute(
            """
            UPDATE document_jobs
            SET status = 'PROCESSING', attempts = ?, updated_at_utc = datetime('now')
            WHERE id = ?
            """,
            (attempts, job_id),
        )
        self.con.commit()

        # Locate file
        target_path = None
        if rel_path:
            p = Path(rel_path)
            if p.is_absolute() and p.exists():
                target_path = p
            elif (self.base_runs_dir / p).exists():
                target_path = self.base_runs_dir / p

        if not target_path or not target_path.exists():
            # Record failure
            err = f"File not found on disk: {rel_path}"
            new_status = "FAILED" if attempts >= job["max_attempts"] else "PENDING"
            self.con.execute(
                """
                UPDATE document_jobs
                SET status = ?, error_message = ?, updated_at_utc = datetime('now')
                WHERE id = ?
                """,
                (new_status, err, job_id),
            )
            self.con.commit()
            return {"job_id": job_id, "status": new_status, "error": err}

        # Process PDF
        try:
            pages = extract_pdf_pages(target_path)
            for page_num, page_text in pages:
                index_page_text(
                    con=self.con,
                    doc_uid_hash=uid_hash,
                    project_id=pid,
                    doc_type=doc_type,
                    file_name=target_path.name,
                    page_number=page_num,
                    content=page_text,
                )

            # Optional post-extraction binary pruning
            if self.prune_binaries and target_path.exists():
                try:
                    target_path.unlink()
                except OSError:
                    pass

            self.con.execute(
                """
                UPDATE document_jobs
                SET status = 'COMPLETED', error_message = NULL,
                    updated_at_utc = datetime('now'), completed_at_utc = datetime('now')
                WHERE id = ?
                """,
                (job_id,),
            )
            self.con.commit()
            return {"job_id": job_id, "status": "COMPLETED", "pages_indexed": len(pages)}

        except Exception as e:
            err = str(e)
            new_status = "FAILED" if attempts >= job["max_attempts"] else "PENDING"
            self.con.execute(
                """
                UPDATE document_jobs
                SET status = ?, error_message = ?, updated_at_utc = datetime('now')
                WHERE id = ?
                """,
                (new_status, err, job_id),
            )
            self.con.commit()
            return {"job_id": job_id, "status": new_status, "error": err}

    def process_batch(self, max_jobs: int = 10) -> Dict[str, int]:
        """Process up to max_jobs from the queue and return summary metrics."""
        summary = {"processed": 0, "completed": 0, "failed": 0}
        for _ in range(max_jobs):
            res = self.process_next_job()
            if not res:
                break
            summary["processed"] += 1
            if res.get("status") == "COMPLETED":
                summary["completed"] += 1
            else:
                summary["failed"] += 1
        return summary

    def get_queue_status(self) -> Dict[str, int]:
        """Return counts of jobs grouped by status."""
        cur = self.con.cursor()
        rows = cur.execute("SELECT status, COUNT(*) as count FROM document_jobs GROUP BY status").fetchall()
        return {r["status"]: r["count"] for r in rows}

    def close(self) -> None:
        if self._owns_con and self.con:
            self.con.close()
