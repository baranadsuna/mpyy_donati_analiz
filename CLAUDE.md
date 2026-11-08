# CLAUDE.md — `02_gelistirilen_eklentiler/mpyy_donati_analiz/` (Anthropic Claude Directives)

> **Plugin Scope**: `c:\Users\lilba\OneDrive\Masaüstü\qgis_plugin\02_gelistirilen_eklentiler\mpyy_donati_analiz\`

---

## 1. Claude Code Rules for `mpyy_donati_analiz` v1.8.0+

- **Core Responsibilities**:
  - `FastRoadGraph`: Spatial-indexed road network topology builder in `EPSG:5253`.
  - Multi-Source Dijkstra: Simultaneous shortest-path calculation from all facility points.
  - MPYY Annex-2 (Ek-2) Compliance: Per-capita area ($\text{m}^2/\text{person}$) and walking radius ($r_{\max}$) deficit evaluation.
  - Polygon Splitting: Service area clipping and proportional population allocation.
- **UI & Compatibility**:
  - 100% English GUI, logs, and HTML synthesis reports by default.
  - Full Qt5/Qt6 & QGIS 3.22–4.99 compatibility (`qgis.PyQt`, scoped enums, `.exec()`).

---

## 2. Workstation & Verification

- **Developer**: Baran Adsuna (`https://github.com/baranadsuna`, Dokuz Eylül University, Urban & Regional Planning)
- **Runtime**: `C:\Program Files\QGIS 3.44.14\bin\python-qgis-ltr.bat` (Windows 11 Pro, i7-13620H, RTX 4050 `6141 MiB`, `16 GB` RAM).
