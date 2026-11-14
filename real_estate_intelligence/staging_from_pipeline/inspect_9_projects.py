import os
import gzip
import json
import csv
import math

PROJECT_IDS = ['13560', '13705', '16104', '16562', '17255', '17830', '17855', '20523', '24508']

def load_csv_data(csv_path):
    csv_data = {}
    if os.path.exists(csv_path):
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid = row.get('projectRegId')
                if pid in PROJECT_IDS:
                    csv_data[pid] = row
    return csv_data

def inspect_projects():
    csv_data = load_csv_data('raw_data/all_projects_111026.csv')
    print(f"Loaded {len(csv_data)} matching projects from CSV.\n")

    for pid in PROJECT_IDS:
        loc_path = f"gujrera_pipeline/data/runs/nine_projects_2026_10_15/raw/projects/{pid}/locations.json.gz"
        if not os.path.exists(loc_path):
            print(f"File not found: {loc_path}")
            continue
        with gzip.open(loc_path, 'rt', encoding='utf-8') as f:
            loc_data = json.load(f)

        csv_row = csv_data.get(pid, {})
        name_loc = loc_data.get('projectName')
        name_csv = csv_row.get('projectName')
        addr_loc = loc_data.get('address')
        addr_csv = csv_row.get('project_address')
        sub_dist = loc_data.get('subDistrictName')
        dist = loc_data.get('districtName')

        coords = loc_data.get('coordinates', [])
        lats = [float(c['lat']) for c in coords if c.get('lat')]
        lngs = [float(c['lang']) for c in coords if c.get('lang')]

        first_v = (lats[0], lngs[0]) if lats and lngs else (None, None)
        centroid = (sum(lats)/len(lats), sum(lngs)/len(lngs)) if lats and lngs else (None, None)

        print(f"--- Project {pid} ---")
        print(f"Name (loc): {name_loc}")
        print(f"Name (csv): {name_csv}")
        print(f"District: {dist}, Sub-district: {sub_dist}")
        print(f"Address (loc): {addr_loc}")
        print(f"Address (csv): {addr_csv}")
        print(f"Addresses Match?: {addr_loc == addr_csv}")
        print(f"Polygon vertex count: {len(coords)}")
        print(f"First vertex: {first_v}")
        print(f"Centroid: {centroid}")
        print()

if __name__ == '__main__':
    inspect_projects()
