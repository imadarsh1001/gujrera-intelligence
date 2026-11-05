"""Deep read-side query interface for completed GujRERA collection runs."""

import abc
import gzip
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple


@dataclass(frozen=True)
class DocumentRef:
    """Reference to a downloaded or cataloged document asset."""
    project_id: int
    request_key: str
    json_path: str
    uid_hash: str
    file_path: Optional[str] = None
    raw_bytes: Optional[int] = None
    sha256: Optional[str] = None
    status: str = "ok"


class ProjectSnapshot:
    """Immutable, lazy observation of verified project filings within a single run."""

    def __init__(
        self,
        project_id: int,
        name: str,
        registration_number: str,
        promoter_id: int,
        promoter_name: str,
        status: str = "complete",
        last_error: Optional[str] = None,
        updated_at_utc: Optional[str] = None,
        fetcher: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
        static_filings: Optional[Dict[str, Any]] = None,
    ):
        self.project_id = project_id
        self.name = name
        self.registration_number = registration_number
        self.promoter_id = promoter_id
        self.promoter_name = promoter_name
        self.status = status
        self.last_error = last_error
        self.updated_at_utc = updated_at_utc
        self._fetcher = fetcher or (lambda _: None)
        self._cache: Dict[str, Any] = static_filings.copy() if static_filings else {}
        self._missing_endpoints: List[str] = []

    def _get_envelope(self, endpoint_key: str) -> Any:
        if endpoint_key in self._cache:
            return self._cache[endpoint_key]
        raw = self._fetcher(endpoint_key)
        if raw is None:
            self._missing_endpoints.append(endpoint_key)
            self._cache[endpoint_key] = {}
            return {}
        # Normalize portal root envelopes: {"data": {...}, "status": 200}
        data = raw.get("data") if isinstance(raw, dict) and "data" in raw else raw
        self._cache[endpoint_key] = data if data is not None else {}
        return self._cache[endpoint_key]

    @property
    def missing_endpoints(self) -> List[str]:
        return list(self._missing_endpoints)

    @property
    def project_details(self) -> Dict[str, Any]:
        res = self._get_envelope("project_details")
        return res if isinstance(res, dict) else {}

    @property
    def form_three(self) -> Dict[str, Any]:
        res = self._get_envelope("latest_form_three")
        if not res:
            res = self._get_envelope("form_three")
        return res if isinstance(res, dict) else {}

    @property
    def index_form_three(self) -> Dict[str, Any]:
        res = self._get_envelope("index_form_three")
        return res if isinstance(res, dict) else {}

    @property
    def form_one(self) -> Dict[str, Any]:
        res = self._get_envelope("latest_form_one")
        if not res:
            res = self._get_envelope("form_one")
        return res if isinstance(res, dict) else {}

    @property
    def form_two(self) -> Dict[str, Any]:
        res = self._get_envelope("latest_form_two")
        if not res:
            res = self._get_envelope("index_form_two")
        return res if isinstance(res, dict) else {}

    @property
    def locations(self) -> Dict[str, Any]:
        res = self._get_envelope("locations")
        return res if isinstance(res, dict) else {}

    @property
    def form_four(self) -> Dict[str, Any]:
        res = self._get_envelope("form_four")
        return res if isinstance(res, dict) else {}

    @property
    def noc_bu(self) -> Dict[str, Any]:
        res = self._get_envelope("latest_noc_bu")
        if not res:
            res = self._get_envelope("noc_bu")
        return res if isinstance(res, dict) else {}

    @property
    def progress_reports(self) -> Dict[str, Any]:
        res = self._get_envelope("progress_reports")
        return res if isinstance(res, dict) else {}

    @property
    def applications(self) -> List[Dict[str, Any]]:
        res = self._get_envelope("all_applications")
        if isinstance(res, list):
            return res
        if isinstance(res, dict):
            inner = res.get("data") or res.get("applications") or []
            return inner if isinstance(inner, list) else []
        return []

    @property
    def quarter_index(self) -> List[Dict[str, Any]]:
        res = self._get_envelope("quarter_index")
        if isinstance(res, list):
            return res
        if isinstance(res, dict):
            inner = res.get("data") or res.get("quarters") or []
            return inner if isinstance(inner, list) else []
        return []

    @property
    def promoter(self) -> Dict[str, Any]:
        res = self._get_envelope("promoter")
        return res if isinstance(res, dict) else {}

    @property
    def previous_projects(self) -> Dict[str, Any]:
        res = self._get_envelope("previous_projects")
        return res if isinstance(res, dict) else {}

    @property
    def banks(self) -> Any:
        return self._get_envelope("banks")

    @property
    def collection_accounts(self) -> Any:
        return self._get_envelope("collection_account")

    @property
    def qpr_progress(self) -> List[Dict[str, Any]]:
        res = self._get_envelope("qpr_progress")
        if isinstance(res, list):
            return res
        if isinstance(res, dict):
            inner = res.get("data") or []
            return inner if isinstance(inner, list) else []
        return []

    @property
    def annual_compliance(self) -> List[Dict[str, Any]]:
        res = self._get_envelope("annual_compliance")
        if isinstance(res, list):
            return res
        if isinstance(res, dict):
            inner = res.get("data") or []
            return inner if isinstance(inner, list) else []
        return []

    @property
    def unit_transactions(self) -> List[Dict[str, Any]]:
        """Normalized unit-level inventory and realization transactions from Form 3."""
        f3 = self.form_three
        alist = f3.get("formThreeAList") or []
        f3_id = f3.get("formThreeId")
        units = []
        for u in alist:
            if not isinstance(u, dict):
                continue
            ca_sqm = float(u.get("carpetArea") or 0.0)
            cons = float(u.get("unitConsideration") or 0.0)
            ca_sqft = round(ca_sqm * 10.7639, 2) if ca_sqm > 0 else 0.0
            rate_sqft = round(cons / ca_sqft, 2) if ca_sqft > 0 and cons > 0 else None
            rate_sqm = round(cons / ca_sqm, 2) if ca_sqm > 0 and cons > 0 else None
            units.append({
                "project_id": self.project_id,
                "form_three_id": f3_id,
                "block_name": str(u.get("blockName") or "General").strip(),
                "unit_type": str(u.get("typeOfInventoryName") or u.get("usage") or "Residential").strip(),
                "carpet_area_sqm": ca_sqm,
                "carpet_area_sqft": ca_sqft,
                "unit_consideration": cons,
                "rate_per_sqft": rate_sqft,
                "rate_per_sqm": rate_sqm,
                "status": str(u.get("status") or "UNBOOKED").upper(),
                "agreement_date": u.get("dateOfAgrrement") or u.get("createdOn"),
            })
        return units


