# Empirical Evaluation: Address Geocoding vs Ground-Truth GPS Coordinates
## GujRERA 9-Project Development Dataset

### 1. Executive Summary
We evaluated the feasibility of replacing GujRERA's `/maplocation/public/getProjectLocations/{project_id}` endpoint with automated address geocoding across the 9 frozen sample projects.
We benchmarked two major geocoding engines: **OpenStreetMap Nominatim** and **MapTiler Geocoding API**, testing raw address strings, automated regex-cleaned addresses (stripping Indian cadastral revenue identifiers like Survey No, FP, TPS), curated landmark/road queries, and village/locality fallbacks.

#### Key Empirical Findings:
- **Raw Full Address Failure:** OpenStreetMap Nominatim failed **100% (0/9)** on raw full addresses because Indian cadastral parcel numbers (`F.P. No.`, `Survey No.`, `T.P.S. No.`) do not exist in consumer gazetteers. MapTiler returned results for 8/9, but frequently matched completely unrelated locations (e.g. Project 17830 `SURVEY NO:- 229, FINAL PLOT NO 116...` was geocoded to an arbitrary village called *'Plot'* in Kerala, 1,620 km away!).
- **Best-Case Cleaned / Locality Error:** Even when addresses are aggressively stripped of cadastral identifiers down to the village/sub-district locality (e.g. Raysan, Randesan, Koba, Godhavi), the geocoded coordinates resolve to the **geographic centroid of the village or road junction**, yielding median error distances of **1.22 km (Nominatim)** and **4.24 km (MapTiler)**.
- **Zero Parcel-Level Accuracy:** Neither engine achieved parcel-level (<100m) or even site-level (<300m) accuracy for any of the 9 projects.
- **Definitive Conclusion:** **`getProjectLocations` CANNOT be replaced by address geocoding.** The actual ground-truth GPS polygon/coordinates collected by the GujRERA portal must be preserved and used for all map rendering and spatial due diligence.

### 2. Comprehensive Results Table by Project
Comparing Ground Truth GPS Centroid (from `locations.json.gz`) against geocoded points across configurations:

#### Project 13560 — Skydeck Serene
- **District / Sub-District:** Ahmedabad / Sanand
- **Ground Truth GPS:** `(23.020160, 72.426782)` (Plot polygon with 5 vertices)
- **Raw Address (`locations.json.gz`):** `F.P. No. 103,  Survey No. 855, T.P.S. No. 429 (Godhavi-Manipur)Near Global Mission International School, Godhavi`
- **Raw Address (`all_projects_111026.csv`):** `F.P. No. 103,  Survey No. 855, T.P.S. No. 429 (Godhavi-Manipur) Near Global Mission International School, Godhavi`

