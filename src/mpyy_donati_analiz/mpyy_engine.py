# -*- coding: utf-8 -*-
"""
MPYY Urban Block Morphology, Multi-Use Subdivision & Capacity-Aware Network Engine
Author / Developer: Baran Adsuna (https://github.com/baranadsuna)
CRS Standard: EPSG:5253 (TUREF / TM30)
"""
import math
import heapq
from qgis.core import (
    QgsGeometry, QgsPointXY, QgsFeature, QgsRectangle,
    QgsSpatialIndex, QgsCoordinateTransform, QgsProject, QgsWkbTypes
)


class FastRoadGraph:
    """
    Ultra-fast Prepared Network Graph Engine.
    Uses QgsSpatialIndex for O(1) node snapping, polygon boundary-point snapping,
    and multi-source Dijkstra (including nearest-facility tracking for capacity-load
    and overflow analysis) in EPSG:5253.
    """
    def __init__(self, network_layer, target_crs=None, tolerance=2.0):
        self.tolerance = tolerance
        self.nodes = []          # node_id -> QgsPointXY
        self.grid = {}           # (gx, gy) -> list of node_id
        self.adj = {}            # node_id -> list of (neighbor_id, length)
        self.sindex = QgsSpatialIndex()
        self._snap_cache = {}    # (round(x,1), round(y,1)) -> (node_id, snap_dist)
        self._build_graph(network_layer, target_crs)

    def _get_or_create_node(self, pt):
        gx = int(round(pt.x() / self.tolerance))
        gy = int(round(pt.y() / self.tolerance))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell = (gx + dx, gy + dy)
                if cell in self.grid:
                    for nid in self.grid[cell]:
                        npt = self.nodes[nid]
                        if math.hypot(pt.x() - npt.x(), pt.y() - npt.y()) <= self.tolerance:
                            return nid
        nid = len(self.nodes)
        p_copy = QgsPointXY(pt.x(), pt.y())
        self.nodes.append(p_copy)
        self.adj[nid] = []
        self.grid.setdefault((gx, gy), []).append(nid)

        feat = QgsFeature(nid)
        feat.setGeometry(QgsGeometry.fromPointXY(p_copy))
        self.sindex.addFeature(feat)
        return nid

    def _build_graph(self, layer, target_crs):
        if layer is None:
            return
        xform = None
        if target_crs is not None and layer.crs().isValid() and target_crs.isValid() and layer.crs() != target_crs:
            xform = QgsCoordinateTransform(layer.crs(), target_crs, QgsProject.instance())

        for feat in layer.getFeatures():
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue
            if xform is not None:
                geom = QgsGeometry(geom)
                try:
                    geom.transform(xform)
                except Exception:
                    pass

            lines = geom.asMultiPolyline() if geom.isMultipart() else [geom.asPolyline()]
            for line in lines:
                n_pts = len(line)
                if n_pts < 2:
                    continue
                prev_u = self._get_or_create_node(line[0])
                acc_len = 0.0
                for i in range(1, n_pts):
                    p1 = line[i - 1]
                    p2 = line[i]
                    seg_len = math.hypot(p2.x() - p1.x(), p2.y() - p1.y())
                    acc_len += seg_len
                    if i == n_pts - 1 or acc_len >= 15.0:
                        if acc_len > 0.001:
                            v = self._get_or_create_node(p2)
                            if prev_u != v:
                                self.adj[prev_u].append((v, acc_len))
                                self.adj[v].append((prev_u, acc_len))
                            prev_u = v
                            acc_len = 0.0

    def snap_point_to_node(self, pt):
        if not self.nodes:
            return None, float('inf')
        key = (round(pt.x(), 1), round(pt.y(), 1))
        if key in self._snap_cache:
            return self._snap_cache[key]

        nearest_ids = self.sindex.nearestNeighbor(pt, 1)
        if nearest_ids:
            nid = nearest_ids[0]
            npt = self.nodes[nid]
            d = math.hypot(pt.x() - npt.x(), pt.y() - npt.y())
            self._snap_cache[key] = (nid, d)
            return nid, d

        self._snap_cache[key] = (None, float('inf'))
        return None, float('inf')

    def snap_polygon_to_node(self, geom):
        """
        Snaps an urban block/building polygon to the closest road network node by checking
        both its centroid and exterior street-frontage vertices. Prevents large blocks
        from suffering artificial centroid-to-street snap penalties.
        """
        if not geom or geom.isEmpty() or not self.nodes:
            return None, float('inf')
        cpt = geom.centroid().asPoint()
        best_nid, best_d = self.snap_point_to_node(cpt)
        try:
            polys = geom.asMultiPolygon() if geom.isMultipart() else [geom.asPolygon()]
            for poly in polys:
                if not poly:
                    continue
                ring = poly[0]
                step = max(1, len(ring) // 8)
                for idx in range(0, len(ring), step):
                    vpt = ring[idx]
                    nid, d = self.snap_point_to_node(vpt)
                    # Add a mild 8m internal walk offset from block boundary to building entrance
                    eff_d = d + 8.0
                    if nid is not None and eff_d < best_d:
                        best_d = eff_d
                        best_nid = nid
        except Exception:
            pass
        return best_nid, best_d

    def multi_source_dijkstra(self, source_points, max_cutoff=4000.0):
        dist = {}
        pq = []
        for pt in source_points:
            nid, snap_d = self.snap_point_to_node(pt)
            if nid is not None and snap_d <= max_cutoff:
                if nid not in dist or snap_d < dist[nid]:
                    dist[nid] = snap_d
                    heapq.heappush(pq, (snap_d, nid))

        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, float('inf')):
                continue
            if d > max_cutoff:
                continue
            for v, w in self.adj.get(u, ()):
                nd = d + w
                if nd <= max_cutoff and nd < dist.get(v, float('inf')):
                    dist[v] = nd
                    heapq.heappush(pq, (nd, v))
        return dist

    def multi_source_dijkstra_with_nearest(self, source_items, max_cutoff=4000.0):
        """
        Runs multi-source Dijkstra from `source_items` = [(source_idx, pt), ...]
        and returns:
          - dist_map: dict[node_id -> float]
          - owner_map: dict[node_id -> source_idx] (identifies which specific existing
            facility serves each road node so we can compute exact population load
            vs. area-based capacity on every school/mosque/ASM!).
        """
        dist = {}
        owner = {}
        pq = []
        for src_idx, pt in source_items:
            nid, snap_d = self.snap_point_to_node(pt)
            if nid is not None and snap_d <= max_cutoff:
                if nid not in dist or snap_d < dist[nid]:
                    dist[nid] = snap_d
                    owner[nid] = src_idx
                    heapq.heappush(pq, (snap_d, nid, src_idx))

        while pq:
            d, u, src_idx = heapq.heappop(pq)
            if d > dist.get(u, float('inf')):
                continue
            if d > max_cutoff:
                continue
            for v, w in self.adj.get(u, ()):
                nd = d + w
                if nd <= max_cutoff and nd < dist.get(v, float('inf')):
                    dist[v] = nd
                    owner[v] = src_idx
                    heapq.heappush(pq, (nd, v, src_idx))
        return dist, owner

    def distance_from_map(self, dist_map, target_pt):
        if not dist_map:
            return float('inf')
        nid, snap_d = self.snap_point_to_node(target_pt)
        if nid is None or nid not in dist_map:
            return float('inf')
        return dist_map[nid] + snap_d


