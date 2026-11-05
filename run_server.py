"""Launch the GujRERA Real Estate Intelligence Interactive Web Terminal."""

import sys
from pathlib import Path

# Ensure real_estate_intelligence package is on sys.path
pkg_root = Path(__file__).resolve().parent / "real_estate_intelligence"
sys.path.insert(0, str(pkg_root))

from real_estate_intelligence.cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv = ["cli.py", "serve", "--port", "8765"]
    main()
