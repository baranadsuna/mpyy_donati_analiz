# Academic Methodology & Operational Guide: `mpyy_donati_analiz` (v2.1.0)

* **Plugin Name:** MPYY Urban Facility Accessibility, Capacity & Spatial Optimization (`mpyy_donati_analiz`)
* **Version:** `2.1.0` (QGIS 3.x & 4.x Compatible, `supportsQt6=True`, `qgisMaximumVersion=4.99`)
* **Default UI Language:** English (`en`), with instant runtime selector for Turkish (`tr`), Chinese (`zh`), and Spanish (`es`)
* **Standard Projected CRS:** `EPSG:5253` (TUREF / TM30)
* **Author:** Baran Adsuna (`https://github.com/baranadsuna`)

---

## 1. Urban Planning Problem Statement

In statutory urban planning under the Turkish Spatial Plans Construction Regulation (*Mekânsal Planlar Yapım Yönetmeliği — MPYY Annex-2*), planners must evaluate whether residential blocks have adequate pedestrian access to public facilities (primary/middle/high schools, kindergarten/nursery, family health centers, hospitals, places of worship, parks, and social-cultural centers) and allocate vacant urban parcels (*boş imar adaları*) to resolve deficits without over-allocating redundant parks or oversized facilities.

Relying solely on Euclidean (*as-the-crow-flies*) buffers overestimates accessibility whenever railway tracks, streams, highways, or cul-de-sacs sever pedestrian routes. Conversely, allocating an entire large vacant urban block ($> 15,000\text{ m}^2$) to a single small facility or oversized park wastes scarce urban development land. Furthermore, proposing residential growth blocks without auditing road-network accessibility and carrying-capacity overflow turns zoning into guesswork.

`mpyy_donati_analiz` resolves these challenges within a unified core workflow implemented across [`mpyy_engine.py`](../src/mpyy_donati_analiz/mpyy_engine.py) and [`mpyy_dialog.py`](../src/mpyy_donati_analiz/mpyy_dialog.py).

---

## 2. Mathematical Formulation & Algorithmic Architecture

### 2.1 Prepared Road Graph & $O(1)$ Spatial Index Snapping (`FastRoadGraph`)
Given a road centerline vector layer $\mathcal{L}_{\text{net}}$ transformed to the working metric CRS (`EPSG:5253`), `FastRoadGraph` constructs a compressed undirected graph $G = (V, E, w)$:
* **Topological Vertex Coalescing:** Endpoints and intermediate polyline vertices (sampled only when accumulated segment length $\ell_{\text{acc}} \ge 15.0\text{ m}$) are snapped within tolerance $\tau = 2.5\text{ m}$ using a 9-neighbor spatial grid hash $(g_x, g_y) = (\lfloor x/\tau \rceil, \lfloor y/\tau \rceil)$.
* **$O(1)$ Cached Nearest-Node Snapping (`snap_point_to_node`):** All graph vertices are indexed in a C++ R-tree (`QgsSpatialIndex`) paired with a coordinate hash cache `(round(x, 1), round(y, 1))`:

$$(v^*(p),\, d_{\text{snap}}(p)) = \arg\min_{v \in V} \|p - \mathbf{x}_v\|_2$$

