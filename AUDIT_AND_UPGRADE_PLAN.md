# Technical Audit & QGIS 3/4 (Qt5/Qt6) Upgrade Plan: `mpyy_donati_analiz`

* **Baseline Archive Audited:** `mpyy_donati_analiz-v14.zip` (`version=1.8.0`)
* **Target Release Version:** `2.0.0` (`mpyy_donati_analiz.zip`)
* **Author & Maintainer:** Baran Adsuna (`https://github.com/baranadsuna`)
* **Target Geodetic Standard:** `EPSG:5253` (TUREF / TM30)

---

## 1. Executive Summary of Audit Findings

An line-by-line inspection of `src/mpyy_donati_analiz/` (`metadata.txt`, `mpyy_plugin.py`, `mpyy_engine.py`, and `mpyy_dialog.py`) confirmed that the core spatial engine (`FastRoadGraph` and `split_polygon_by_ratios`) is algorithmically sound and self-contained. However, four structural upgrades are required to meet international QGIS Plugin Repository standards, QGIS 4.x (Qt6/PyQt6) compatibility, and `EPSG:5253` geodetic governance:

1. **Default UI Language & Internationalization (`mpyy_dialog.py`):**
   * *Finding:* Although `TRANSLATIONS` (lines 31–188) already contains complete dictionaries for English (`"en"`), Turkish (`"tr"`), Chinese (`"zh"`), and Spanish (`"es"`), `MPYYDonatiDialog.__init__` (lines 364–368) hardcodes `self.current_lang = "tr"` and initializes `self.cmb_lang` with Turkish at index 0. Additionally, `build_html_report` (lines 1311–1375) and `run_full_analysis` narrative strings (lines 1045–1236) contain Turkish-only report headers when running in English mode.
   * *Upgrade Action:* Switch the default initialization language to English (`self.current_lang = "en"`, `self.apply_language("en")`), place `"English (EN)"` as the default active item in `self.cmb_lang`, localize the HTML report generator (`build_html_report`) and toolbar action strings to respect `self.current_lang`, while preserving full 1-click switching across `en`, `tr`, `zh`, and `es`.

2. **`metadata.txt` Modernization for QGIS 3.x & 4.x (`metadata.txt`):**
   * *Finding:* `metadata.txt` lacks `qgisMaximumVersion=4.99`, `supportsQt6=True`, and `license=GPL-2.0-or-later`, and points to placeholder URLs (`https://github.com/planlama/mpyy_donati_analiz`).
   * *Upgrade Action:* Update `metadata.txt` with English primary metadata, `qgisMinimumVersion=3.22`, `qgisMaximumVersion=4.99`, `supportsQt6=True`, `license=GPL-2.0-or-later`, and verified URLs under `https://github.com/baranadsuna/mpyy_donati_analiz` and `https://baranadsuna.github.io/mpyy_donati_analiz/`.

3. **Qt5 / Qt6 Scoped Enum & `QgsWkbTypes` Compatibility (`mpyy_dialog.py`):**
   * *Finding:* `mpyy_dialog.py` uses unscoped PyQt5 enums that raise `AttributeError` under PyQt6 / QGIS 4.x.
   * *Upgrade Action:* Replace all unscoped Qt and QGIS enums with Qt5/Qt6 dual-compatible scoped attributes or a dedicated compatibility helper:

| Legacy Unscoped Symbol (`mpyy_dialog.py`) | Line(s) | Upgraded Qt5/Qt6 Compatible Scoped Symbol |
| :--- | :--- | :--- |
| `Qt.transparent`, `Qt.NoPen`, `Qt.NoBrush` | 298, 305, 344, 351 | `Qt.GlobalColor.transparent`, `Qt.PenStyle.NoPen`, `Qt.BrushStyle.NoBrush` |
| `QPainter.Antialiasing` | 300, 353 | `QPainter.RenderHint.Antialiasing` |
| `Qt.KeepAspectRatio`, `Qt.SmoothTransformation` | 384 | `Qt.AspectRatioMode.KeepAspectRatio`, `Qt.TransformationMode.SmoothTransformation` |
| `Qt.AlignCenter` | 482, 644, 668 | `Qt.AlignmentFlag.AlignCenter` |
| `QHeaderView.Stretch`, `QHeaderView.Interactive` | 484–486 | `QHeaderView.ResizeMode.Stretch`, `QHeaderView.ResizeMode.Interactive` |
| `Qt.UserRole` | 593, 632, 660, 700, 736 | `Qt.ItemDataRole.UserRole` |
| `QFont.Bold`, `QFont.DemiBold` | 623–624, 661 | `QFont.Weight.Bold`, `QFont.Weight.DemiBold` |
| `QgsWkbTypes.PolygonGeometry`, `PointGeometry`, `LineGeometry` | 612, 688, 690, 836 | `QgsWkbTypes.GeometryType.PolygonGeometry`, `PointGeometry`, `LineGeometry` |
| `QVariant.String`, `QVariant.Int`, `QVariant.Double` | 810–813, 889–900, 976–983 | Scoped `QMetaType.Type` / `QVariant` compatibility wrapper |

4. **`EPSG:5253` (TUREF / TM30) Default CRS Enforcement (`mpyy_dialog.py`):**
   * *Finding:* `create_demo_layers()` at line 1378 hardcodes `crs = "EPSG:32635"`, and `run_full_analysis()` at line 795 adopts `vac_poly_lyr.crs()` without checking if the CRS is geographic (degrees) or defaulting to `EPSG:5253`.
   * *Upgrade Action:* Set `crs = "EPSG:5253"` (with TUREF / TM30 coordinates `base_x = 498000.0, base_y = 4254000.0`) in `create_demo_layers()`, and automatically reproject geographic layers to `EPSG:5253` during `run_full_analysis()` so all Euclidean and Dijkstra road-network distances are strictly evaluated in metric meters ($\text{m}$) and square meters ($\text{m}^2$).

---

## 2. Verification Matrix

| Verification Gate | Target Criterion | Validation Method |
| :--- | :--- | :--- |
| **Default Language Gate** | Opens in English (`"en"`) by default; switches cleanly between `en`, `tr`, `zh`, `es` | Headless PyQGIS instantiation & screenshot capture (`gui_step1_en_table.png`) |
| **Qt5 / Qt6 Enum Gate** | Zero unscoped Qt5-only enums remaining in `src/mpyy_donati_analiz/` | Static AST audit & live execution in QGIS 3.44.14 LTR |
| **EPSG:5253 CRS Gate** | Sample generator and analysis engine operate natively in `EPSG:5253` | Assert `alloc_lyr.crs().authid() == "EPSG:5253"` in E2E test suite |
| **Algorithmic Integrity Gate** | `FastRoadGraph.multi_source_dijkstra` and `split_polygon_by_ratios` produce exact Annex-2 splits | Assert output polygon count, area conservation ($\sum A_{\text{part}} = A_{\text{parcel}}$), and HTML report generation (`gui_step2_report_tab.png`) |
