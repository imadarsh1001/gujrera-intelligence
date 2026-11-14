# Staging from `gujrera_pipeline` (Producer Handover)

This directory serves as the **isolated staging area** for candidate consumer and intelligence modules migrated out of `gujrera_pipeline`.

Following architectural decision record **ADR-0004**, `gujrera_pipeline` is strictly the private **Producer Ingestion Tier** (crawling, data lake partitioning, raw archive persistence). Downstream knowledge graph derivation, relationship network analysis, and analytical coverage audits belong in this repository (**`real_estate_intelligence`**).

---

## 1. Staged Assets & Candidate Destinations

| Staged File | Description & Capability | Candidate Destination in `real_estate_intelligence` |
| :--- | :--- | :--- |
| **`graph_pilot.py`** | Builds source-linked SQLite relationship graphs (`project`, `promoter`, `filing`, `block`, `document_content` nodes). | `real_estate_intelligence/graph/` |
| **`party_graph.py`** | First-hop professional network builder linking promoters, architects, engineers, and CAs with cryptographic provenance on every edge. | `real_estate_intelligence/graph/` |
| **`coverage_audit.py`** | Audits party and professional role coverage against project indexes, outputting allowlisted gap reports and JSON matrices. | `real_estate_intelligence/analytics/` |
| **`GEOCODING_EXPERIMENT_REPORT.md`** | Definitive empirical benchmark proving why OpenStreetMap/MapTiler geocoding fails on Indian revenue parcels (`Survey No.`, `F.P. No.`) compared to GujRERA GPS polygons. | `docs/` or `research/` |
| **`geocoding_experiment.py`** | Benchmark script testing Nominatim and MapTiler geocoding accuracy against ground-truth portal GPS coordinates. | `tests/` or `scripts/` |
| **`analyze_results.py`** | Statistical analysis script for the geocoding benchmark. | `scripts/` |
| **`inspect_9_projects.py`** | Utility inspecting raw project locations from the reference dataset. | `scripts/` |
| **`EGM.md`** | The engineering contract that originally governed these experiment modules in `gujrera_pipeline`. | Staging reference |

---

## 2. Integration Guidance for This Workspace

When integrating these files into `real_estate_intelligence`:
1. **Import Seam**: Replace references to `gujrera_pipeline.core.storage` or `gujrera_pipeline.legacy_collector.*` with the typed `RunReader` interface (`from gujrera_pipeline import DiskRunReader`) or native `real_estate_intelligence.db` models.
2. **Database Integration**: Connect graph builder logic directly to `real_estate_intelligence.db` and the intelligence platform's schema.
3. **Testing**: Add corresponding unit tests under `real_estate_intelligence/tests/` to verify graph and analytics queries.