### 2.2 Multi-Source Dijkstra Network P-Location Catchments (`FastRoadGraph.multi_source_dijkstra`)
Grounded in **Dijkstra (1959)** ([DOI: `10.1007/BF01386390`](https://doi.org/10.1007/BF01386390)) and graph-median network assignment (**Hakimi, 1964**, [DOI: `10.1287/opre.12.3.450`](https://doi.org/10.1287/opre.12.3.450)), `multi_source_dijkstra` seeds the binary min-heap (`heapq`) with all existing facility centroids $\mathcal{F}_k$ of category $k$ simultaneously and tracks both shortest-path distance $D_k(u)$ and owning facility index $\text{owner}_k(u)$ (p-location demand accumulation $D_j$):

$$D_k(u) = \min_{f \in \mathcal{F}_k} \left( d_{\text{snap}}(f) + \min_{\pi: v^*(f) \leadsto u} \sum_{e \in \pi} w(e) \right), \qquad \forall u \in V \text{ with } D_k(u) \le D_{\max}$$

For each residential block $r_i$ with polygon area $A_i$ and area-weighted population $P_i = P_{\text{total}} \frac{A_i}{\sum_{j} A_j}$, the plugin evaluates both Euclidean distance $d_{\text{euclid}}(r_i, k)$ and network distance $d_{\text{road}}(r_i, k) = D_k(v^*(r_i)) + d_{\text{snap}}(r_i)$, plus facility overload ratio $D_j / C_j$:
1. **`OK`:** $d_{\text{euclid}} \le R_{\text{euclid},k}$, $d_{\text{road}} \le R_{\text{net},k}$, and assigned facility load $D_j \le 1.05\,C_j$.
2. **`CAPACITY OVERLOAD`:** Distance thresholds hold, yet $D_j > 1.05\,C_j$ with excess load $D_j - C_j \ge 350$ triggers overflow-relief scoring.
3. **`BIRD OK / NO ROAD ACCESS` (Barrier Diagnostic):** $d_{\text{euclid}} \le R_{\text{euclid},k}$ while $d_{\text{road}} > R_{\text{net},k}$.
4. **`NO ACCESS`:** Both thresholds exceeded; $P_i$ is added to $P_{\text{unserved}}(k)$.

### 2.3 Core Stochastic Per-Block Deficit Weighting (`AdaptiveAmenityWeightingEngine`)
Synthesizing capacity-to-demand ratio modeling (**Luo & Wang, 2003**, [DOI: `10.1068/b29120`](https://doi.org/10.1068/b29120)) and Enhanced Two-Step Floating Catchment Area decay (**Luo & Qi, 2009**, [DOI: `10.1016/j.healthplace.2009.06.002`](https://doi.org/10.1016/j.healthplace.2009.06.002)), `compute_block_amenity_profiles` traverses existing residential blocks in seeded stochastic order (preventing geographic order bias) and computes each block's accessible facility area per person $s_{i,k}$ against MPYY Annex-2 normative standards $T_k$ (e.g., Park $10.0\text{ m}^2$, Primary School $2.0\text{ m}^2$, Middle School $2.0\text{ m}^2$, High School $2.0\text{ m}^2$, Kindergarten $0.50\text{ m}^2$, Health/ASM $0.75\text{ m}^2$):

$$W_{i,k} = \max\!\left(0,\; \min\!\left(1,\; \frac{T_k - s_{i,k}}{T_k}\right)\right) \in [0.0, 1.0]$$

For each candidate vacant block $v$, `compute_neighborhood_deficit_weights` computes the population-weighted local deficit vector $\bar{W}_k(v)$ across neighboring residential blocks (enforcing a $450\text{ m}$ existing-park proximity safeguard $\bar{W}_{\text{park}}(v) \leftarrow 0$ whenever a sufficient park already exists within walking distance). Each eligible candidate facility $k$ with $A_v \ge A_{\min,k}$ is scored dynamically and relieves $\bar{W}_k$ upon placement:

$$\text{Score}(v, k) = \frac{\left(2.4 \cdot P_{\text{newly\_covered}}(v, k) + 0.45 \cdot D_{\text{pop}}(k)\right) \cdot \left(1.0 + 1.15\,\bar{W}_k(v)\right) \cdot \text{Scale}(A_v, k)}{1.0 + 0.70 \cdot N_{\text{allocated}}(k)}$$

### 2.4 Orthogonal Multi-Use & Park-Buffered Subdivision (`subdivide_block_multi_use`, `split_polygon_by_ratios`)
When allocating vacant urban blocks:
* **Highway-Edge / Sliver Islands:** Narrow or acute-angle strips ($A_v < 1500\text{ m}^2$, $\text{min\_dim} < 22\text{ m}$, or `rect_fill` $< 0.62$) are classified outside MPYY as **Passive Green Buffers** (`Onerilen_Pasif_Yesil_Alanlar`).
* **Multi-Use Orthogonal Subdivision:** Large regular blocks are split along the dominant street frontage via a 12-iteration binary search (`split_polygon_by_ratios`, relative error $\le 2^{-12} \approx 0.0244\%$) into 1–2 compact built facilities + a local Park buffer (+ outer Passive Green Strip for blocks $\ge 26,000\text{ m}^2$ with $\text{rect\_fill} < 0.72$).
* **Compact Lot + Residential Preservation Guard:** When assigning compact facilities (`anaokulu`, `asm`, `ibadet`) or when a split leaves excess green area near an already-adequate park, the engine avoids filling the entire block with an oversized park and designates the well-served remainder to **Residential Development Areas** (`Onerilen_Konut_Adalari`, kept strictly separate from `MPYY_Onerilen_ve_Bolunen_Donati_Alanlari`).

### 2.5 Unified Residential Walkability & Carrying-Capacity Feedback (`evaluate_housing_parcel_equilibrium`)
When the unified propose-and-display residential option is checked (`Onerilen_Konut_Adalari`), every proposed residential block is evaluated using Gaussian/piecewise pedestrian road-network decay $u_k(d)$ to Primary School ($500\text{ m}$), Park ($500\text{ m}$), ASM ($500\text{ m}$), Middle School ($1000\text{ m}$), and Commercial ($800\text{ m}$), combined with carrying-capacity feedback after adding prospective population $P_{\text{new}}$ at $180\text{ pers/ha}$:

$$S_{\text{res}} = 100 \cdot \left(0.27\,u_{\text{sch}} + 0.22\,u_{\text{park}} + 0.20\,u_{\text{asm}} + 0.15\,u_{\text{mid}} + 0.08\,u_{\text{comm}} + 0.08\,C_{\text{safe}}\right) \in [0, 100]$$

### 2.6 Plan Decisions vs. Actual Land Use Discrepancy Audit (`PlanActualDiffEngine`)
Dedicated Tab 2 overlays historical/approved zoning decisions against field land-use surveys in `EPSG:5253`, quantifying transition matrices (`BOS_ADA` unrealized commercial/facility parcels, `DONATI_KAYBI` MPYY Article 26 equivalent-area obligations, and `UYUMLU` conforming parcels).

---

## 3. Real PyQGIS GUI Workflow

| Stage | Screenshot Asset | Operational Description |
| :--- | :--- | :--- |
| **Stage 1: English Default Table & Streamlined Controls** | ![Stage 1 English Table UI](assets/gui_step1_en_table.png) | Opens in English (`en`) by default with a 4-language switcher (`en`, `tr`, `zh`, `es`), scrollable Tab 1 layout with 7+ visible editable rows (`Kindergarten` included, `Residential` excluded from amenities), core-engine automation, and 4 unified output toggles including `Propose and Display Residential Development Blocks`. |
| **Stage 1 (TR): Localized Interface Validation** | ![Stage 1 Turkish Table UI](assets/gui_step1_tr_clean.png) | Instant runtime translation into Turkish (`tr`) preserving crisp non-clipped tab titles, headers, and action buttons. |
| **Stage 2: Detailed Accessibility & Equilibrium Report** | ![Stage 2 Report Tab](assets/gui_step2_report_tab.png) | After clicking **RUN SMART ANNEX-2 ANALYSIS AND RENDER ON MAP**, the plugin populates grouped MPYY, Residential (`Onerilen_Konut_Adalari`), and Non-MPYY (`Pasif Yesil` / `Ticari Demo`) layers and renders detailed E2SFCA deficit tables and parcel-by-parcel rationales. |

---

## 4. Verified Academic References (Crossref Validated)

1. **Dijkstra, E. W. (1959).** *A note on two problems in connexion with graphs*. Numerische Mathematik, 1(1), 269–271. **DOI:** [`10.1007/BF01386390`](https://doi.org/10.1007/BF01386390)
2. **Luo, W., & Wang, F. (2003).** *Measures of Spatial Accessibility to Health Care in a GIS Environment: Synthesis and a Case Study in the Chicago Region*. Environment and Planning B: Planning and Design, 30(6), 865–884. **DOI:** [`10.1068/b29120`](https://doi.org/10.1068/b29120)
3. **Luo, W., & Qi, Y. (2009).** *An enhanced two-step floating catchment area (E2SFCA) method for measuring spatial accessibility to primary care physicians*. Health & Place, 15(4), 1100–1107. **DOI:** [`10.1016/j.healthplace.2009.06.002`](https://doi.org/10.1016/j.healthplace.2009.06.002)
4. **Hakimi, S. L. (1964).** *Optimum Locations of Switching Centers and the Absolute Centers and Medians of a Graph*. Operations Research, 12(3), 450–459. **DOI:** [`10.1287/opre.12.3.450`](https://doi.org/10.1287/opre.12.3.450)
