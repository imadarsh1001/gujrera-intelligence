import json
from pathlib import Path
import statistics

BENCHMARK_DIR = Path(__file__).resolve().parent
REPO_ROOT = BENCHMARK_DIR.parents[3]
RESULTS_FILE = BENCHMARK_DIR / "geocoding_results.json"
REPORT_OUTPUT = REPO_ROOT / "docs" / "research" / "GEOCODING_EXPERIMENT_REPORT.md"

def generate_report():
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        results = json.load(f)

    test_keys = [
        ('nominatim_raw_csv', 'OSM Nominatim (Raw Full CSV)'),
        ('maptiler_raw_csv', 'MapTiler (Raw Full CSV)'),
        ('nominatim_cleaned_regex', 'OSM Nominatim (Cleaned Regex)'),
        ('maptiler_cleaned_regex', 'MapTiler (Cleaned Regex)'),
        ('nominatim_curated', 'OSM Nominatim (Curated Road/Landmark)'),
        ('maptiler_curated', 'MapTiler (Curated Road/Landmark)'),
        ('nominatim_locality', 'OSM Nominatim (Locality/Village Only)'),
        ('maptiler_locality', 'MapTiler (Locality/Village Only)')
    ]

    lines = []
    lines.append("# Empirical Evaluation: Address Geocoding vs Ground-Truth GPS Coordinates")
    lines.append("## GujRERA 9-Project Development Dataset\n")
    
    lines.append("### 1. Executive Summary")
    lines.append("We evaluated the feasibility of replacing GujRERA's `/maplocation/public/getProjectLocations/{project_id}` endpoint with automated address geocoding across the 9 frozen sample projects.")
    lines.append("We benchmarked two major geocoding engines: **OpenStreetMap Nominatim** and **MapTiler Geocoding API**, testing raw address strings, automated regex-cleaned addresses (stripping Indian cadastral revenue identifiers like Survey No, FP, TPS), curated landmark/road queries, and village/locality fallbacks.\n")

    lines.append("#### Key Empirical Findings:")
    lines.append("- **Raw Full Address Failure:** OpenStreetMap Nominatim failed **100% (0/9)** on raw full addresses because Indian cadastral parcel numbers (`F.P. No.`, `Survey No.`, `T.P.S. No.`) do not exist in consumer gazetteers. MapTiler returned results for 8/9, but frequently matched completely unrelated locations (e.g. Project 17830 `SURVEY NO:- 229, FINAL PLOT NO 116...` was geocoded to an arbitrary village called *'Plot'* in Kerala, 1,620 km away!).")
    lines.append("- **Best-Case Cleaned / Locality Error:** Even when addresses are aggressively stripped of cadastral identifiers down to the village/sub-district locality (e.g. Raysan, Randesan, Koba, Godhavi), the geocoded coordinates resolve to the **geographic centroid of the village or road junction**, yielding median error distances of **1.22 km (Nominatim)** and **4.24 km (MapTiler)**.")
    lines.append("- **Zero Parcel-Level Accuracy:** Neither engine achieved parcel-level (<100m) or even site-level (<300m) accuracy for any of the 9 projects.")
    lines.append("- **Definitive Conclusion:** **`getProjectLocations` CANNOT be replaced by address geocoding.** The actual ground-truth GPS polygon/coordinates collected by the GujRERA portal must be preserved and used for all map rendering and spatial due diligence.\n")

    lines.append("### 2. Comprehensive Results Table by Project")
    lines.append("Comparing Ground Truth GPS Centroid (from `locations.json.gz`) against geocoded points across configurations:\n")

    for p in results:
        pid = p['projectId']
        name = p['projectName']
        gt_lat = p['ground_truth']['lat']
        gt_lon = p['ground_truth']['lon']
        poly_count = p['ground_truth']['polygon_vertices']
        lines.append(f"#### Project {pid} — {name}")
        lines.append(f"- **District / Sub-District:** {p['district']} / {p['subDistrict']}")
        lines.append(f"- **Ground Truth GPS:** `({gt_lat:.6f}, {gt_lon:.6f})` (Plot polygon with {poly_count} vertices)")
        lines.append(f"- **Raw Address (`locations.json.gz`):** `{p['address_loc']}`")
        lines.append(f"- **Raw Address (`all_projects_111026.csv`):** `{p['address_csv']}`\n")
        
        lines.append("| Geocoding Method | Query String Tested | Status | Lat/Lon | Error Dist (km) | Error Dist (m) | Match Quality | Resolved Feature |")
        lines.append("|---|---|---|---|---|---|---|---|")
        
        for key, label in test_keys:
            t = p['tests'].get(key, {})
            succ = "SUCCESS" if t.get('success') else "FAILED"
            coords = f"`{t.get('lat'):.5f}, {t.get('lon'):.5f}`" if t.get('success') else "—"
            km_str = f"{t.get('distance_km'):.3f}" if t.get('distance_km') is not None else "—"
            m_str = f"{t.get('distance_m'):.1f}" if t.get('distance_m') is not None else "—"
            mq = t.get('match_quality', 'FAILED')
            q_clean = t.get('query', '').replace('|', '/')
            matched = (t.get('matched_name') or t.get('error') or '—').replace('|', '/')
            lines.append(f"| {label} | `{q_clean}` | {succ} | {coords} | {km_str} | {m_str} | {mq} | {matched} |")
        lines.append("\n")

    lines.append("### 3. Aggregate Benchmark Performance")
    lines.append("| Method / Configuration | Success Rate | Median Error (km) | Mean Error (km) | Min Error (km) | Max Error (km) | Practical Usability |")
    lines.append("|---|---|---|---|---|---|---|")

    for key, label in test_keys:
        dists = []
        successes = 0
        for p in results:
            t = p['tests'].get(key, {})
            if t.get('success') and t.get('distance_km') is not None:
                successes += 1
                dists.append(t['distance_km'])
        
        succ_rate = f"{successes}/9 ({successes/9.0*100:.1f}%)"
        if dists:
            med = f"{statistics.median(dists):.3f}"
            mean = f"{statistics.mean(dists):.3f}"
            min_e = f"{min(dists):.3f}"
            max_e = f"{max(dists):.3f}"
            if statistics.median(dists) > 50:
                usability = "Catastrophic Hallucination"
            elif statistics.median(dists) > 3.0:
                usability = "Unusable (District/City centroid)"
            else:
                usability = "Approximate Neighborhood Only (~1-2km)"
        else:
            med, mean, min_e, max_e = "N/A", "N/A", "N/A", "N/A"
            usability = "Total Failure (0% match)"
        lines.append(f"| {label} | {succ_rate} | {med} | {mean} | {min_e} | {max_e} | {usability} |")

    report_content = "\n".join(lines)
    REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(report_content)
    print(f"Report generated at {REPORT_OUTPUT}")

if __name__ == '__main__':
    generate_report()
