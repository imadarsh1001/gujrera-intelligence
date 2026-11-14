# Geocoding vs. Ground-Truth GPS Benchmarks

This directory contains the empirical benchmark runner, raw response data, and statistical analysis scripts used to evaluate whether address-based geocoding (OpenStreetMap Nominatim and MapTiler) can substitute for official GujRERA GPS polygon coordinates.

## Assets
- `geocoding_results.json`: Frozen ground-truth execution dataset containing cached responses from Nominatim and MapTiler across the 9 representative pilot projects.
- `analyze_results.py`: Computes statistical distance metrics (Haversine errors in km/m, error distributions) and compiles the formal findings into `docs/research/GEOCODING_EXPERIMENT_REPORT.md`.
- `geocoding_experiment.py`: Benchmark runner querying Nominatim (1 req/sec rate limit) and MapTiler APIs.
- `inspect_9_projects.py`: Diagnostic inspector comparing portal address strings against coordinate vertices.

## Running Statistical Analysis
To regenerate or inspect the empirical distance report:
```powershell
python real_estate_intelligence/scripts/benchmarks/geocoding/analyze_results.py
```

## Definitive Empirical Finding
Nominatim failed 100% on raw cadastral parcel addresses (`Survey No.`, `F.P. No.`), and MapTiler exhibited a median error of 4.24 km (resolving to city centroids or spurious homonyms). For full findings and methodology, see [`docs/research/GEOCODING_EXPERIMENT_REPORT.md`](../../../../docs/research/GEOCODING_EXPERIMENT_REPORT.md).
