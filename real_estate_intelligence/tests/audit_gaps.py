import os
import glob
import gzip
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RUN_DIR = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15"
RAW_PROJECTS_DIR = RUN_DIR / "raw" / "projects"

def main():
    print(f"=== SUMMARY OF ALL ENDPOINTS IN THE DATASET ===")
    project_folders = [p for p in RAW_PROJECTS_DIR.iterdir() if p.is_dir()]
    print(f"Total project folders found: {len(project_folders)}")

    endpoint_files = {}

    for pf in project_folders:
        for f in pf.glob("*.json.gz"):
            ep_name = f.name.replace(".json.gz", "")
            endpoint_files[ep_name] = endpoint_files.get(ep_name, 0) + 1

    print(f"\nUnique endpoints found across all projects: {len(endpoint_files)}")
    for ep, count in sorted(endpoint_files.items()):
        print(f" - {ep:<30} (present in {count}/{len(project_folders)} projects)")

    # Also inspect any other subfolders inside projects (like quarters, forms, etc.)
    subfolder_types = set()
    for pf in project_folders:
        for d in pf.iterdir():
            if d.is_dir():
                subfolder_types.add(d.name)
    print(f"\nSubfolders inside project directories: {subfolder_types}")

    for sub in sorted(subfolder_types):
        sample_files = list(RAW_PROJECTS_DIR.glob(f"*/{sub}/*"))
        print(f" - {sub}: contains e.g. {len(sample_files)} items across projects")
        if sample_files:
            print(f"    sample items: {[s.name for s in sample_files[:5]]}")

if __name__ == "__main__":
    main()