| Geocoding Method | Query String Tested | Status | Lat/Lon | Error Dist (km) | Error Dist (m) | Match Quality | Resolved Feature |
|---|---|---|---|---|---|---|---|
| OSM Nominatim (Raw Full CSV) | `F.P. No. 103,  Survey No. 855, T.P.S. No. 429 (Godhavi-Manipur) Near Global Mission International School, Godhavi, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Raw Full CSV) | `F.P. No. 103,  Survey No. 855, T.P.S. No. 429 (Godhavi-Manipur) Near Global Mission International School, Godhavi, Gujarat, India` | SUCCESS | `10.77212, 79.76515` | 1568.881 | 1568881.0 | GROSS_MISMATCH | School, Tamil Nadu, India |
| OSM Nominatim (Cleaned Regex) | `Near Global Mission International School Godhavi, Sanand, Ahmedabad, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Cleaned Regex) | `Near Global Mission International School Godhavi, Sanand, Ahmedabad, Gujarat, India` | SUCCESS | `22.99245, 72.38256` | 5.475 | 5475.2 | DISTANT_SECTOR | Sanand, Sanand Taluka, Gujarat, India |
| OSM Nominatim (Curated Road/Landmark) | `Near Global Mission International School, Godhavi, Sanand, Ahmedabad, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Curated Road/Landmark) | `Near Global Mission International School, Godhavi, Sanand, Ahmedabad, Gujarat, India` | SUCCESS | `22.99245, 72.38256` | 5.475 | 5475.2 | DISTANT_SECTOR | Sanand, Sanand Taluka, Gujarat, India |
| OSM Nominatim (Locality/Village Only) | `Godhavi, Sanand, Ahmedabad, Gujarat, India` | SUCCESS | `23.02332, 72.40871` | 1.883 | 1882.6 | SUB_DISTRICT_LOCALITY | Godhavi, Sanand Taluka, Ahmedabad, Gujarat, India |
| MapTiler (Locality/Village Only) | `Godhavi, Sanand, Ahmedabad, Gujarat, India` | SUCCESS | `23.02332, 72.40871` | 1.883 | 1882.7 | SUB_DISTRICT_LOCALITY | Godhavi, Sanand Taluka, Gujarat, India |


#### Project 13705 — THE GATE BY DEV AASHISH
- **District / Sub-District:** Gandhinagar / Gandhinagar
- **Ground Truth GPS:** `(23.154061, 72.656755)` (Plot polygon with 4 vertices)
- **Raw Address (`locations.json.gz`):** `THE GATE BY DEV AASHISH ROYAL STREET`
- **Raw Address (`all_projects_111026.csv`):** `THE GATE BY DEV AASHISH ROYAL STREET PDPU ROAD KOBA`

| Geocoding Method | Query String Tested | Status | Lat/Lon | Error Dist (km) | Error Dist (m) | Match Quality | Resolved Feature |
|---|---|---|---|---|---|---|---|
| OSM Nominatim (Raw Full CSV) | `THE GATE BY DEV AASHISH ROYAL STREET PDPU ROAD KOBA, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Raw Full CSV) | `THE GATE BY DEV AASHISH ROYAL STREET PDPU ROAD KOBA, Gujarat, India` | SUCCESS | `19.29659, 74.67362` | 477.138 | 477137.6 | GROSS_MISMATCH | Dev, Maharashtra, India |
| OSM Nominatim (Cleaned Regex) | `THE GATE BY DEV AASHISH ROYAL STREET PDPU ROAD KOBA, Gandhinagar, Gandhinagar, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Cleaned Regex) | `THE GATE BY DEV AASHISH ROYAL STREET PDPU ROAD KOBA, Gandhinagar, Gandhinagar, Gujarat, India` | SUCCESS | `23.22329, 72.64923` | 7.736 | 7736.0 | DISTANT_SECTOR | Gandhinagar, Gujarat, India |
| OSM Nominatim (Curated Road/Landmark) | `PDPU Road, Koba, Gandhinagar, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Curated Road/Landmark) | `PDPU Road, Koba, Gandhinagar, Gujarat, India` | SUCCESS | `23.22329, 72.64923` | 7.736 | 7736.0 | DISTANT_SECTOR | Gandhinagar, Gujarat, India |
| OSM Nominatim (Locality/Village Only) | `Koba, Gandhinagar, Gujarat, India` | SUCCESS | `23.14460, 72.63399` | 2.555 | 2554.7 | DISTANT_SECTOR | Koba - Gandhinagar Highway, Gandhinagar, Gandhinagar Taluka, Gandhinagar, Gujarat, 382421, India |
| MapTiler (Locality/Village Only) | `Koba, Gandhinagar, Gujarat, India` | SUCCESS | `23.22329, 72.64923` | 7.736 | 7736.0 | DISTANT_SECTOR | Gandhinagar, Gandhinagar Taluka, Gujarat, India |


#### Project 16104 — VRUNDAVAN ELYSIA
- **District / Sub-District:** Gandhinagar / Gandhinagar
- **Ground Truth GPS:** `(23.164538, 72.643393)` (Plot polygon with 6 vertices)
- **Raw Address (`locations.json.gz`):** `VRUNDAVAN ELYSIA, OPP. BAPS SCHOOL,`
- **Raw Address (`all_projects_111026.csv`):** `VRUNDAVAN ELYSIA, OPP. BAPS SCHOOL,  RAYSAN, GANDHINAGAR`

