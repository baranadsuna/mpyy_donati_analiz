# AGENTS.md — `02_gelistirilen_eklentiler/mpyy_donati_analiz/` (MPYY Urban Facility & Service Area Analyzer v1.8.0+)

> **Plugin Scope**: `c:\Users\lilba\OneDrive\Masaüstü\qgis_plugin\02_gelistirilen_eklentiler\mpyy_donati_analiz\`
> **Version**: `v1.8.0+` (QGIS 3.22–4.99, Qt5 & Qt6 Compatible, 100% English UI Default)

---

## 1. Domain Architecture & Algorithmic Invariants

`mpyy_donati_analiz` (**MPYY Urban Social & Technical Infrastructure Accessibility & Capacity Analyzer**) implements legal and spatial urban facility analysis in accordance with **Turkish Spatial Plans Construction Regulation (Mekânsal Planlar Yapım Yönetmeliği — MPYY) Annex-2 (Ek-2) Minimum Standards**:

1. **`FastRoadGraph` $O(1)$ / $O(\log N)$ Spatial Index Graph Construction**:
   - Builds a topological pedestrian/road network graph from line layers (`LineString` / `MultiLineString`) in **EPSG:5253**.
   - Uses `QgsSpatialIndex` (or grid-bucket spatial hashing with configurable snap tolerance, e.g., `1.0m`–`5.0m`) to snap road endpoints and facility/building access nodes in $O(\log N)$ / amortized $O(1)$ time—strictly forbidding $O(N^2)$ pairwise vertex loops.
2. **Multi-Source Dijkstra Shortest-Path Engine**:
   - Initializes the priority queue (`heapq`) with all active facility access nodes simultaneously at distance $d = 0$.
   - Computes exact network walking distances ($d_{\text{net}}$) from every road node and snapped building/parcel centroid to its nearest facility in a single $O((V + E) \log V)$ pass.
3. **MPYY Annex-2 (Ek-2) Legal Standards Compliance**:
   - Evaluates per-capita minimum land area ($\text{m}^2/\text{person}$) and maximum walking distance thresholds ($r_{\max}$, e.g., $300\text{ m}$ for Kindergarten/Preschool, $500\text{ m}$ for Primary School & Family Health Center, $750\text{ m}$ for Secondary School, $1000\text{ m}$ for High School) across demographic settlement hierarchies (`< 15,000`, `15,000–45,000`, `45,000–100,000`, `> 100,000` population).
4. **Polygon Splitting & Parcel/Building Service Classification**:
   - Supports geometric polygon splitting / service boundary clipping along network isochrone or Euclidean buffers so partially served large parcels or blocks are accurately partitioned into served (`Served`) vs. unserved (`Deficit`) sub-polygons with proportional population allocation.
5. **Verified Academic Citations (Rule 2)**:
   - Dijkstra, E. W. (1959) — `10.1007/BF01386390`
   - Hansen, W. G. (1959) Accessibility — `10.1080/01944365908978307`
   - Luo, W., & Wang, F. (2003) 2SFCA — `10.1068/b29120`
   - Talen, E., & Anselin, L. (1998) — `10.1068/a300595`

---

## 2. Mandatory Engineering Rules for `mpyy_donati_analiz`

- **100% English UI Default**: All dialog tabs, facility category names (with MPYY Annex-2 codes in parentheses where helpful), progress logs, layer names, and HTML/CSV reports must default to 100% English.
- **Qt5 & Qt6 Compatibility**:
  - Import only from `qgis.PyQt.QtCore`, `qgis.PyQt.QtWidgets`, `qgis.PyQt.QtGui`.
  - Use scoped enums (`QgsMapLayerProxyModel.Filter`, `QgsWkbTypes.GeometryType`, `Qt.AlignmentFlag`, `QMessageBox.StandardButton`) and `.exec()`.
- **EPSG:5253 CRS Enforcement**: Automatically check and reproject input layers (Facilities, Buildings/Population, Road Network) to `EPSG:5253` before building `FastRoadGraph` or computing areas.

---

## 3. Workstation & Verification Commands

- **Developer**: Baran Adsuna (`https://github.com/baranadsuna`, Dokuz Eylül University, Urban & Regional Planning)
- **Workstation**: Windows 11 Pro, Intel Core i7-13620H, RTX 4050 (`6141 MiB`), `16 GB` RAM.
- **Run E2E Verification**:
  ```powershell
  & "C:\Program Files\QGIS 3.44.14\bin\python-qgis-ltr.bat" 04_test_ve_dogrulama_laboratuvari/run_all_tests.py
  ```
