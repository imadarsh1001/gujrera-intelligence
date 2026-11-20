"""Launch the GujRERA Real Estate Intelligence Interactive Web Terminal."""

import argparse
import sys
from pathlib import Path

# Ensure workspace root and real_estate_intelligence package are on sys.path
workspace_root = Path(__file__).resolve().parent
pkg_root = workspace_root / "real_estate_intelligence"
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch GujRERA FastAPI server")
    parser.add_argument("--port", type=int, default=8765, help="Web server port (default: 8765)")
    parser.add_argument("--db", default=None, help="Deprecated database path option (no longer applies)")
    args, _ = parser.parse_known_args()

    if args.db:
        print(f"[NOTE] The --db option ({args.db}) no longer applies; FastAPI server uses DEFAULT_DB_PATH or configured environment database.")

    import uvicorn
    print(f"Starting GujRERA FastAPI server on http://127.0.0.1:{args.port}...")
    uvicorn.run("api.index:app", host="127.0.0.1", port=args.port, reload=False)