def _clean_polygon_geom(geom):
    """
    Ensures a geometry resulting from intersection/difference is a clean Polygon/MultiPolygon
    (strips any degenerate LineString/Point artifacts inside a GeometryCollection).
    """
    if not geom or geom.isEmpty():
        return None
    try:
        if QgsWkbTypes.flatType(geom.wkbType()) == QgsWkbTypes.GeometryCollection:
            polys = geom.asGeometryCollection()
            valid_polys = [
                g for g in polys
                if g and not g.isEmpty() and g.type() == QgsWkbTypes.PolygonGeometry and g.area() > 0.5
            ]
            if not valid_polys:
                return None
            if len(valid_polys) == 1:
                return valid_polys[0]
            return QgsGeometry.unaryUnion(valid_polys)
    except Exception:
        pass
    return geom


def _num_polygon_parts(geom):
    if not geom or geom.isEmpty():
        return 0
    g = _clean_polygon_geom(geom)
    if not g or g.isEmpty():
        return 0
    try:
        if g.isMultipart():
            mp = g.asMultiPolygon()
            return sum(1 for p in mp if p)
        return 1
    except Exception:
        try:
            parts = [p for p in g.asGeometryCollection() if p.type() == QgsWkbTypes.PolygonGeometry and p.area() > 1.0]
            return len(parts)
        except Exception:
            return 1