class RunReader(abc.ABC):
    """Abstract reader interface for querying archived collection runs."""

    @abc.abstractmethod
    def iter_snapshots(self, project_ids: Optional[List[int]] = None) -> Iterator[ProjectSnapshot]:
        """Iterate over project snapshots in the run."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_snapshot(self, project_id: int, require_complete: bool = False) -> ProjectSnapshot:
        """Fetch a single project snapshot by ID."""
        raise NotImplementedError

    @abc.abstractmethod
    def iter_document_refs(self, project_id: Optional[int] = None) -> Iterator[DocumentRef]:
        """Iterate over verified document references."""
        raise NotImplementedError

    @abc.abstractmethod
    def resolve_document_path(self, uid_hash: str) -> Optional[Path]:
        """Resolve the local on-disk path for a document hash."""
        raise NotImplementedError

    @abc.abstractmethod
    def counts(self) -> Dict[str, Any]:
        """Return run summary counts."""
        raise NotImplementedError

    @abc.abstractmethod
    def close(self) -> None:
        """Release underlying connections."""
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class DiskRunReader(RunReader):
    """Production adapter reading from compressed .json.gz files and manifest.sqlite."""

    def __init__(self, run_dir_or_root: Path, run_id: Optional[str] = None):
        path = run_dir_or_root.resolve()
        if run_id:
            self.root = path / "runs" / run_id
            self.run_id = run_id
        elif (path / "manifest.sqlite").exists():
            self.root = path
            self.run_id = path.name
        elif (path / "runs").exists():
            runs = [d for d in (path / "runs").iterdir() if d.is_dir() and (d / "manifest.sqlite").exists()]
            if not runs:
                raise FileNotFoundError(f"No valid run directories found in {path / 'runs'}")
            runs.sort(key=lambda d: d.name, reverse=True)
            self.root = runs[0]
            self.run_id = self.root.name
        else:
            self.root = path
            self.run_id = path.name

        self.db_path = self.root / "manifest.sqlite"
        if not self.db_path.exists():
            raise FileNotFoundError(f"manifest.sqlite not found at: {self.db_path}")

        self._con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=30.0)
        self._con.row_factory = sqlite3.Row

    def _read_compressed_json(self, rel_path: Path) -> Optional[Dict[str, Any]]:
        full_path = self.root / rel_path
        if not full_path.exists():
            return None
        try:
            raw = gzip.decompress(full_path.read_bytes())
            return json.loads(raw.decode("utf-8-sig"))
        except Exception:
            return None

    def _fetch_endpoint_for_project(self, project_id: int, promoter_id: int, endpoint_name: str) -> Optional[Dict[str, Any]]:
        if endpoint_name == "promoter":
            return self._read_compressed_json(Path("raw") / "promoters" / f"{promoter_id}.json.gz")
        
        # Check standard project relative path
        pdir = Path("raw") / "projects" / str(project_id)
        direct_path = pdir / f"{endpoint_name}.json.gz"
        data = self._read_compressed_json(direct_path)
        if data is not None:
            return data

        # Manifest lookup fallback for non-standard or versioned request keys
        row = self._con.execute(
            "SELECT raw_path FROM requests WHERE project_id = ? AND endpoint = ? AND status = 'ok' ORDER BY fetched_at_utc DESC LIMIT 1",
            (project_id, endpoint_name),
        ).fetchone()
        if row and row["raw_path"]:
            return self._read_compressed_json(Path(row["raw_path"]))
        return None

    def iter_snapshots(self, project_ids: Optional[List[int]] = None) -> Iterator[ProjectSnapshot]:
        sql = "SELECT * FROM projects"
        params: List[Any] = []
        if project_ids:
            placeholders = ",".join("?" for _ in project_ids)
            sql += f" WHERE project_id IN ({placeholders})"
            params.extend(project_ids)
        sql += " ORDER BY project_id"

        rows = self._con.execute(sql, params).fetchall()
        for r in rows:
            yield self._build_snapshot(r)

    def get_snapshot(self, project_id: int, require_complete: bool = False) -> ProjectSnapshot:
        row = self._con.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        if not row:
            raise KeyError(f"Project ID {project_id} not found in run {self.run_id}")
        if require_complete and row["status"] != "complete":
            raise ValueError(f"Project {project_id} status is '{row['status']}', expected 'complete'")
        return self._build_snapshot(row)

    def _build_snapshot(self, row: sqlite3.Row) -> ProjectSnapshot:
        pid = row["project_id"]
        promoter_id = row["promoter_id"] or 0
        return ProjectSnapshot(
            project_id=pid,
            name=row["name"],
            registration_number=row["registration_number"],
            promoter_id=promoter_id,
            promoter_name=row["promoter_name"] or "",
            status=row["status"],
            last_error=row["last_error"],
            updated_at_utc=row["updated_at_utc"],
            fetcher=lambda ep: self._fetch_endpoint_for_project(pid, promoter_id, ep),
        )

    def iter_document_refs(self, project_id: Optional[int] = None) -> Iterator[DocumentRef]:
        sql = """
            SELECT r.project_id, r.request_key, r.json_path, d.uid_hash, d.file_path, d.raw_bytes, d.sha256, d.status
            FROM document_refs r
            JOIN documents d ON d.uid_hash = r.uid_hash
            WHERE d.file_path IS NOT NULL AND d.status IN ('ok', 'unrecognized')
        """
        params: List[Any] = []
        if project_id is not None:
            sql += " AND r.project_id = ?"
            params.append(project_id)
        sql += " ORDER BY r.project_id, d.uid_hash"

        for row in self._con.execute(sql, params).fetchall():
            yield DocumentRef(
                project_id=row["project_id"],
                request_key=row["request_key"],
                json_path=row["json_path"],
                uid_hash=row["uid_hash"],
                file_path=row["file_path"],
                raw_bytes=row["raw_bytes"],
                sha256=row["sha256"],
                status=row["status"],
            )

    def resolve_document_path(self, uid_hash: str) -> Optional[Path]:
        row = self._con.execute("SELECT file_path FROM documents WHERE uid_hash = ?", (uid_hash,)).fetchone()
        if not row or not row["file_path"]:
            return None
        full = self.root / row["file_path"]
        return full if full.exists() else None

    def counts(self) -> Dict[str, Any]:
        return {
            "projects": dict(self._con.execute("SELECT status, COUNT(*) FROM projects GROUP BY status").fetchall()),
            "requests": dict(self._con.execute("SELECT status, COUNT(*) FROM requests GROUP BY status").fetchall()),
            "documents": dict(self._con.execute("SELECT status, COUNT(*) FROM documents GROUP BY status").fetchall()),
        }

    def close(self) -> None:
        if self._con:
            self._con.close()


class FakeRunReader(RunReader):
    """In-memory test adapter for testing downstream consumers without disk I/O."""

    def __init__(
        self,
        snapshots: Optional[List[ProjectSnapshot]] = None,
        document_refs: Optional[List[DocumentRef]] = None,
        document_files: Optional[Dict[str, Path]] = None,
        run_id: str = "fake_run",
    ):
        self.run_id = run_id
        self._snapshots = {s.project_id: s for s in (snapshots or [])}
        self._document_refs = list(document_refs or [])
        self._document_files = dict(document_files or {})

    def iter_snapshots(self, project_ids: Optional[List[int]] = None) -> Iterator[ProjectSnapshot]:
        for pid, s in sorted(self._snapshots.items()):
            if not project_ids or pid in project_ids:
                yield s

    def get_snapshot(self, project_id: int, require_complete: bool = False) -> ProjectSnapshot:
        if project_id not in self._snapshots:
            raise KeyError(f"Project ID {project_id} not found in fake store")
        snap = self._snapshots[project_id]
        if require_complete and snap.status != "complete":
            raise ValueError(f"Project {project_id} status is '{snap.status}', expected 'complete'")
        return snap

    def iter_document_refs(self, project_id: Optional[int] = None) -> Iterator[DocumentRef]:
        for ref in self._document_refs:
            if project_id is None or ref.project_id == project_id:
                yield ref

    def resolve_document_path(self, uid_hash: str) -> Optional[Path]:
        return self._document_files.get(uid_hash)

    def counts(self) -> Dict[str, Any]:
        return {"projects": {"complete": len(self._snapshots)}, "requests": {}, "documents": {}}

    def close(self) -> None:
        pass