| Geocoding Method | Query String Tested | Status | Lat/Lon | Error Dist (km) | Error Dist (m) | Match Quality | Resolved Feature |
|---|---|---|---|---|---|---|---|
| OSM Nominatim (Raw Full CSV) | `VRUNDAVAN ELYSIA, OPP. BAPS SCHOOL,  RAYSAN, GANDHINAGAR, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Raw Full CSV) | `VRUNDAVAN ELYSIA, OPP. BAPS SCHOOL,  RAYSAN, GANDHINAGAR, Gujarat, India` | SUCCESS | `23.16714, 72.64856` | 0.603 | 602.6 | SUB_DISTRICT_LOCALITY | Raysan Road, 382 421 Gandhinagar Taluka, Gujarat, India |
| OSM Nominatim (Cleaned Regex) | `VRUNDAVAN ELYSIA OPP. BAPS SCHOOL RAYSAN GANDHINAGAR, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Cleaned Regex) | `VRUNDAVAN ELYSIA OPP. BAPS SCHOOL RAYSAN GANDHINAGAR, Gujarat, India` | SUCCESS | `23.16714, 72.64856` | 0.603 | 602.6 | SUB_DISTRICT_LOCALITY | Raysan Road, 382 421 Gandhinagar Taluka, Gujarat, India |
| OSM Nominatim (Curated Road/Landmark) | `Opp. BAPS School, Raysan, Gandhinagar, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Curated Road/Landmark) | `Opp. BAPS School, Raysan, Gandhinagar, Gujarat, India` | SUCCESS | `23.16588, 72.65038` | 0.730 | 729.8 | SUB_DISTRICT_LOCALITY | Raysan, Gandhinagar Taluka, Gujarat, India |
| OSM Nominatim (Locality/Village Only) | `Raysan, Gandhinagar, Gujarat, India` | SUCCESS | `23.16706, 72.66062` | 1.783 | 1783.4 | SUB_DISTRICT_LOCALITY | Raysan, Gandhinagar Taluka, Gandhinagar, Gujarat, India |
| MapTiler (Locality/Village Only) | `Raysan, Gandhinagar, Gujarat, India` | SUCCESS | `23.16588, 72.65038` | 0.730 | 729.8 | SUB_DISTRICT_LOCALITY | Raysan, Gandhinagar Taluka, Gujarat, India |


#### Project 16562 — THE BALCONY
- **District / Sub-District:** Gandhinagar / Gandhinagar
- **Ground Truth GPS:** `(23.185404, 72.644197)` (Plot polygon with 4 vertices)
- **Raw Address (`locations.json.gz`):** `THE BALCONY BY KAAVYARATNA, OPP. METRO STATION`
- **Raw Address (`all_projects_111026.csv`):** `THE BALCONY BY KAAVYARATNA, OPP. METRO STATION GIFT CITY ROAD,RANDESAN,GANDHINAGAR, GUJARAT`

| Geocoding Method | Query String Tested | Status | Lat/Lon | Error Dist (km) | Error Dist (m) | Match Quality | Resolved Feature |
|---|---|---|---|---|---|---|---|
| OSM Nominatim (Raw Full CSV) | `THE BALCONY BY KAAVYARATNA, OPP. METRO STATION GIFT CITY ROAD,RANDESAN,GANDHINAGAR, GUJARAT, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Raw Full CSV) | `THE BALCONY BY KAAVYARATNA, OPP. METRO STATION GIFT CITY ROAD,RANDESAN,GANDHINAGAR, GUJARAT, Gujarat, India` | SUCCESS | `23.16219, 72.68280` | 4.715 | 4715.3 | DISTANT_SECTOR | GIFT City, Gandhinagar Taluka, Gujarat, India |
| OSM Nominatim (Cleaned Regex) | `THE BALCONY BY KAAVYARATNA OPP. METRO STATION GIFT CITY ROAD RANDESAN GANDHINAGAR GUJARAT, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Cleaned Regex) | `THE BALCONY BY KAAVYARATNA OPP. METRO STATION GIFT CITY ROAD RANDESAN GANDHINAGAR GUJARAT, Gujarat, India` | SUCCESS | `23.16219, 72.68280` | 4.715 | 4715.3 | DISTANT_SECTOR | GIFT City, Gandhinagar Taluka, Gujarat, India |
| OSM Nominatim (Curated Road/Landmark) | `Gift City Road, Randesan, Gandhinagar, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Curated Road/Landmark) | `Gift City Road, Randesan, Gandhinagar, Gujarat, India` | SUCCESS | `23.16317, 72.68275` | 4.652 | 4652.0 | DISTANT_SECTOR | GIFT City Road, 382 355 Gandhinagar Taluka, Gujarat, India |
| OSM Nominatim (Locality/Village Only) | `Randesan, Gandhinagar, Gujarat, India` | SUCCESS | `23.17909, 72.64732` | 0.772 | 771.7 | SUB_DISTRICT_LOCALITY | Randesan, Randesan Road, Radesan, Gandhinagar, Gandhinagar Taluka, Gandhinagar, Gujarat, 382007, India |
| MapTiler (Locality/Village Only) | `Randesan, Gandhinagar, Gujarat, India` | SUCCESS | `23.22329, 72.64923` | 4.244 | 4243.7 | DISTANT_SECTOR | Gandhinagar, Gandhinagar Taluka, Gujarat, India |