def compute_polygon_shape_metrics(geom):
    """
    Computes urban morphology shape metrics for a polygon:
      - rect_fill: Area / OrientedMinimumBoundingBox_Area in (0, 1].
        (1.0 = perfect rectangle, ~0.82+ = compact quadrilateral, ~0.50 = triangle)
      - aspect: max(w, h) / min(w, h) of OMBB
      - min_dim: min(w, h) in meters
      - ombb_angle: orientation angle in degrees
    """
    if not geom or geom.isEmpty():
        return {"rect_fill": 0.0, "aspect": 99.0, "min_dim": 0.0, "max_dim": 0.0, "ombb_angle": 0.0}
    poly_area = geom.area()
    if poly_area <= 0.1:
        return {"rect_fill": 0.0, "aspect": 99.0, "min_dim": 0.0, "max_dim": 0.0, "ombb_angle": 0.0}
    try:
        ombb_geom, ombb_area, angle, w, h = geom.orientedMinimumBoundingBox()
        if ombb_area <= 0.1 or w <= 0.1 or h <= 0.1:
            bbox = geom.boundingBox()
            w, h = max(bbox.width(), 0.1), max(bbox.height(), 0.1)
            ombb_area = w * h
            angle = 0.0
        rect_fill = min(1.0, poly_area / ombb_area)
        min_dim = min(w, h)
        max_dim = max(w, h)
        aspect = max_dim / max(min_dim, 0.1)
        return {
            "rect_fill": rect_fill,
            "aspect": aspect,
            "min_dim": min_dim,
            "max_dim": max_dim,
            "ombb_angle": angle,
        }
    except Exception:
        return {"rect_fill": 0.7, "aspect": 1.5, "min_dim": 30.0, "max_dim": 45.0, "ombb_angle": 0.0}


def _dominant_street_edge_angles(geom):
    """
    Extracts the dominant street frontage angles (in degrees) from the longest
    straight segments of the polygon exterior ring, plus its OMBB angle.
    """
    angles = []
    try:
        _, _, ombb_angle, _, _ = geom.orientedMinimumBoundingBox()
        angles.append(float(ombb_angle) % 180.0)
    except Exception:
        angles.append(0.0)

    try:
        polys = geom.asMultiPolygon() if geom.isMultipart() else [geom.asPolygon()]
        seg_weights = []
        for poly in polys:
            if not poly:
                continue
            ring = poly[0]
            for i in range(len(ring) - 1):
                dx = ring[i + 1].x() - ring[i].x()
                dy = ring[i + 1].y() - ring[i].y()
                seg_len = math.hypot(dx, dy)
                if seg_len >= 12.0:
                    ang_deg = math.degrees(math.atan2(dy, dx)) % 180.0
                    seg_weights.append((seg_len, ang_deg))
        seg_weights.sort(key=lambda x: x[0], reverse=True)
        for _, a in seg_weights[:3]:
            if all(min(abs(a - ex), 180.0 - abs(a - ex)) > 6.0 for ex in angles):
                angles.append(a)
    except Exception:
        pass
    return angles[:3] if angles else [0.0]


