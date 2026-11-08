# GEMINI.md — `02_gelistirilen_eklentiler/mpyy_donati_analiz/` (Google Gemini Directives)

> **Plugin Scope**: `c:\Users\lilba\OneDrive\Masaüstü\qgis_plugin\02_gelistirilen_eklentiler\mpyy_donati_analiz\`

---

## 1. Gemini Engineering Directives for `mpyy_donati_analiz` v1.8.0+

1. **`FastRoadGraph` & Multi-Source Dijkstra**:
   - Preserve the $O(1)$ / $O(\log N)$ spatial index vertex snapping in `FastRoadGraph` and single-pass multi-source `heapq` Dijkstra traversal.
   - Ensure disconnected road segments fallback gracefully or report unreachable building populations clearly as unserved (`Deficit`).
2. **MPYY Annex-2 Table & Polygon Splitting**:
   - Maintain exact legal thresholds for Turkish Spatial Plans Construction Regulation (MPYY Ek-2) across all population brackets while presenting all UI controls, table headers, and diagnostic reports in 100% English.
   - Ensure polygon splitting accurately recalculates split polygon areas in `EPSG:5253` ($\text{m}^2$) and distributes population proportionally.
3. **Qt5 & Qt6 Compatibility**:
   - Never use `PyQt5` direct imports or unscoped Qt enums. Ensure `metadata.txt` has `supportsQt6=True`, `qgisMinimumVersion=3.22`, `qgisMaximumVersion=4.99`.

---

## 2. Immutable Academic & Ethical Rules ("Değişmez Akademik ve Etik Kurallar")

1. **Sıfır Halüsinasyon (Zero Hallucination)**: Yapay zekâya uydurma veri, hayali istatistik veya sentetik katman ürettirilemez.
2. **Gerçek DOI Zorunluluğu (Real DOI Requirement)**: Dijkstra (1959) `10.1007/BF01386390`, Hansen (1959) `10.1080/01944365908978307`, Luo & Wang (2003) `10.1068/b29120`.
3. **Öksüz Analiz Yok (No Orphan Analysis)**: Every facility accessibility & capacity metric feeds directly into the Annex-2 deficit synthesis table.
4. **Koordinat Sistemi (CRS Standard)**: Enforce **EPSG:5253** (TUREF / TM30).
5. **Bireysel Sorumluluk (Individual Responsibility)**: Walk speed, snap tolerance, custom per-capita standards, and service radii are transparent and researcher-configurable.