#### Project 17255 — ATMOS BY SOLAIRE
- **District / Sub-District:** Gandhinagar / Gandhinagar
- **Ground Truth GPS:** `(23.191857, 72.619410)` (Plot polygon with 5 vertices)
- **Raw Address (`locations.json.gz`):** `ATMOS by solaire , SUB PLOT NUMBER -32/2, Opp. Akshat Icon, Near S G Highway,"Sargasan Cross Roads, Sargasan, Gandhinagar 382421 India "`
- **Raw Address (`all_projects_111026.csv`):** `ATMOS by solaire , SUB PLOT NUMBER -32/2, Opp. Akshat Icon, Near S G Highway, "Sargasan Cross Roads, Sargasan, Gandhinagar 382421 India "`

| Geocoding Method | Query String Tested | Status | Lat/Lon | Error Dist (km) | Error Dist (m) | Match Quality | Resolved Feature |
|---|---|---|---|---|---|---|---|
| OSM Nominatim (Raw Full CSV) | `ATMOS by solaire , SUB PLOT NUMBER -32/2, Opp. Akshat Icon, Near S G Highway, "Sargasan Cross Roads, Sargasan, Gandhinagar 382421 India ", Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Raw Full CSV) | `ATMOS by solaire , SUB PLOT NUMBER -32/2, Opp. Akshat Icon, Near S G Highway, "Sargasan Cross Roads, Sargasan, Gandhinagar 382421 India ", Gujarat, India` | FAILED | — | — | — | FAILED | HTTP Error 404: Not Found |
| OSM Nominatim (Cleaned Regex) | `ATMOS by solaire Opp. Akshat Icon Near S G Highway Sargasan Cross Roads Sargasan Gandhinagar 382421 India, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Cleaned Regex) | `ATMOS by solaire Opp. Akshat Icon Near S G Highway Sargasan Cross Roads Sargasan Gandhinagar 382421 India, Gujarat, India` | SUCCESS | `23.22329, 72.64923` | 4.637 | 4636.8 | DISTANT_SECTOR | Gandhinagar, Gujarat, India |
| OSM Nominatim (Curated Road/Landmark) | `Sargasan Cross Roads, Sargasan, Gandhinagar, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Curated Road/Landmark) | `Sargasan Cross Roads, Sargasan, Gandhinagar, Gujarat, India` | SUCCESS | `23.18424, 72.61544` | 0.939 | 938.9 | SUB_DISTRICT_LOCALITY | Sargasan, Gandhinagar Taluka, Gujarat, India |
| OSM Nominatim (Locality/Village Only) | `Sargasan, Gandhinagar, Gujarat, India` | SUCCESS | `23.18428, 72.61568` | 0.925 | 924.8 | SUB_DISTRICT_LOCALITY | Sargasan, Gandhinagar, Gandhinagar Taluka, Gandhinagar, Gujarat, 382421, India |
| MapTiler (Locality/Village Only) | `Sargasan, Gandhinagar, Gujarat, India` | SUCCESS | `23.18424, 72.61544` | 0.939 | 938.9 | SUB_DISTRICT_LOCALITY | Sargasan, Gandhinagar Taluka, Gujarat, India |


#### Project 17830 — SANDALWOOD
- **District / Sub-District:** Gandhinagar / Gandhinagar
- **Ground Truth GPS:** `(23.182025, 72.649753)` (Plot polygon with 5 vertices)
- **Raw Address (`locations.json.gz`):** `SURVEY NO:- 229, FINAL PLOT NO 116`
- **Raw Address (`all_projects_111026.csv`):** `SURVEY NO:- 229, FINAL PLOT NO 116 T.P.S. NO 5,RANDESAN ROAD, GANDHINAGAR,`

| Geocoding Method | Query String Tested | Status | Lat/Lon | Error Dist (km) | Error Dist (m) | Match Quality | Resolved Feature |
|---|---|---|---|---|---|---|---|
| OSM Nominatim (Raw Full CSV) | `SURVEY NO:- 229, FINAL PLOT NO 116 T.P.S. NO 5,RANDESAN ROAD, GANDHINAGAR,, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Raw Full CSV) | `SURVEY NO:- 229, FINAL PLOT NO 116 T.P.S. NO 5,RANDESAN ROAD, GANDHINAGAR,, Gujarat, India` | SUCCESS | `9.10752, 76.60391` | 1620.654 | 1620654.0 | GROSS_MISMATCH | Plot, Kerala, India |
| OSM Nominatim (Cleaned Regex) | `RANDESAN ROAD GANDHINAGAR, Gujarat, India` | SUCCESS | `23.17456, 72.64278` | 1.094 | 1093.9 | SUB_DISTRICT_LOCALITY | Randesan Road, Gandhinagar, Gandhinagar Taluka, Gandhinagar, Gujarat, 382009, India |
| MapTiler (Cleaned Regex) | `RANDESAN ROAD GANDHINAGAR, Gujarat, India` | SUCCESS | `23.17445, 72.64440` | 1.004 | 1004.5 | SUB_DISTRICT_LOCALITY | Randesan Road, 382 007 Gandhinagar Taluka, Gujarat, India |
| OSM Nominatim (Curated Road/Landmark) | `Randesan Road, Randesan, Gandhinagar, Gujarat, India` | SUCCESS | `23.17908, 72.64726` | 0.415 | 414.7 | GOOD_NEIGHBORHOOD | Randesan, Randesan Road, Radesan, Gandhinagar, Gandhinagar Taluka, Gandhinagar, Gujarat, 382007, India |
| MapTiler (Curated Road/Landmark) | `Randesan Road, Randesan, Gandhinagar, Gujarat, India` | SUCCESS | `23.17445, 72.64440` | 1.004 | 1004.5 | SUB_DISTRICT_LOCALITY | Randesan Road, 382 007 Gandhinagar Taluka, Gujarat, India |
| OSM Nominatim (Locality/Village Only) | `Randesan, Gandhinagar, Gujarat, India` | SUCCESS | `23.17909, 72.64732` | 0.410 | 410.4 | GOOD_NEIGHBORHOOD | Randesan, Randesan Road, Radesan, Gandhinagar, Gandhinagar Taluka, Gandhinagar, Gujarat, 382007, India |
| MapTiler (Locality/Village Only) | `Randesan, Gandhinagar, Gujarat, India` | SUCCESS | `23.22329, 72.64923` | 4.589 | 4588.6 | DISTANT_SECTOR | Gandhinagar, Gandhinagar Taluka, Gujarat, India |