def _binary_slice_in_rotated_frame(geom, pivot_pt, rot_deg, axis, from_high_end, target_area):
    """
    Rotates `geom` by `rot_deg` around `pivot_pt`, slices straight across `axis`
    ('x' or 'y') from either the low end or high end to match `target_area`,
    and rotates both pieces back by `-rot_deg`.
    """
    work = QgsGeometry(geom)
    if abs(rot_deg) > 1e-4:
        work.rotate(rot_deg, pivot_pt)

    bbox = work.boundingBox()
    xmin, xmax = bbox.xMinimum(), bbox.xMaximum()
    ymin, ymax = bbox.yMinimum(), bbox.yMaximum()
    pad = 10.0

    low = xmin if axis == "x" else ymin
    high = xmax if axis == "x" else ymax
    best_piece = None

    for _ in range(14):
        mid = (low + high) * 0.5
        if axis == "x":
            if not from_high_end:
                rect = QgsRectangle(xmin - pad, ymin - pad, mid, ymax + pad)
            else:
                rect = QgsRectangle(mid, ymin - pad, xmax + pad, ymax + pad)
        else:
            if not from_high_end:
                rect = QgsRectangle(xmin - pad, ymin - pad, xmax + pad, mid)
            else:
                rect = QgsRectangle(xmin - pad, mid, xmax + pad, ymax + pad)

        clip_geom = QgsGeometry.fromRect(rect)
        piece = work.intersection(clip_geom)
        a = piece.area() if (piece and not piece.isEmpty()) else 0.0
        if not from_high_end:
            if a < target_area:
                low = mid
            else:
                high = mid
        else:
            if a < target_area:
                high = mid
            else:
                low = mid
        best_piece = piece

    if not best_piece or best_piece.isEmpty():
        return None, None

    rem_piece = work.difference(best_piece)
    if abs(rot_deg) > 1e-4:
        best_piece.rotate(-rot_deg, pivot_pt)
        if rem_piece and not rem_piece.isEmpty():
            rem_piece.rotate(-rot_deg, pivot_pt)

    return _clean_polygon_geom(best_piece), _clean_polygon_geom(rem_piece)


def _corner_quad_slice_in_rotated_frame(geom, pivot_pt, rot_deg, corner_idx, target_area, aspect_ratio=1.35):
    """
    Carves a compact orthogonal corner parcel (with aspect ratio ~1.35) anchored at one
    of the 4 street corners of the rotated bounding box. Ideal when carving a small/medium
    facility (like a 2,000 m² ASM or 2,800 m² Mosque) out of a wide urban block so it
    does not become a long skinny ribbon, while keeping the remainder Park as 1 single piece.
    """
    work = QgsGeometry(geom)
    if abs(rot_deg) > 1e-4:
        work.rotate(rot_deg, pivot_pt)

    bbox = work.boundingBox()
    xmin, xmax = bbox.xMinimum(), bbox.xMaximum()
    ymin, ymax = bbox.yMinimum(), bbox.yMaximum()
    bw = xmax - xmin
    bh = ymax - ymin
    if bw <= 10.0 or bh <= 10.0:
        return None, None

    if bw >= bh:
        w_base = math.sqrt(target_area * aspect_ratio)
        h_base = math.sqrt(target_area / aspect_ratio)
    else:
        w_base = math.sqrt(target_area / aspect_ratio)
        h_base = math.sqrt(target_area * aspect_ratio)

    low, high = 0.5, 2.8
    best_piece = None
    for _ in range(14):
        s = (low + high) * 0.5
        cw = min(bw * 0.88, w_base * s)
        ch = min(bh * 0.88, h_base * s)
        if corner_idx == 0:
            rect = QgsRectangle(xmin - 2.0, ymin - 2.0, xmin + cw, ymin + ch)
        elif corner_idx == 1:
            rect = QgsRectangle(xmax - cw, ymin - 2.0, xmax + 2.0, ymin + ch)
        elif corner_idx == 2:
            rect = QgsRectangle(xmin - 2.0, ymax - ch, xmin + cw, ymax + 2.0)
        else:
            rect = QgsRectangle(xmax - cw, ymax - ch, xmax + 2.0, ymax + 2.0)

        piece = work.intersection(QgsGeometry.fromRect(rect))
        a = piece.area() if (piece and not piece.isEmpty()) else 0.0
        if a < target_area:
            low = s
        else:
            high = s
        best_piece = piece

    if not best_piece or best_piece.isEmpty():
        return None, None

    rem_piece = work.difference(best_piece)
    if abs(rot_deg) > 1e-4:
        best_piece.rotate(-rot_deg, pivot_pt)
        if rem_piece and not rem_piece.isEmpty():
            rem_piece.rotate(-rot_deg, pivot_pt)

    return _clean_polygon_geom(best_piece), _clean_polygon_geom(rem_piece)


