"""Configuration and path resolution for Real Estate Intelligence."""

import os
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = PACKAGE_ROOT.parent

# Ensure workspace root is in sys.path for cross-package imports
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

# Sibling pipeline repo path resolution
PARENT_DIR = WORKSPACE_ROOT.parent
if (PARENT_DIR / "gujrera_pipeline").exists() and str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))


def _load_env_file() -> None:
    """Load KEY=VALUE pairs from the workspace-root .env into os.environ.

    Never overrides variables that are already set; .env is gitignored and is the
    documented place for secrets such as MAPTILER_API_KEY.
    """
    for candidate in (WORKSPACE_ROOT / ".env", Path.cwd() / ".env"):
        if candidate.is_file():
            try:
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
            except OSError:
                pass
            break


_load_env_file()

# Default source run containing raw JSON snapshots and binary documents
# Resolves to sibling gujrera_pipeline repo if present, fallback to nested folder
_SIBLING_SOURCE_RUN = WORKSPACE_ROOT.parent / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15"
_NESTED_SOURCE_RUN = WORKSPACE_ROOT / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15"
DEFAULT_SOURCE_RUN = _SIBLING_SOURCE_RUN if _SIBLING_SOURCE_RUN.exists() else _NESTED_SOURCE_RUN

# Local intelligence working directory for curated SQLite DB and derived indices
DEFAULT_DATA_DIR = PACKAGE_ROOT / "data"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "intelligence.sqlite"
DEFAULT_GRAPH_DB_PATH = DEFAULT_DATA_DIR / "knowledge_graph.sqlite"

# Ensure data directory exists
DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
