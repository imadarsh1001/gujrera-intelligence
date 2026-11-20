"""Package shim for real_estate_intelligence root directory."""
import sys
from pathlib import Path

_inner_pkg = Path(__file__).resolve().parent / "real_estate_intelligence"
if _inner_pkg.exists() and str(_inner_pkg) not in __path__:
    __path__.insert(0, str(_inner_pkg))

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