#### Project 17855 — PROVINCE
- **District / Sub-District:** Gandhinagar / Gandhinagar
- **Ground Truth GPS:** `(23.132618, 72.576109)` (Plot polygon with 4 vertices)
- **Raw Address (`locations.json.gz`):** `NR. SAVYA SKYZ, 200' RING ROAD,ZUNDAL`
- **Raw Address (`all_projects_111026.csv`):** `NR. SAVYA SKYZ, 200' RING ROAD, ZUNDAL`

| Geocoding Method | Query String Tested | Status | Lat/Lon | Error Dist (km) | Error Dist (m) | Match Quality | Resolved Feature |
|---|---|---|---|---|---|---|---|
| OSM Nominatim (Raw Full CSV) | `NR. SAVYA SKYZ, 200' RING ROAD, ZUNDAL, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Raw Full CSV) | `NR. SAVYA SKYZ, 200' RING ROAD, ZUNDAL, Gujarat, India` | SUCCESS | `23.13531, 72.58218` | 0.689 | 689.0 | SUB_DISTRICT_LOCALITY | Zundal, Gandhinagar Taluka, Gujarat, India |
| OSM Nominatim (Cleaned Regex) | `NR. SAVYA SKYZ 200 RING ROAD ZUNDAL, Gandhinagar, Gandhinagar, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Cleaned Regex) | `NR. SAVYA SKYZ 200 RING ROAD ZUNDAL, Gandhinagar, Gandhinagar, Gujarat, India` | SUCCESS | `23.22329, 72.64923` | 12.550 | 12550.3 | GROSS_MISMATCH | Gandhinagar, Gujarat, India |
| OSM Nominatim (Curated Road/Landmark) | `200 Feet Ring Road, Zundal, Gandhinagar, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Curated Road/Landmark) | `200 Feet Ring Road, Zundal, Gandhinagar, Gujarat, India` | SUCCESS | `23.13531, 72.58218` | 0.689 | 689.0 | SUB_DISTRICT_LOCALITY | Zundal, Gandhinagar Taluka, Gujarat, India |
| OSM Nominatim (Locality/Village Only) | `Zundal, Gandhinagar, Gujarat, India` | SUCCESS | `23.13544, 72.58195` | 0.675 | 675.2 | SUB_DISTRICT_LOCALITY | Zundal, Adalaj, Gandhinagar Taluka, Gandhinagar, Gujarat, India |
| MapTiler (Locality/Village Only) | `Zundal, Gandhinagar, Gujarat, India` | SUCCESS | `23.13531, 72.58218` | 0.689 | 689.0 | SUB_DISTRICT_LOCALITY | Zundal, Gandhinagar Taluka, Gujarat, India |