def _street_edge_pocket_slice_in_rotated_frame(
    geom, pivot_pt, rot_deg, edge_side, along_frac, target_area, aspect_ratio=1.30
):
    """
    Carves a compact rectangular parcel flush against a straight street edge
    (`edge_side` in ('xmax', 'xmin', 'ymax', 'ymin')) centered at `along_frac` in (0.2, 0.85).
    Specifically enables placing a second built facility (like an ASM on Ada #2544)
    along the straight eastern street frontage below a tapered northern tip, leaving a
    Park & Playground buffer between the bottom Primary School and the upper ASM!
    """
    work = QgsGeometry(geom)
    if abs(rot_deg) > 1e-4:
        work.rotate(rot_deg, pivot_pt)

    bbox = work.boundingBox()
    xmin, xmax = bbox.xMinimum(), bbox.xMaximum()
    ymin, ymax = bbox.yMinimum(), bbox.yMaximum()
    bw = xmax - xmin
    bh = ymax - ymin
    if bw <= 15.0 or bh <= 15.0:
        return None, None

    if edge_side in ("xmax", "xmin"):
        depth_base = math.sqrt(target_area / aspect_ratio)
        front_base = math.sqrt(target_area * aspect_ratio)
    else:
        front_base = math.sqrt(target_area * aspect_ratio)
        depth_base = math.sqrt(target_area / aspect_ratio)

    low, high = 0.55, 2.4
    best_piece = None
    for _ in range(14):
        s = (low + high) * 0.5
        if edge_side in ("xmax", "xmin"):
            d_w = min(bw * 0.82, depth_base * s)
            f_h = min(bh * 0.65, front_base * s)
            yc = ymin + along_frac * bh
            y0 = max(ymin - 1.0, yc - f_h * 0.5)
            y1 = min(ymax + 1.0, yc + f_h * 0.5)
            if edge_side == "xmax":
                rect = QgsRectangle(xmax - d_w, y0, xmax + 2.0, y1)
            else:
                rect = QgsRectangle(xmin - 2.0, y0, xmin + d_w, y1)
        else:
            f_w = min(bw * 0.65, front_base * s)
            d_h = min(bh * 0.82, depth_base * s)
            xc = xmin + along_frac * bw
            x0 = max(xmin - 1.0, xc - f_w * 0.5)
            x1 = min(xmax + 1.0, xc + f_w * 0.5)
            if edge_side == "ymax":
                rect = QgsRectangle(x0, ymax - d_h, x1, ymax + 2.0)
            else:
                rect = QgsRectangle(x0, ymin - 2.0, x1, ymin + d_h)

        piece = work.intersection(QgsGeometry.fromRect(rect))
        a = piece.area() if (piece and not piece.isEmpty()) else 0.0
        if a < target_area:
            low = s
        else:
            high = s
        best_piece = piece

    if not best_piece or best_piece.isEmpty():
        return None, None

    rem_piece = work.difference(best_piece)
    if abs(rot_deg) > 1e-4:
        best_piece.rotate(-rot_deg, pivot_pt)
        if rem_piece and not rem_piece.isEmpty():
            rem_piece.rotate(-rot_deg, pivot_pt)

    return _clean_polygon_geom(best_piece), _clean_polygon_geom(rem_piece)


def _score_built_parcel_geometry(built_geom, rem_geom, target_area):
    """
    Scores a candidate subdivision where `built_geom` is a Built Facility
    (School, Mosque, Health Center, Social Facility) and `rem_geom` is Park / Green Space.
    Strictly enforces:
      1. Both `built_geom` AND `rem_geom` must be single contiguous polygons (never split Park into 2 disconnected pieces!).
      2. High rectangularity (`rect_fill >= 0.80`) for `built_geom` (never triangular!).
      3. Compact aspect ratio (`1.0 <= aspect <= 2.1`) so built parcels are compact rectangles, not thin strips!
    """
    if not built_geom or built_geom.isEmpty():
        return -1e9
    if _num_polygon_parts(built_geom) != 1:
        return -1e7

    if rem_geom and not rem_geom.isEmpty():
        if _num_polygon_parts(rem_geom) != 1:
            return -1e7

    m = compute_polygon_shape_metrics(built_geom)
    rect_fill = m["rect_fill"]
    aspect = m["aspect"]
    min_dim = m["min_dim"]

    area_err = abs(built_geom.area() - target_area) / max(target_area, 1.0)
    if area_err > 0.14:
        return -1e5

    score = rect_fill * 120.0
    if rect_fill < 0.72:
        score -= (0.72 - rect_fill) * 350.0

    if 1.0 <= aspect <= 1.95:
        score += 22.0
    elif aspect > 2.1:
        score -= (aspect - 2.1) * 45.0

    if min_dim < 25.0:
        score -= (25.0 - min_dim) * 5.0

    return score


