"""Real Estate Intelligence Platform for Gujarat (GujRERA).

Evidence-backed due-diligence, knowledge graphs, and hybrid RAG for analytical
buyers, investors, and legal advisors.
"""

import sys
from pathlib import Path

# Ensure workspace root and sibling gujrera_pipeline are discoverable
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

# Sibling pipeline repo path resolution (parent directory contains package gujrera_pipeline)
PARENT_DIR = WORKSPACE_ROOT.parent
if (PARENT_DIR / "gujrera_pipeline").exists() and str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

__version__ = "0.1.0"
