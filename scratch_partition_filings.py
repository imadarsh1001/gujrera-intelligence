import math
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import duckdb

def partition_filings():
    filings_dir = Path("gujrera_pipeline/data/filings")
    quarters = [
        ("formthree_2023-12-01_q4.parquet", "2023-12-01", 4),
        ("formthree_2024-10-13_q4.parquet", "2024-10-13", 4),
        ("formthree_2025-03-01_q1.parquet", "2025-03-01", 4),
        ("formthree_2026-10-11_q4.parquet", "2026-10-11", 4),
    ]
    
    for filename, date_folder, num_parts in quarters:
        src_path = filings_dir / filename
        if not src_path.exists():
            print(f"Skipping {filename} (not found)")
            continue
            
        print(f"\nPartitioning {filename} into {num_parts} parts...")
        table = pq.read_table(src_path)
        total_rows = table.num_rows
        part_size = math.ceil(total_rows / num_parts)
        
        target_dir = filings_dir / date_folder
        target_dir.mkdir(parents=True, exist_ok=True)
        
        for i in range(num_parts):
            start = i * part_size
            end = min((i + 1) * part_size, total_rows)
            if start >= total_rows:
                break
            part_table = table.slice(start, end - start)
            part_path = target_dir / f"part_{i+1:02d}.parquet"
            pq.write_table(part_table, part_path, compression='zstd')
            print(f"  Created {part_path.relative_to(filings_dir)}: {part_table.num_rows:,} rows, {part_path.stat().st_size / 1024 / 1024:.2f} MB")
            
        # Verify with duckdb that globbing matches original row count
        glob_str = str((target_dir / "*.parquet").resolve()).replace('\\', '/')
        con = duckdb.connect()
        count = con.execute(f"SELECT COUNT(*) FROM '{glob_str}'").fetchone()[0]
        print(f"  VERIFIED with DuckDB: {count:,} rows match original {total_rows:,} rows!")

if __name__ == "__main__":
    partition_filings()