def split_polygon_by_ratios(poly_geom, ratios, is_built_flags=None):
    """
    Morphology-Aware Oriented Urban Block Subdivision Engine (Single or Sequential Split).
    """
    if not poly_geom or poly_geom.isEmpty():
        return []
    total_ratio = sum(ratios)
    if total_ratio <= 0 or len(ratios) <= 1:
        return [poly_geom]

    norm_ratios = [r / total_ratio for r in ratios]
    if is_built_flags is None:
        is_built_flags = [True] * (len(ratios) - 1) + [False]

    parts = []
    remaining = QgsGeometry(poly_geom)

    for i in range(len(norm_ratios) - 1):
        if not remaining or remaining.isEmpty():
            break
        rem_ratio_sum = sum(norm_ratios[i:])
        target_frac = norm_ratios[i] / rem_ratio_sum
        target_area = remaining.area() * target_frac

        pivot_pt = remaining.centroid().asPoint()
        candidate_angles = _dominant_street_edge_angles(remaining)

        best_score = -1e9
        best_left = None
        best_right = None

        for ang in candidate_angles:
            for axis in ("x", "y"):
                for from_high in (False, True):
                    piece, rem = _binary_slice_in_rotated_frame(
                        remaining, pivot_pt, -ang, axis, from_high, target_area
                    )
                    if piece is None or rem is None or rem.isEmpty():
                        continue
                    sc = _score_built_parcel_geometry(piece, rem, target_area)
                    if sc > best_score:
                        best_score = sc
                        best_left = piece
                        best_right = rem

        if is_built_flags[i] and target_frac <= 0.45:
            need_corner = True
            if best_left is not None:
                mb = compute_polygon_shape_metrics(best_left)
                if mb["rect_fill"] >= 0.85 and mb["aspect"] <= 2.0:
                    need_corner = False
            if need_corner:
                for ang in candidate_angles[:2]:
                    for c_idx in range(4):
                        piece, rem = _corner_quad_slice_in_rotated_frame(
                            remaining, pivot_pt, -ang, c_idx, target_area, aspect_ratio=1.35
                        )
                        if piece is None or rem is None or rem.isEmpty():
                            continue
                        sc = _score_built_parcel_geometry(piece, rem, target_area)
                        if sc > best_score:
                            best_score = sc
                            best_left = piece
                            best_right = rem

        if best_left and not best_left.isEmpty():
            parts.append(best_left)
            if best_right and not best_right.isEmpty():
                remaining = best_right
            else:
                remaining = None
                break
        else:
            break

    if remaining and not remaining.isEmpty():
        parts.append(remaining)

    return parts if parts else [poly_geom]


