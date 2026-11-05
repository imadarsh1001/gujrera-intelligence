"""Configuration and path resolution for Real Estate Intelligence."""

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = PACKAGE_ROOT.parent

# Ensure workspace root is in sys.path for cross-package imports
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

# Default source run containing raw JSON snapshots and binary documents
DEFAULT_SOURCE_RUN = WORKSPACE_ROOT / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15"

# Local intelligence working directory for curated SQLite DB and derived indices
DEFAULT_DATA_DIR = PACKAGE_ROOT / "data"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "intelligence.sqlite"
DEFAULT_GRAPH_DB_PATH = DEFAULT_DATA_DIR / "knowledge_graph.sqlite"

# Ensure data directory exists
DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
