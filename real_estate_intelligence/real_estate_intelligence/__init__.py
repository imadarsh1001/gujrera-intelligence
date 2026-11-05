"""Real Estate Intelligence Platform for Gujarat (GujRERA).

Evidence-backed due-diligence, knowledge graphs, and hybrid RAG for analytical
buyers, investors, and legal advisors.
"""

import sys
from pathlib import Path

# Ensure workspace root is always discoverable for sibling imports (gujrera_pipeline)
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

__version__ = "0.1.0"