def subdivide_block_multi_use(
    poly_geom,
    built1_area,
    built2_area=0.0,
    carve_passive_strip=False,
    passive_area_ratio=0.28,
    neighborhood_center_pt=None,
):
    """
    Advanced Urban Design Multi-Use Block Subdivision Engine.
    Specifically implements the planner's multi-facility block layout:
      1. Optional `passive_geom`: If `carve_passive_strip=True` (for large highway-edge blocks
         like Ada #2544), slices off the outer roadside/tapered strip opposite the residential
         neighborhood as a Passive Green Buffer ('Pasif Yeşil Alan - Sade Tampon Görevli Yeşil').
      2. `built1_geom`: Compact rectangular Primary Facility (e.g. Primary School) anchored at
         one street end/corner.
      3. `built2_geom` (if `built2_area > 0`): Compact rectangular Secondary Facility (e.g. ASM)
         placed along the street frontage at the opposite end/upper-right, separated from `built1_geom`
         by a generous contiguous Park & Playground (`park_geom`) buffer!
      4. `park_geom`: Contiguous Active Green Space ('Çocuk Bahçesi & Park') between/around
         the built facilities.

    Returns dict:
      {
        "built1": QgsGeometry or None,
        "built2": QgsGeometry or None,
        "park": QgsGeometry or None,
        "passive": QgsGeometry or None,
      }
    """
    result = {"built1": None, "built2": None, "park": None, "passive": None}
    if not poly_geom or poly_geom.isEmpty():
        return result

    work_geom = QgsGeometry(poly_geom)
    total_area = work_geom.area()
    pivot_pt = work_geom.centroid().asPoint()
    angles = _dominant_street_edge_angles(work_geom)
    primary_ang = angles[0] if angles else 0.0

    # Determine which side in rotated frame faces AWAY from the residential neighborhood
    # so the Passive Green Buffer strip is placed on the outer highway side (e.g. West side + North tapered tip of Ada #2544)
    if carve_passive_strip and total_area >= 26000.0:
        rot_test = QgsGeometry(work_geom)
        if abs(primary_ang) > 1e-4:
            rot_test.rotate(-primary_ang, pivot_pt)
        bbox = rot_test.boundingBox()
        bw = bbox.xMaximum() - bbox.xMinimum()
        bh = bbox.yMaximum() - bbox.yMinimum()
        short_axis = "x" if bw <= bh else "y"
        long_axis = "y" if short_axis == "x" else "x"

        # Default outer highway side: low end of x (West) if neighborhood is East
        from_high_end = False
        if neighborhood_center_pt is not None:
            ref_g = QgsGeometry.fromPointXY(neighborhood_center_pt)
            if abs(primary_ang) > 1e-4:
                ref_g.rotate(-primary_ang, pivot_pt)
            rpt = ref_g.asPoint()
            c_rot = rot_test.centroid().asPoint()
            if short_axis == "x":
                from_high_end = (rpt.x() < c_rot.x())
            else:
                from_high_end = (rpt.y() < c_rot.y())

        target_passive = total_area * (passive_area_ratio * 0.82)
        passive_piece, main_rem = _binary_slice_in_rotated_frame(
            work_geom, pivot_pt, -primary_ang, short_axis, from_high_end, target_passive
        )
        if (
            passive_piece is not None
            and not passive_piece.isEmpty()
            and main_rem is not None
            and not main_rem.isEmpty()
            and _num_polygon_parts(main_rem) == 1
        ):
            # Also check if one end of `main_rem` along `long_axis` tapers to a narrow triangle (like the North tip of Ada #2544).
            # Slicing off that tapered tip into `passive_piece` makes the upper-right built parcel (e.g. ASM) a crisp rectangle!
            tip_area = main_rem.area() * 0.09
            tip_high, rem_high = _binary_slice_in_rotated_frame(
                main_rem, pivot_pt, -primary_ang, long_axis, True, tip_area
            )
            tip_low, rem_low = _binary_slice_in_rotated_frame(
                main_rem, pivot_pt, -primary_ang, long_axis, False, tip_area
            )
            m_high = compute_polygon_shape_metrics(tip_high) if tip_high else {"rect_fill": 1.0}
            m_low = compute_polygon_shape_metrics(tip_low) if tip_low else {"rect_fill": 1.0}

            if m_high["rect_fill"] < 0.68 and rem_high and _num_polygon_parts(rem_high) == 1:
                combined_pas = _clean_polygon_geom(QgsGeometry.unaryUnion([passive_piece, tip_high]))
                if combined_pas is not None:
                    passive_piece = combined_pas
                    main_rem = rem_high
            elif m_low["rect_fill"] < 0.68 and rem_low and _num_polygon_parts(rem_low) == 1:
                combined_pas = _clean_polygon_geom(QgsGeometry.unaryUnion([passive_piece, tip_low]))
                if combined_pas is not None:
                    passive_piece = combined_pas
                    main_rem = rem_low

            result["passive"] = passive_piece
            work_geom = main_rem

    # Step 2: Carve Built_1 (e.g. İlkokul) from work_geom as a crisp compact rectangle
    rem_area_total = work_geom.area()
    b1_target = min(built1_area, rem_area_total * 0.55)
    parts_1 = split_polygon_by_ratios(work_geom, [b1_target, rem_area_total - b1_target], is_built_flags=[True, False])
    if len(parts_1) < 2:
        result["built1"] = work_geom
        return result

    b1_geom, park_rem = parts_1[0], parts_1[1]
    result["built1"] = b1_geom

    # Step 3: If Built_2 (e.g. ASM) is requested and enough room remains for Built_2 + Park Buffer
    if built2_area >= 650.0 and park_rem and not park_rem.isEmpty() and park_rem.area() >= (built2_area + 1600.0):
        b1_center = b1_geom.centroid().asPoint()
        p_pivot = park_rem.centroid().asPoint()
        p_angles = _dominant_street_edge_angles(park_rem)

        best_b2 = None
        best_park = None
        best_b2_score = -1e9

        # Candidate A: Corner quad cuts on `park_rem` (prefer corners separated from Built_1 by Park!)
        for ang in p_angles[:2]:
            for c_idx in range(4):
                cand_b2, cand_park = _corner_quad_slice_in_rotated_frame(
                    park_rem, p_pivot, -ang, c_idx, built2_area, aspect_ratio=1.32
                )
                if cand_b2 is None or cand_park is None or cand_park.isEmpty():
                    continue
                sc = _score_built_parcel_geometry(cand_b2, cand_park, built2_area)
                if sc < 0:
                    continue
                # Ensure a physical green Park buffer gap between Built_1 and Built_2
                gap_d = b1_geom.distance(cand_b2)
                b2_c = cand_b2.centroid().asPoint()
                sep_d = math.hypot(b2_c.x() - b1_center.x(), b2_c.y() - b1_center.y())
                if gap_d >= 12.0:
                    sc += 28.0 + min(gap_d, 80.0) * 0.25
                else:
                    sc -= 35.0
                sc += min(sep_d, 180.0) * 0.08
                # Keep Built_2 on the neighborhood street side (away from the passive highway buffer strip!)
                if result["passive"] is not None:
                    d_pas = result["passive"].distance(cand_b2)
                    if d_pas < 12.0:
                        sc -= 60.0
                    else:
                        sc += min(d_pas, 50.0) * 0.5
                if neighborhood_center_pt is not None:
                    d_to_res = math.hypot(b2_c.x() - neighborhood_center_pt.x(), b2_c.y() - neighborhood_center_pt.y())
                    sc -= d_to_res * 0.02
                if sc > best_b2_score:
                    best_b2_score = sc
                    best_b2 = cand_b2
                    best_park = cand_park

        # Candidate B: Street-edge pocket cuts along the straight frontage (ideal when the far tip tapers, like Ada #2544!)
        for ang in p_angles[:2]:
            for edge_side in ("xmax", "xmin", "ymax", "ymin"):
                for along_frac in (0.58, 0.66, 0.74):
                    cand_b2, cand_park = _street_edge_pocket_slice_in_rotated_frame(
                        park_rem, p_pivot, -ang, edge_side, along_frac, built2_area, aspect_ratio=1.30
                    )
                    if cand_b2 is None or cand_park is None or cand_park.isEmpty():
                        continue
                    sc = _score_built_parcel_geometry(cand_b2, cand_park, built2_area)
                    if sc < 0:
                        continue
                    gap_d = b1_geom.distance(cand_b2)
                    if gap_d >= 15.0:
                        sc += 32.0 + min(gap_d, 80.0) * 0.25
                    else:
                        sc -= 45.0
                    # Bonus if placed on the neighborhood-facing street side
                    if neighborhood_center_pt is not None:
                        d_to_res = math.hypot(
                            cand_b2.centroid().asPoint().x() - neighborhood_center_pt.x(),
                            cand_b2.centroid().asPoint().y() - neighborhood_center_pt.y(),
                        )
                        sc -= d_to_res * 0.015
                    if sc > best_b2_score:
                        best_b2_score = sc
                        best_b2 = cand_b2
                        best_park = cand_park

        # Candidate C: Full-width orthogonal cut at the opposite end of `park_rem`
        for ang in p_angles[:2]:
            for axis in ("x", "y"):
                for from_high in (False, True):
                    cand_b2, cand_park = _binary_slice_in_rotated_frame(
                        park_rem, p_pivot, -ang, axis, from_high, built2_area
                    )
                    if cand_b2 is None or cand_park is None or cand_park.isEmpty():
                        continue
                    sc = _score_built_parcel_geometry(cand_b2, cand_park, built2_area)
                    if sc < 0:
                        continue
                    gap_d = b1_geom.distance(cand_b2)
                    if gap_d >= 12.0:
                        sc += 25.0 + min(gap_d, 80.0) * 0.20
                    else:
                        sc -= 40.0
                    if sc > best_b2_score:
                        best_b2_score = sc
                        best_b2 = cand_b2
                        best_park = cand_park

        if best_b2 is not None and best_park is not None:
            m_b2 = compute_polygon_shape_metrics(best_b2)
            if m_b2["rect_fill"] >= 0.78:
                result["built2"] = best_b2
                result["park"] = best_park
                return result

    result["park"] = park_rem
    return result
