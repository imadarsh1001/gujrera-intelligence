"""
Geocoding Experiment comparing address geocoding against ground-truth GPS coordinates
for 9 sample GujRERA projects.
"""

import os
import gzip
import json
import csv
import math
import time
import re
import urllib.request
import urllib.parse

PROJECT_IDS = ['13560', '13705', '16104', '16562', '17255', '17830', '17855', '20523', '24508']

# Haversine distance formula
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0088  # Earth mean radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    km = R * c
    meters = km * 1000.0
    return km, meters

def load_maptiler_key():
    env_path = '.env'
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('MAPTILER_API_KEY='):
                    return line.split('=', 1)[1].strip()
    return os.environ.get('MAPTILER_API_KEY')

def geocode_nominatim(query):
    """Query OSM Nominatim API with compliant headers and rate limit."""
    time.sleep(1.2)  # Respect OSM Nominatim 1 request per second policy
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1"
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'GujRERA-Research-Diligence/1.0 (gujrera-audit@local)'}
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and len(data) > 0:
                top = data[0]
                return {
                    'success': True,
                    'lat': float(top['lat']),
                    'lon': float(top['lon']),
                    'display_name': top.get('display_name'),
                    'type': top.get('type'),
                    'class': top.get('class')
                }
            return {'success': False, 'error': 'No results'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def geocode_maptiler(query, api_key):
    """Query MapTiler Geocoding API."""
    if not api_key:
        return {'success': False, 'error': 'No API key'}
    time.sleep(0.3)
    url = f"https://api.maptiler.com/geocoding/{urllib.parse.quote(query)}.json?key={api_key}"
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'GujRERA-Research-Diligence/1.0'}
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            features = data.get('features', [])
            if features:
                top = features[0]
                center = top.get('center', [])
                if len(center) >= 2:
                    return {
                        'success': True,
                        'lon': float(center[0]),
                        'lat': float(center[1]),
                        'place_name': top.get('place_name'),
                        'place_type': top.get('place_type')
                    }
            return {'success': False, 'error': 'No results'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def clean_revenue_address(raw_addr, district, sub_district):
    """
    Cleans revenue parcel artifacts (F.P., Survey No., T.P.S., Sub Plot)
    and produces a cleaned locality + district address.
    """
    text = raw_addr
    # Strip quotes
    text = text.replace('"', ' ').replace("'", ' ')
    
    # Remove patterns like "F.P. No. 103,", "Survey No. 855,", "T.P.S. No. 429 (Godhavi-Manipur)"
    # Clean F.P. / Final Plot
    text = re.sub(r'(?i)\b(F\.?P\.?|Final\s*Plot)\s*(?:No\.?)?[\s:-]*\w+/?\w*', ' ', text)
    # Clean Survey No / Block No
    text = re.sub(r'(?i)\b(Survey|Block)\s*(?:No\.?|N0\.?)?[\s:-]*\w+/?\w*', ' ', text)
    # Clean T.P.S. / T.P. / Town Planning Scheme
    text = re.sub(r'(?i)\b(T\.?P\.?S?\.?|Town\s*Planning\s*Scheme)\s*(?:No\.?)?[\s:-]*\w+(\s*\([^)]*\))?', ' ', text)
    # Clean Sub Plot Number
    text = re.sub(r'(?i)\bSub\s*Plot\s*(?:Number|No\.?)?[\s:-]*\w+/?\w*', ' ', text)
    
    # Remove excessive punctuation/whitespace
    text = re.sub(r'[\s,;-]+', ' ', text).strip()
    
    # Add locality context if district/state missing
    parts = [text]
    if sub_district and sub_district.lower() not in text.lower():
        parts.append(sub_district)
    if district and district.lower() not in text.lower():
        parts.append(district)
    parts.extend(['Gujarat', 'India'])
    
    cleaned = ", ".join([p.strip() for p in parts if p.strip()])
    return cleaned

def run_experiment():
    maptiler_key = load_maptiler_key()
    print(f"MapTiler Key found: {bool(maptiler_key)}")

    # Load CSV data
    csv_data = {}
    with open('raw_data/all_projects_111026.csv', mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = row.get('projectRegId')
            if pid in PROJECT_IDS:
                csv_data[pid] = row

    results = []

    # Defined cleaned localities for structured testing based on domain knowledge of projects
    # to test best-case cleaned locality geocoding:
    curated_cleaned = {
        '13560': 'Near Global Mission International School, Godhavi, Sanand, Ahmedabad, Gujarat, India',
        '13705': 'PDPU Road, Koba, Gandhinagar, Gujarat, India',
        '16104': 'Opp. BAPS School, Raysan, Gandhinagar, Gujarat, India',
        '16562': 'Gift City Road, Randesan, Gandhinagar, Gujarat, India',
        '17255': 'Sargasan Cross Roads, Sargasan, Gandhinagar, Gujarat, India',
        '17830': 'Randesan Road, Randesan, Gandhinagar, Gujarat, India',
        '17855': '200 Feet Ring Road, Zundal, Gandhinagar, Gujarat, India',
        '20523': 'Kudasan Por Road, Por, Gandhinagar, Gujarat, India',
        '24508': 'K Raheja Road, Koba, Gandhinagar, Gujarat, India'
    }

    # Also test pure locality/village level fallback (District + Locality):
    locality_only = {
        '13560': 'Godhavi, Sanand, Ahmedabad, Gujarat, India',
        '13705': 'Koba, Gandhinagar, Gujarat, India',
        '16104': 'Raysan, Gandhinagar, Gujarat, India',
        '16562': 'Randesan, Gandhinagar, Gujarat, India',
        '17255': 'Sargasan, Gandhinagar, Gujarat, India',
        '17830': 'Randesan, Gandhinagar, Gujarat, India',
        '17855': 'Zundal, Gandhinagar, Gujarat, India',
        '20523': 'Por, Gandhinagar, Gujarat, India',
        '24508': 'Koba, Gandhinagar, Gujarat, India'
    }

    for pid in PROJECT_IDS:
        loc_file = f'gujrera_pipeline/data/runs/nine_projects_2026_10_15/raw/projects/{pid}/locations.json.gz'
        with gzip.open(loc_file, 'rt', encoding='utf-8') as f:
            loc_data = json.load(f)

        csv_row = csv_data.get(pid, {})
        project_name = loc_data.get('projectName')
        addr_loc = loc_data.get('address') or ''
        addr_csv = csv_row.get('project_address') or ''
        district = loc_data.get('districtName') or ''
        sub_district = loc_data.get('subDistrictName') or ''

        coords = loc_data.get('coordinates', [])
        lats = [float(c['lat']) for c in coords if c.get('lat')]
        lngs = [float(c['lang']) for c in coords if c.get('lang')]

        first_vertex = (lats[0], lngs[0]) if lats and lngs else (None, None)
        centroid = (sum(lats)/len(lats), sum(lngs)/len(lngs)) if lats and lngs else (None, None)
        gt_lat, gt_lon = centroid

        print(f"\n=======================================================")
        print(f"Processing Project {pid}: {project_name}")
        print(f"Ground Truth Centroid: ({gt_lat:.6f}, {gt_lon:.6f})")
        print(f"Raw Address (locations.json.gz): {addr_loc}")
        print(f"Raw Address (CSV): {addr_csv}")

        # Formulate query variations
        # 1. Raw location address
        q_raw_loc = f"{addr_loc}, {district}, Gujarat, India" if district and district.lower() not in addr_loc.lower() else f"{addr_loc}, Gujarat, India"
        # 2. Raw CSV address
        q_raw_csv = f"{addr_csv}, Gujarat, India"
        # 3. Regex cleaned address
        q_cleaned_regex = clean_revenue_address(addr_csv if addr_csv else addr_loc, district, sub_district)
        # 4. Curated landmark/locality
        q_curated = curated_cleaned.get(pid, q_cleaned_regex)
        # 5. Pure locality/village level
        q_locality = locality_only.get(pid, f"{district}, Gujarat, India")

        print(f"Query 1 (Raw Loc): {q_raw_loc}")
        print(f"Query 2 (Raw CSV): {q_raw_csv}")
        print(f"Query 3 (Cleaned Regex): {q_cleaned_regex}")
        print(f"Query 4 (Curated Landmark/Road): {q_curated}")
        print(f"Query 5 (Locality/Village): {q_locality}")

        project_res = {
            'projectId': pid,
            'projectName': project_name,
            'address_loc': addr_loc,
            'address_csv': addr_csv,
            'district': district,
            'subDistrict': sub_district,
            'ground_truth': {
                'lat': gt_lat,
                'lon': gt_lon,
                'first_vertex_lat': first_vertex[0],
                'first_vertex_lon': first_vertex[1],
                'polygon_vertices': len(coords)
            },
            'tests': {}
        }

        # Test A: Raw CSV with Nominatim
        print(" -> Geocoding Raw CSV with Nominatim...")
        res_nom_raw = geocode_nominatim(q_raw_csv)
        project_res['tests']['nominatim_raw_csv'] = evaluate_geocode(res_nom_raw, gt_lat, gt_lon, q_raw_csv)

        # Test B: Raw CSV with MapTiler
        print(" -> Geocoding Raw CSV with MapTiler...")
        res_mt_raw = geocode_maptiler(q_raw_csv, maptiler_key)
        project_res['tests']['maptiler_raw_csv'] = evaluate_geocode(res_mt_raw, gt_lat, gt_lon, q_raw_csv)

        # Test C: Cleaned Regex with Nominatim
        print(" -> Geocoding Cleaned Regex with Nominatim...")
        res_nom_regex = geocode_nominatim(q_cleaned_regex)
        project_res['tests']['nominatim_cleaned_regex'] = evaluate_geocode(res_nom_regex, gt_lat, gt_lon, q_cleaned_regex)

        # Test D: Cleaned Regex with MapTiler
        print(" -> Geocoding Cleaned Regex with MapTiler...")
        res_mt_regex = geocode_maptiler(q_cleaned_regex, maptiler_key)
        project_res['tests']['maptiler_cleaned_regex'] = evaluate_geocode(res_mt_regex, gt_lat, gt_lon, q_cleaned_regex)

        # Test E: Curated Landmark/Road with Nominatim
        print(" -> Geocoding Curated with Nominatim...")
        res_nom_curated = geocode_nominatim(q_curated)
        project_res['tests']['nominatim_curated'] = evaluate_geocode(res_nom_curated, gt_lat, gt_lon, q_curated)

        # Test F: Curated Landmark/Road with MapTiler
        print(" -> Geocoding Curated with MapTiler...")
        res_mt_curated = geocode_maptiler(q_curated, maptiler_key)
        project_res['tests']['maptiler_curated'] = evaluate_geocode(res_mt_curated, gt_lat, gt_lon, q_curated)

        # Test G: Village / Locality fallback with Nominatim
        print(" -> Geocoding Locality with Nominatim...")
        res_nom_loc = geocode_nominatim(q_locality)
        project_res['tests']['nominatim_locality'] = evaluate_geocode(res_nom_loc, gt_lat, gt_lon, q_locality)

        # Test H: Village / Locality fallback with MapTiler
        print(" -> Geocoding Locality with MapTiler...")
        res_mt_loc = geocode_maptiler(q_locality, maptiler_key)
        project_res['tests']['maptiler_locality'] = evaluate_geocode(res_mt_loc, gt_lat, gt_lon, q_locality)

        results.append(project_res)

    output_path = 'gujrera_pipeline/experiments/geocoding_results.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\nAll 9 projects processed. Results saved to {output_path}")

def evaluate_geocode(res, gt_lat, gt_lon, query):
    eval_data = {'query': query, 'success': res.get('success', False)}
    if not res.get('success'):
        eval_data['error'] = res.get('error')
        eval_data['distance_km'] = None
        eval_data['distance_m'] = None
        eval_data['match_quality'] = 'FAILED'
        return eval_data

    lat = res['lat']
    lon = res['lon']
    km, meters = haversine(gt_lat, gt_lon, lat, lon)
    eval_data['lat'] = lat
    eval_data['lon'] = lon
    eval_data['distance_km'] = round(km, 3)
    eval_data['distance_m'] = round(meters, 1)
    eval_data['matched_name'] = res.get('display_name') or res.get('place_name')

    # Classify match quality based on real-estate search criteria
    if km < 0.1:  # < 100 meters: Parcel/Building level
        quality = 'EXCELLENT_PARCEL'
    elif km < 0.5:  # 100 - 500 meters: Street/Immediate Neighborhood
        quality = 'GOOD_NEIGHBORHOOD'
    elif km < 2.0:  # 500m - 2 km: Locality/Ward level
        quality = 'SUB_DISTRICT_LOCALITY'
    elif km < 10.0:  # 2 - 10 km: City/District sector level
        quality = 'DISTANT_SECTOR'
    else:  # > 10 km: Completely wrong area / centroid
        quality = 'GROSS_MISMATCH'

    eval_data['match_quality'] = quality
    return eval_data

if __name__ == '__main__':
    run_experiment()