#### Project 20523 — PRAMUKH PENTAGON
- **District / Sub-District:** Gandhinagar / Gandhinagar
- **Ground Truth GPS:** `(23.178045, 72.618454)` (Plot polygon with 5 vertices)
- **Raw Address (`locations.json.gz`):** `Survey No 762,TP No 28, FP NO 143,`
- **Raw Address (`all_projects_111026.csv`):** `Survey No 762,TP No 28, FP NO 143, NR THAKAR FARM,KUDASAN -POR ROAD,POR,GANDHINAGAR`

| Geocoding Method | Query String Tested | Status | Lat/Lon | Error Dist (km) | Error Dist (m) | Match Quality | Resolved Feature |
|---|---|---|---|---|---|---|---|
| OSM Nominatim (Raw Full CSV) | `Survey No 762,TP No 28, FP NO 143, NR THAKAR FARM,KUDASAN -POR ROAD,POR,GANDHINAGAR, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Raw Full CSV) | `Survey No 762,TP No 28, FP NO 143, NR THAKAR FARM,KUDASAN -POR ROAD,POR,GANDHINAGAR, Gujarat, India` | SUCCESS | `23.22329, 72.64923` | 5.933 | 5932.9 | DISTANT_SECTOR | Gandhinagar, Gujarat, India |
| OSM Nominatim (Cleaned Regex) | `NR THAKAR FARM KUDASAN POR ROAD POR GANDHINAGAR, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Cleaned Regex) | `NR THAKAR FARM KUDASAN POR ROAD POR GANDHINAGAR, Gujarat, India` | SUCCESS | `23.17967, 72.63471` | 1.672 | 1672.0 | SUB_DISTRICT_LOCALITY | Kudasan-Por Road, 382 421 Gandhinagar Taluka, Gujarat, India |
| OSM Nominatim (Curated Road/Landmark) | `Kudasan Por Road, Por, Gandhinagar, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Curated Road/Landmark) | `Kudasan Por Road, Por, Gandhinagar, Gujarat, India` | SUCCESS | `23.17967, 72.63471` | 1.672 | 1672.0 | SUB_DISTRICT_LOCALITY | Kudasan-Por Road, 382 421 Gandhinagar Taluka, Gujarat, India |
| OSM Nominatim (Locality/Village Only) | `Por, Gandhinagar, Gujarat, India` | SUCCESS | `23.17947, 72.63306` | 1.501 | 1501.0 | SUB_DISTRICT_LOCALITY | Kudasan-Por Road, Gandhinagar, Gandhinagar Taluka, Gandhinagar, Gujarat, 382009, India |
| MapTiler (Locality/Village Only) | `Por, Gandhinagar, Gujarat, India` | SUCCESS | `23.22329, 72.64923` | 5.933 | 5932.9 | DISTANT_SECTOR | Gandhinagar, Gandhinagar Taluka, Gujarat, India |


#### Project 24508 — REVANTA FORTUNE 3
- **District / Sub-District:** Gandhinagar / Gandhinagar
- **Ground Truth GPS:** `(23.154824, 72.638200)` (Plot polygon with 4 vertices)
- **Raw Address (`locations.json.gz`):** `REVANTA FORTUNE 3, NEAR GARMENT ZONE,K RAHEJA ROAD,`
- **Raw Address (`all_projects_111026.csv`):** `REVANTA FORTUNE 3, NEAR GARMENT ZONE,K RAHEJA ROAD, KOBA, GANDHINAGAR,382421`

| Geocoding Method | Query String Tested | Status | Lat/Lon | Error Dist (km) | Error Dist (m) | Match Quality | Resolved Feature |
|---|---|---|---|---|---|---|---|
| OSM Nominatim (Raw Full CSV) | `REVANTA FORTUNE 3, NEAR GARMENT ZONE,K RAHEJA ROAD, KOBA, GANDHINAGAR,382421, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Raw Full CSV) | `REVANTA FORTUNE 3, NEAR GARMENT ZONE,K RAHEJA ROAD, KOBA, GANDHINAGAR,382421, Gujarat, India` | SUCCESS | `23.22329, 72.64923` | 7.696 | 7695.8 | DISTANT_SECTOR | Gandhinagar, Gujarat, India |
| OSM Nominatim (Cleaned Regex) | `REVANTA FORTUNE 3 NEAR GARMENT ZONE K RAHEJA ROAD KOBA GANDHINAGAR 382421, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Cleaned Regex) | `REVANTA FORTUNE 3 NEAR GARMENT ZONE K RAHEJA ROAD KOBA GANDHINAGAR 382421, Gujarat, India` | SUCCESS | `23.22329, 72.64923` | 7.696 | 7695.8 | DISTANT_SECTOR | Gandhinagar, Gujarat, India |
| OSM Nominatim (Curated Road/Landmark) | `K Raheja Road, Koba, Gandhinagar, Gujarat, India` | FAILED | — | — | — | FAILED | No results |
| MapTiler (Curated Road/Landmark) | `K Raheja Road, Koba, Gandhinagar, Gujarat, India` | SUCCESS | `23.22329, 72.64923` | 7.696 | 7695.8 | DISTANT_SECTOR | Gandhinagar, Gujarat, India |
| OSM Nominatim (Locality/Village Only) | `Koba, Gandhinagar, Gujarat, India` | SUCCESS | `23.14460, 72.63399` | 1.216 | 1216.0 | SUB_DISTRICT_LOCALITY | Koba - Gandhinagar Highway, Gandhinagar, Gandhinagar Taluka, Gandhinagar, Gujarat, 382421, India |
| MapTiler (Locality/Village Only) | `Koba, Gandhinagar, Gujarat, India` | SUCCESS | `23.22329, 72.64923` | 7.696 | 7695.8 | DISTANT_SECTOR | Gandhinagar, Gandhinagar Taluka, Gujarat, India |


### 3. Aggregate Benchmark Performance
| Method / Configuration | Success Rate | Median Error (km) | Mean Error (km) | Min Error (km) | Max Error (km) | Practical Usability |
|---|---|---|---|---|---|---|
| OSM Nominatim (Raw Full CSV) | 0/9 (0.0%) | N/A | N/A | N/A | N/A | Total Failure (0% match) |
| MapTiler (Raw Full CSV) | 8/9 (88.9%) | 6.814 | 460.789 | 0.603 | 1620.654 | Unusable (District/City centroid) |
| OSM Nominatim (Cleaned Regex) | 1/9 (11.1%) | 1.094 | 1.094 | 1.094 | 1.094 | Approximate Neighborhood Only (~1-2km) |
| MapTiler (Cleaned Regex) | 9/9 (100.0%) | 4.715 | 5.121 | 0.603 | 12.550 | Unusable (District/City centroid) |
| OSM Nominatim (Curated Road/Landmark) | 1/9 (11.1%) | 0.415 | 0.415 | 0.415 | 0.415 | Approximate Neighborhood Only (~1-2km) |
| MapTiler (Curated Road/Landmark) | 9/9 (100.0%) | 1.672 | 3.399 | 0.689 | 7.736 | Approximate Neighborhood Only (~1-2km) |
| OSM Nominatim (Locality/Village Only) | 9/9 (100.0%) | 1.216 | 1.302 | 0.410 | 2.555 | Approximate Neighborhood Only (~1-2km) |
| MapTiler (Locality/Village Only) | 9/9 (100.0%) | 4.244 | 3.827 | 0.689 | 7.736 | Unusable (District/City centroid) |