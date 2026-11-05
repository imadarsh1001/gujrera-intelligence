import sys
from pathlib import Path
from real_estate_intelligence.config import DEFAULT_SOURCE_RUN, DEFAULT_DB_PATH
from real_estate_intelligence.db.database import get_connection
from real_estate_intelligence.db.loader import ingest_from_run

sys.stdout.reconfigure(encoding="utf-8")

def main():
    print(f"Starting ingestion from: {DEFAULT_SOURCE_RUN}")
    print(f"Target DB: {DEFAULT_DB_PATH}")
    if DEFAULT_DB_PATH.exists():
        print("Removing existing DB to apply upgraded schema...")
        DEFAULT_DB_PATH.unlink()
    stats = ingest_from_run(DEFAULT_SOURCE_RUN, DEFAULT_DB_PATH, index_documents=True)
    
    # Compact database
    con = get_connection(DEFAULT_DB_PATH)
    con.execute("VACUUM")
    con.close()
    
    final_size_mb = DEFAULT_DB_PATH.stat().st_size / (1024 * 1024)
    print(f"\n[SUCCESS] Ingestion and compaction completed! Final DB size: {final_size_mb:.2f} MB")
    for k, v in stats.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
