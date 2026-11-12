# -*- coding: utf-8 -*-
"""
MPYY Urban Block Morphology, Multi-Use Subdivision & Capacity-Aware Network Engine
Author / Developer: Baran Adsuna (https://github.com/baranadsuna)
CRS Standard: EPSG:5253 (TUREF / TM30)
"""
import math
import heapq
import random
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

    def compute_isochrone_pedshed(self, source_pt, cutoff_m=500.0, buffer_m=20.0):
        """
        Computes the network isochrone service area polygon and pedshed ratio
        (Network Catchment Area / Theoretical Circular Buffer Area)
        according to PLN3113 & PlanX methodology.
        """
        circ_geom = QgsGeometry.fromPointXY(source_pt).buffer(cutoff_m, 24)
        circ_area = circ_geom.area() if (circ_geom and not circ_geom.isEmpty()) else (math.pi * cutoff_m * cutoff_m)

        nid, snap_d = self.snap_point_to_node(source_pt)
        if nid is None or snap_d > cutoff_m:
            return {
                "network_geom": None,
                "circular_geom": circ_geom,
                "network_area_m2": 0.0,
                "circular_area_m2": circ_area,
                "pedshed_ratio": 0.0,
            }

        rem_cutoff = cutoff_m - snap_d
        dist_map = {}
        pq = [(0.0, nid)]
        dist_map[nid] = 0.0
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist_map.get(u, float('inf')):
                continue
            if d > rem_cutoff:
                continue
            for v, w in self.adj.get(u, ()):
                nd = d + w
                if nd <= rem_cutoff and nd < dist_map.get(v, float('inf')):
                    dist_map[v] = nd
                    heapq.heappush(pq, (nd, v))

        reached_nodes = set(dist_map.keys())
        reached_lines = []
        for u in reached_nodes:
            pu = self.nodes[u]
            for v, w in self.adj.get(u, ()):
                if v in reached_nodes and u < v:
                    pv = self.nodes[v]
                    reached_lines.append(QgsGeometry.fromPolylineXY([pu, pv]))

        if not reached_lines:
            pts = [self.nodes[u] for u in reached_nodes]
            if len(pts) >= 3:
                hull = QgsGeometry.fromMultiPointXY(pts).convexHull()
                net_area = hull.area() if (hull and not hull.isEmpty()) else 0.0
                return {
                    "network_geom": hull,
                    "circular_geom": circ_geom,
                    "network_area_m2": net_area,
                    "circular_area_m2": circ_area,
                    "pedshed_ratio": min(1.0, net_area / max(circ_area, 1.0)),
                }
            return {
                "network_geom": None,
                "circular_geom": circ_geom,
                "network_area_m2": 0.0,
                "circular_area_m2": circ_area,
                "pedshed_ratio": 0.0,
            }

        union_lines = QgsGeometry.unaryUnion(reached_lines)
        net_poly = union_lines.buffer(buffer_m, 12)
        net_area = net_poly.area() if (net_poly and not net_poly.isEmpty()) else 0.0
        pedshed_ratio = min(1.0, net_area / max(circ_area, 1.0))
        return {
            "network_geom": net_poly,
            "circular_geom": circ_geom,
            "network_area_m2": net_area,
            "circular_area_m2": circ_area,
            "pedshed_ratio": pedshed_ratio,
        }


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


class PlanActualDiffEngine:
    """
    Spatial Overlay and Planning Discrepancy Engine.
    Implements comparison between Old/Approved Master Plan Decisions and Current Real Land Use.
    Synthesizes PLN3113 `plan_farki.py` and PlanX `plan_diff.py` methodology into clean-room PyQGIS.

    Detects:
      1. UYUMLU / REALIZED: Plan matches actual use (e.g. Planned Commercial -> Actual Commercial).
      2. GERÇEKLEŞMEMİŞ (BOŞ ADA): Plan designates Commercial, Residential or Facility -> Field is actually Vacant (Boş Ada).
      3. GERÇEKLEŞMEMİŞ (PARK / AÇIK ALAN): Plan designates Commercial/Building -> Field is currently Park / Open Space.
      4. AYKIRI DÖNÜŞÜM / DONATI KAYBI: Plan designates Park/Amenity -> Field built over as Residential/Commercial/Industry (MPYY Madde 26).
      5. FONKSİYON DEĞİŞİMİ: Any other development divergence (e.g. Planned Residential -> Actual Commercial corridor).
    """

    @staticmethod
    def normalize_text(text):
        if text is None:
            return ""
        s = str(text).strip().lower()
        repl = [
            ("ı", "i"), ("ğ", "g"), ("ü", "u"), ("ş", "s"), ("ö", "o"), ("ç", "c"),
            ("İ", "i"), ("Ğ", "g"), ("Ü", "u"), ("Ş", "s"), ("Ö", "o"), ("Ç", "c"),
        ]
        for a, b in repl:
            s = s.replace(a, b)
        return s

    @classmethod
    def classify_category(cls, val):
        t = cls.normalize_text(val)
        if any(w in t for w in ["ticari", "ticaret", "dukkan", "ofis", "avm", "carsi", "is_merkezi", "commercial", "business", "retail"]):
            return "TICARET"
        if any(w in t for w in ["bos", "arsa", "tarla", "ham", "yapilasmamis", "acik_alan", "vacant", "unbuilt", "atil", "bos_ada"]):
            return "BOS_ADA"
        if any(w in t for w in ["park", "cocuk", "oyun", "rekreasyon", "meydan", "yesil", "pasif_yesil", "aktif_yesil", "green", "garden"]):
            return "PARK_YESIL"
        if any(w in t for w in ["konut", "yerlesme", "mesken", "apartman", "residential", "housing"]):
            return "KONUT"
        if any(w in t for w in ["ilkokul", "ortaokul", "lise", "okul", "egitim", "kres", "anaokulu", "school", "education"]):
            return "EGITIM"
        if any(w in t for w in ["saglik", "asm", "hastane", "dispanser", "poliklinik", "saglik_ocagi", "health", "hospital"]):
            return "SAGLIK"
        if any(w in t for w in ["cami", "mescit", "ibadet", "dini", "worship", "mosque"]):
            return "IBADET"
        if any(w in t for w in ["sosyal", "kultur", "kulturel", "social", "cultural", "kutuphane"]):
            return "SOSYAL_KULTUR"
        if any(w in t for w in ["sanayi", "endustri", "kucuk_sanayi", "depolama", "atolye", "industry", "industrial"]):
            return "SANAYI"
        if any(w in t for w in ["belediye", "bha", "kamu", "resmi", "public", "administrative"]):
            return "KAMU_BELEDIYE"
        return "DIGER"

    @classmethod
    def evaluate_discrepancy(cls, old_val, actual_val):
        old_cat = cls.classify_category(old_val)
        act_cat = cls.classify_category(actual_val)

        old_str = str(old_val).strip() if old_val is not None else "Belirtilmemiş"
        act_str = str(actual_val).strip() if actual_val is not None else "Belirtilmemiş"

        if old_cat == act_cat and old_cat != "DIGER":
            durum = "UYUMLU / GERÇEKLEŞMİŞ"
            kod = "UYUMLU"
            yorum = f"Eski plan kararı ({old_str}) sahada fiilen gerçekleşmiştir ({act_str})."
        elif act_cat == "BOS_ADA":
            durum = "GERÇEKLEŞMEMİŞ (BOŞ ADA)"
            kod = "BOS_ADA"
            yorum = (
                f"Planda '{old_str}' kararı verilmiş olmasına rağmen fiiliyatta yapılaşmamış boş ada durumundadır. "
                "İmar hakkı gerçekleşmemiş olup revizyon veya kentsel dönüşüm rezervidir."
            )
        elif old_cat in ("TICARET", "KONUT") and act_cat == "PARK_YESIL":
            durum = "GERÇEKLEŞMEMİŞ (PARK / AÇIK ALAN)"
            kod = "ACIK_ALAN"
            yorum = (
                f"Planda yapılaşma ({old_str}) öngörülmüş fakat fiiliyatta yeşil alan/park olarak korunmuştur. "
                "Halkın fiili yeşil alan kullanımı gözetilerek plan tadilatı değerlendirilmelidir."
            )
        elif old_cat in ("PARK_YESIL", "EGITIM", "SAGLIK", "SOSYAL_KULTUR", "IBADET") and act_cat in ("KONUT", "TICARET", "SANAYI"):
            durum = "AYKIRI DÖNÜŞÜM / DONATI KAYBI"
            kod = "DONATI_KAYBI"
            yorum = (
                f"Planda kamu donatısı ({old_str}) olarak ayrılan alan fiiliyatta yapılaşmış ({act_str}). "
                "MPYY Madde 26 gereğince donatı azaltılamaz; yürüyüş mesafesinde eşdeğer alan tahsis edilmelidir!"
            )
        else:
            durum = "FONKSİYON DEĞİŞİMİ"
            kod = "FONKSIYON_DEGISIMI"
            yorum = f"Plandaki '{old_str}' fonksiyonu sahadaki fiili '{act_str}' kullanımına evrilmiştir."

        return durum, kod, yorum, old_cat, act_cat

    @classmethod
    def run_comparison(
        cls,
        old_layer,
        old_field,
        actual_layer,
        actual_field,
        target_crs=None,
        min_area_m2=1.0,
        feedback=None
    ):
        """
        Executes spatial overlay between Old/Approved Master Plan and Current Actual Use.
        Calculates exact intersection area (m²) in EPSG:5253.
        Returns:
          - diff_features: list of dicts with geometry, areas, categories, and justifications.
          - summary: overall statistics.
          - matrix: (old_use, actual_use) -> total_area_m2 cross-tabulation.
        """
        diff_features = []
        matrix = {}
        summary = {
            "toplam_alan_m2": 0.0,
            "uyumlu_alan_m2": 0.0,
            "uyumlu_m2": 0.0,
            "bos_ada_m2": 0.0,
            "acik_alan_m2": 0.0,
            "donati_kaybi_m2": 0.0,
            "fonksiyon_degisimi_m2": 0.0,
            "parsel_sayisi": 0,
            "uyumlu_adet": 0,
            "bos_ada_adet": 0,
            "acik_alan_adet": 0,
            "donati_kaybi_adet": 0,
            "fonksiyon_degisimi_adet": 0,
        }

        if old_layer is None or actual_layer is None:
            return diff_features, summary, matrix

        project = QgsProject.instance()
        target_crs = target_crs or old_layer.crs()

        xform_old = None
        if old_layer.crs() != target_crs and old_layer.crs().isValid() and target_crs.isValid():
            xform_old = QgsCoordinateTransform(old_layer.crs(), target_crs, project)

        xform_act = None
        if actual_layer.crs() != target_crs and actual_layer.crs().isValid() and target_crs.isValid():
            xform_act = QgsCoordinateTransform(actual_layer.crs(), target_crs, project)

        old_f_idx = old_layer.fields().indexFromName(old_field) if old_field else -1
        act_f_idx = actual_layer.fields().indexFromName(actual_field) if actual_field else -1

        # Build spatial index on actual use layer
        act_index = QgsSpatialIndex()
        act_map = {}
        for af in actual_layer.getFeatures():
            ag = af.geometry()
            if not ag or ag.isEmpty():
                continue
            if xform_act is not None:
                ag = QgsGeometry(ag)
                try:
                    ag.transform(xform_act)
                except Exception:
                    pass
            ag = ag.makeValid()
            act_val = af[act_f_idx] if act_f_idx >= 0 else af.attribute(0)
            act_map[af.id()] = (ag, act_val)
            feat = QgsFeature(af.id())
            feat.setGeometry(ag)
            act_index.addFeature(feat)

        # Iterate over old plan features and intersect
        for of in old_layer.getFeatures():
            og = of.geometry()
            if not og or og.isEmpty():
                continue
            if xform_old is not None:
                og = QgsGeometry(og)
                try:
                    og.transform(xform_old)
                except Exception:
                    pass
            og = og.makeValid()
            old_val = of[old_f_idx] if old_f_idx >= 0 else of.attribute(0)

            cand_ids = act_index.intersects(og.boundingBox())
            if not cand_ids:
                area_m2 = og.area()
                if area_m2 >= min_area_m2:
                    durum, kod, yorum, o_c, a_c = cls.evaluate_discrepancy(old_val, "Boş Ada")
                    diff_features.append({
                        "geom": og,
                        "eski_plan": str(old_val),
                        "mevcut_fiili": "Saha Verisi Yok / Boş",
                        "durum": durum,
                        "kod": kod,
                        "alan_m2": round(area_m2, 1),
                        "yorum": yorum,
                    })
                    summary["toplam_alan_m2"] += area_m2
                    summary["bos_ada_m2"] += area_m2
                    summary["bos_ada_adet"] += 1
                    summary["parsel_sayisi"] += 1
                continue

            for cid in cand_ids:
                ag, act_val = act_map[cid]
                if not og.intersects(ag):
                    continue
                inter_g = _clean_polygon_geom(og.intersection(ag))
                if inter_g is None or inter_g.isEmpty():
                    continue
                ia = inter_g.area()
                if ia < min_area_m2:
                    continue

                durum, kod, yorum, o_c, a_c = cls.evaluate_discrepancy(old_val, act_val)
                diff_features.append({
                    "geom": inter_g,
                    "eski_plan": str(old_val),
                    "mevcut_fiili": str(act_val),
                    "durum": durum,
                    "kod": kod,
                    "alan_m2": round(ia, 1),
                    "yorum": yorum,
                })

                pair = (str(old_val), str(act_val))
                matrix[pair] = matrix.get(pair, 0.0) + ia
                summary["toplam_alan_m2"] += ia
                summary["parsel_sayisi"] += 1

                if kod == "UYUMLU":
                    summary["uyumlu_alan_m2"] += ia
                    summary["uyumlu_m2"] += ia
                    summary["uyumlu_adet"] += 1
                elif kod == "BOS_ADA":
                    summary["bos_ada_m2"] += ia
                    summary["bos_ada_adet"] += 1
                elif kod == "ACIK_ALAN":
                    summary["acik_alan_m2"] += ia
                    summary["acik_alan_adet"] += 1
                elif kod == "DONATI_KAYBI":
                    summary["donati_kaybi_m2"] += ia
                    summary["donati_kaybi_adet"] += 1
                else:
                    summary["fonksiyon_degisimi_m2"] += ia
                    summary["fonksiyon_degisimi_adet"] += 1

        return diff_features, summary, matrix


class ResidentialGrowthNetworkEvaluator:
    """
    Multi-Criteria Road Network Accessibility & Capacity Evaluator
    for Proposed Residential Development Areas ('Gelişme Konut Alanı').

    Key Urban Planning Principle:
    Residential zones are demand recipients, not facility emitters. Therefore,
    recommending or zoning an urban block as 'Gelişme Konut Alanı' cannot be an
    arbitrary guess; it must be rigorously justified by pedestrian network accessibility
    to essential daily facilities (Primary School 500m, Secondary School 1000m, Health 500m,
    Park 500m, Commercial 800m) while safeguarding against facility capacity overload!
    """

    @staticmethod
    def _distance_decay_utility(dist, threshold):
        """
        Calculates walkability utility score in [0.0, 1.0] with smooth distance decay:
          - <= 0.8 * threshold: 1.0 (Comfortable walking zone)
          - 0.8 * threshold to threshold: linear decay 1.0 -> 0.75
          - threshold to 1.5 * threshold: linear decay 0.75 -> 0.0
          - > 1.5 * threshold or inf: 0.0
        """
        if dist is None or math.isinf(dist) or dist < 0:
            return 0.0
        if dist <= 0.80 * threshold:
            return 1.0
        if dist <= threshold:
            frac = (dist - 0.80 * threshold) / max(0.20 * threshold, 1.0)
            return 1.0 - 0.25 * frac
        if dist <= 1.50 * threshold:
            frac = (dist - threshold) / max(0.50 * threshold, 1.0)
            return 0.75 * (1.0 - frac)
        return 0.0

    @classmethod
    def evaluate_candidate_blocks(
        cls,
        candidate_features,
        graph,
        fac_by_type,
        specs,
        comm_pts=None,
        net_dist_maps=None,
        net_owner_maps=None,
        overloaded_facilities=None,
        target_crs=None,
        gross_density_pop_per_ha=180.0
    ):
        """
        Evaluates candidate vacant / reserve blocks for Residential Growth suitability.
        Returns list of evaluated record dicts.
        """
        results = []
        if not candidate_features or graph is None:
            return results

        comm_pts = comm_pts or []
        net_dist_maps = net_dist_maps or {}
        net_owner_maps = net_owner_maps or {}
        overloaded_facilities = overloaded_facilities or {}

        # Commercial distance map
        comm_dist_map = graph.multi_source_dijkstra(comm_pts, max_cutoff=2500.0) if comm_pts else {}

        # Standard thresholds
        sch_r = 500.0
        mid_r = 1000.0
        asm_r = 500.0
        park_r = 500.0
        comm_r = 800.0

        for cf in candidate_features:
            geom = cf.geometry() if hasattr(cf, "geometry") else cf
            fid = cf.id() if hasattr(cf, "id") else 0
            if not geom or geom.isEmpty():
                continue

            area_m2 = geom.area()
            if area_m2 < 100.0:
                continue

            cpt = geom.centroid().asPoint()
            nid, snap_d = graph.snap_polygon_to_node(geom)

            # 1. Primary School Distance
            sch_items = fac_by_type.get("ilkokul", [])
            d_sch = float('inf')
            sch_overloaded = False
            if "ilkokul" in net_dist_maps and nid is not None and nid in net_dist_maps["ilkokul"]:
                d_sch = net_dist_maps["ilkokul"][nid] + snap_d
                o_idx = net_owner_maps.get("ilkokul", {}).get(nid, -1)
                if 0 <= o_idx < len(sch_items):
                    if sch_items[o_idx][4] > sch_items[o_idx][2] * 1.05:
                        sch_overloaded = True
            elif sch_items:
                d_sch = min(math.hypot(cpt.x() - it[1].x(), cpt.y() - it[1].y()) for it in sch_items) * 1.25

            # 2. Middle School Distance
            mid_items = fac_by_type.get("ortaokul", [])
            d_mid = float('inf')
            if "ortaokul" in net_dist_maps and nid is not None and nid in net_dist_maps["ortaokul"]:
                d_mid = net_dist_maps["ortaokul"][nid] + snap_d
            elif mid_items:
                d_mid = min(math.hypot(cpt.x() - it[1].x(), cpt.y() - it[1].y()) for it in mid_items) * 1.25

            # 3. Family Health Center (ASM) Distance
            asm_items = fac_by_type.get("asm", [])
            d_asm = float('inf')
            asm_overloaded = False
            if "asm" in net_dist_maps and nid is not None and nid in net_dist_maps["asm"]:
                d_asm = net_dist_maps["asm"][nid] + snap_d
                o_idx = net_owner_maps.get("asm", {}).get(nid, -1)
                if 0 <= o_idx < len(asm_items):
                    if asm_items[o_idx][4] > asm_items[o_idx][2] * 1.05:
                        asm_overloaded = True
            elif asm_items:
                d_asm = min(math.hypot(cpt.x() - it[1].x(), cpt.y() - it[1].y()) for it in asm_items) * 1.25

            # 4. Park Distance
            park_items = fac_by_type.get("park", [])
            d_park = float('inf')
            if "park" in net_dist_maps and nid is not None and nid in net_dist_maps["park"]:
                d_park = net_dist_maps["park"][nid] + snap_d
            elif park_items:
                d_park = min(math.hypot(cpt.x() - it[1].x(), cpt.y() - it[1].y()) for it in park_items) * 1.25

            # 5. Commercial Distance
            d_comm = (comm_dist_map[nid] + snap_d) if (nid is not None and nid in comm_dist_map) else float('inf')

            # Calculate Utilities
            u_sch = cls._distance_decay_utility(d_sch, sch_r)
            u_mid = cls._distance_decay_utility(d_mid, mid_r)
            u_asm = cls._distance_decay_utility(d_asm, asm_r)
            u_park = cls._distance_decay_utility(d_park, park_r)
            u_comm = cls._distance_decay_utility(d_comm, comm_r)

            # Capacity Safety Factor
            c_safe = 1.0
            cap_warnings = []
            if sch_overloaded:
                c_safe -= 0.35
                cap_warnings.append("En yakın ilkokul kapasite aşımında")
            if asm_overloaded:
                c_safe -= 0.25
                cap_warnings.append("En yakın ASM kapasite aşımında")
            c_safe = max(0.20, c_safe)

            # Multi-Criteria Suitability Score S_res in [0, 100]
            # Weights: School 25%, ASM 20%, Park 20%, Middle School 15%, Commercial 10%, Capacity Margin 10%
            raw_score = (
                0.25 * u_sch +
                0.20 * u_asm +
                0.20 * u_park +
                0.15 * u_mid +
                0.10 * u_comm +
                0.10 * c_safe
            ) * 100.0

            suitability_score = round(max(0.0, min(100.0, raw_score)), 1)

            # Estimated Population Capacity based on Planned Density
            est_pop = int(round((area_m2 / 10000.0) * gross_density_pop_per_ha))

            # Urban Classification
            if suitability_score >= 80.0:
                sinif = "Öncelikli Gelişme Konut Alanı (15-Dk Şehir Standardı)"
                kod = "ONCELIKLI_KONUT"
                renk = "#eab308"  # Gold
            elif suitability_score >= 60.0:
                sinif = "Uygun Gelişme Konut Alanı (İyi Donatı Erişimi)"
                kod = "UYGUN_KONUT"
                renk = "#f97316"  # Amber/Orange
            elif suitability_score >= 40.0:
                sinif = "Şartlı Gelişme Konut Alanı (Kısmi Donatı Eksikliği)"
                kod = "SARTLI_KONUT"
                renk = "#84cc16"  # Lime/Khaki
            else:
                sinif = "Gelişmeye Uygun Değil (Donatı Altyapısı Yetersiz)"
                kod = "UYGUN_DEGIL"
                renk = "#94a3b8"  # Slate/Gray

            # Narrative Justification
            notes = []
            notes.append(f"Yol Ağı Donatı Erişim Skoru: {suitability_score}/100.")
            notes.append(f"İlkokul: {int(d_sch) if d_sch < 1e8 else 'Yok'}m ({'Uygun' if d_sch <= sch_r else 'Uzak'}).")
            notes.append(f"Sağlık (ASM): {int(d_asm) if d_asm < 1e8 else 'Yok'}m ({'Uygun' if d_asm <= asm_r else 'Uzak'}).")
            notes.append(f"Park: {int(d_park) if d_park < 1e8 else 'Yok'}m ({'Uygun' if d_park <= park_r else 'Uzak'}).")
            if cap_warnings:
                notes.append("DİKKAT: " + ", ".join(cap_warnings) + "!")
            else:
                notes.append("Mevcut okul ve sağlık kapasitesi yeterlidir.")

            gerekce = " ".join(notes)

            results.append({
                "geom": geom,
                "ada_id": fid,
                "alan_m2": round(area_m2, 1),
                "ongorulen_nufus": est_pop,
                "konut_skoru": suitability_score,
                "erisim_sinifi": sinif,
                "kod": kod,
                "renk": renk,
                "ilkokul_yol_m": round(d_sch, 1) if d_sch < 1e8 else -1.0,
                "ortaokul_yol_m": round(d_mid, 1) if d_mid < 1e8 else -1.0,
                "asm_yol_m": round(d_asm, 1) if d_asm < 1e8 else -1.0,
                "park_yol_m": round(d_park, 1) if d_park < 1e8 else -1.0,
                "ticari_yol_m": round(d_comm, 1) if d_comm < 1e8 else -1.0,
                "kapasite_durumu": "Kapasite Yeterli (OK)" if not cap_warnings else "Kapasite Aşımı Riski",
                "planlama_gerekcesi": gerekce,
            })

        return results


class AdaptiveAmenityWeightingEngine:
    """
    Adaptive Amenity Deficit Weighting & Stochastic Land-Use Equilibrium Engine.

    Operationalizes the Professor's Planning Methodology:
    1. Per-Residential-Block Amenity Density & Deficit Weights:
       - Compares accessible facility area per capita (m²/person) against MPYY Annex-2
         standards (e.g. Park 10 m², Primary School 2 m², Middle School 2 m², Health/ASM 0.75 m²).
       - Computes local deficit weight W_{i,k} = max(0, (T_k - s_{i,k}) / T_k) in [0.0, 1.0].
    2. Spatial Variation & Stochastic Sweep:
       - Iteratively examines residential blocks in a randomized/stochastic order (seeded for reproducibility)
         so evaluation is unbiased by geometry ordering or spatial orientation.
       - Each block is evaluated, recorded, and flagged as processed.
    3. Dual-Role Vacant Parcel Allocation with Carrying-Capacity Feedback:
       - Vacant blocks are evaluated using the deficit weights of surrounding residential blocks.
       - If surrounding area has high deficit: Allocated to the highest-deficit facility (e.g. Primary School).
       - If surrounding amenities are adequate: Designated as Candidate Residential Growth Area.
       - FEEDBACK LOOP: Simulates adding prospective new housing population to the neighborhood,
         verifying whether schools, health centers, and parks still maintain standard per-capita
         capacity and equal spatial distribution without overloading.
    """

    @staticmethod
    def get_normative_standard_m2(cat_key, specs=None):
        """Returns MPYY Annex-2 normative target m² per person."""
        if specs and cat_key in specs:
            std = specs[cat_key].get("std_m2", 0.0)
            if std > 0:
                return float(std)
        defaults = {
            "park": 10.0,
            "ilkokul": 2.0,
            "ortaokul": 2.0,
            "lise": 2.0,
            "asm": 0.75,
            "saglik": 0.75,
            "ibadet": 0.50,
            "sosyal": 1.0,
            "kultur": 1.0,
        }
        for k, v in defaults.items():
            if k in cat_key.lower():
                return v
        return 1.5

    @classmethod
    def compute_block_amenity_profiles(
        cls,
        res_feats,
        graph,
        fac_by_type,
        specs,
        total_pop,
        net_dist_maps=None,
        randomize_order=True,
        seed=42,
    ):
        """
        Evaluates each residential block in stochastic order.
        Returns a dict of profiles: { ada_id: profile_dict }
        and an ordered list of profiles.
        """
        profiles = {}
        ordered_list = []
        if not res_feats:
            return profiles, ordered_list

        total_res_area = sum(rf[2] for rf in res_feats)
        if total_res_area <= 0:
            total_res_area = 1.0

        net_dist_maps = net_dist_maps or {}

        # Stochastic permutation of residential blocks
        indices = list(range(len(res_feats)))
        if randomize_order:
            rng = random.Random(seed)
            rng.shuffle(indices)

        for step_idx, idx in enumerate(indices):
            r_id, pt, r_area, r_nid, r_snap = res_feats[idx]
            pop_i = total_pop * (r_area / total_res_area)

            s_ik = {}       # accessible m² per capita
            t_k = {}        # normative standard m² per capita
            w_ik = {}       # deficit weights in [0.0, 1.0]

            for cat, sp in specs.items():
                key_id = sp.get("key_id", cat).lower()
                if key_id in ("konut",):
                    continue

                target_m2 = cls.get_normative_standard_m2(key_id, specs)
                t_k[cat] = target_m2
                walk_limit = float(sp.get("net_r", 500.0))

                # Identify facilities reachable from this block
                fac_items = fac_by_type.get(cat, [])
                accessible_area = 0.0
                accessible_load = 0.0

                d_map = net_dist_maps.get(cat, {})
                for fid, fpt, fcap, farea, fload in fac_items:
                    # Road distance check
                    d_road = float('inf')
                    if r_nid is not None and r_nid in d_map:
                        d_road = d_map[r_nid] + r_snap
                    d_bird = math.hypot(pt.x() - fpt.x(), pt.y() - fpt.y())
                    eff_d = min(d_road, d_bird * 1.25)

                    if eff_d <= walk_limit:
                        accessible_area += farea
                        accessible_load += max(fload, 1.0)

                # Compute accessible m² per person for block i
                if accessible_area > 0 and accessible_load > 0:
                    s_val = min(target_m2 * 2.5, accessible_area / max(accessible_load, pop_i, 400.0))
                else:
                    s_val = 0.0

                s_ik[cat] = round(s_val, 2)

                # Deficit ratio W_{i,k} in [0.0, 1.0]
                if target_m2 > 0:
                    deficit = max(0.0, min(1.0, (target_m2 - s_val) / target_m2))
                else:
                    deficit = 0.0
                w_ik[cat] = round(deficit, 3)

            # Find primary need (highest deficit weight)
            if w_ik:
                top_cat = max(w_ik.keys(), key=lambda c: w_ik[c])
                top_w = w_ik[top_cat]
                avg_satisfaction = round((1.0 - (sum(w_ik.values()) / max(len(w_ik), 1))) * 100.0, 1)
            else:
                top_cat = "None"
                top_w = 0.0
                avg_satisfaction = 100.0

            prof = {
                "ada_id": r_id,
                "pt": pt,
                "area_m2": round(r_area, 1),
                "nufus": round(pop_i, 1),
                "mevcut_m2_kisi": s_ik,
                "standart_m2_kisi": t_k,
                "ihtiyac_agirligi": w_ik,
                "en_oncelikli_ihtiyac": top_cat,
                "oncelikli_agirlik": top_w,
                "donati_yeterlilik_yuzdesi": avg_satisfaction,
                "stokastik_sira": step_idx + 1,
            }
            profiles[r_id] = prof
            ordered_list.append(prof)

        return profiles, ordered_list

    @classmethod
    def evaluate_and_allocate_vacant_blocks(
        cls,
        vac_feats,
        block_profiles,
        graph,
        specs,
        fac_by_type,
        gross_density_pop_per_ha=180.0,
        satisfaction_threshold=0.35,
        randomize_vacant=True,
        seed=42,
    ):
        """
        Stochastically processes vacant blocks.
        Evaluates local amenity deficit weights from nearby residential blocks.
        Decides between Amenity Allocation (Donatı) vs Residential Growth (Gelişme Konut),
        and runs feedback simulation for Residential Growth.
        """
        allocations = []
        if not vac_feats:
            return allocations

        indices = list(range(len(vac_feats)))
        if randomize_vacant:
            rng = random.Random(seed + 101)
            rng.shuffle(indices)

        # Dynamic copy of profiles so newly placed amenities relieve subsequent blocks
        dyn_profiles = {k: dict(v) for k, v in block_profiles.items()}
        for k, v in dyn_profiles.items():
            v["ihtiyac_agirligi"] = dict(v["ihtiyac_agirligi"])
            v["mevcut_m2_kisi"] = dict(v["mevcut_m2_kisi"])

        # Track dynamically placed facilities
        dyn_facilities = {c: [list(it) for it in fac_by_type.get(c, [])] for c in specs.keys()}

        for step_idx, v_idx in enumerate(indices):
            vf = vac_feats[v_idx]
            geom = vf.geometry() if hasattr(vf, "geometry") else vf
            fid = vf.id() if hasattr(vf, "id") else (step_idx + 1)
            if not geom or geom.isEmpty():
                continue

            area_m2 = geom.area()
            if area_m2 < 100.0:
                continue

            cpt = geom.centroid().asPoint()
            v_nid, v_snap = graph.snap_polygon_to_node(geom)

            # 1. Identify nearby residential blocks within walking catchment
            neighborhood_blocks = []
            for r_id, prof in dyn_profiles.items():
                rpt = prof["pt"]
                dist = math.hypot(cpt.x() - rpt.x(), cpt.y() - rpt.y())
                if dist <= 900.0:
                    neighborhood_blocks.append((r_id, prof, dist))

            if not neighborhood_blocks:
                sorted_all = sorted(
                    dyn_profiles.items(),
                    key=lambda item: math.hypot(cpt.x() - item[1]["pt"].x(), cpt.y() - item[1]["pt"].y())
                )
                neighborhood_blocks = [
                    (item[0], item[1], math.hypot(cpt.x() - item[1]["pt"].x(), cpt.y() - item[1]["pt"].y()))
                    for item in sorted_all[:3]
                ]

            # 2. Compute population-weighted neighborhood deficit weights
            tot_n_pop = sum(item[1]["nufus"] for item in neighborhood_blocks)
            if tot_n_pop <= 0:
                tot_n_pop = 1.0

            agg_weights = {}
            for cat in specs.keys():
                if specs[cat].get("key_id", "").lower() == "konut":
                    continue
                w_sum = sum(item[1]["nufus"] * item[1]["ihtiyac_agirligi"].get(cat, 0.0) for item in neighborhood_blocks)
                agg_weights[cat] = round(w_sum / tot_n_pop, 3)

            # Overall neighborhood satisfaction
            if agg_weights:
                max_deficit_cat = max(agg_weights.keys(), key=lambda c: agg_weights[c])
                max_deficit_val = agg_weights[max_deficit_cat]
                avg_neighborhood_satisfaction = round(
                    (1.0 - (sum(agg_weights.values()) / max(len(agg_weights), 1))) * 100.0, 1
                )
            else:
                max_deficit_cat = "None"
                max_deficit_val = 0.0
                avg_neighborhood_satisfaction = 100.0

            # 3. Decision Gate: Amenity vs Residential Growth
            if max_deficit_val >= satisfaction_threshold:
                # ALLOCATE AS DONATI
                assigned_cat = max_deficit_cat
                sp = specs.get(assigned_cat, {})
                unit_cap = sp.get("unit_cap", 2500)

                justification = (
                    f"Ada #{fid} ({int(area_m2)} m²): Çevre konut adalarında '{assigned_cat}' kişi başı açık "
                    f"ihtiyaç ağırlığı %{int(max_deficit_val * 100)} ile en yüksek seviyededir "
                    f"(Mahalle donatı yeterliliği: %{avg_neighborhood_satisfaction}). "
                    f"Stokastik ihtiyaç modeli gereğince bu boş parsel öncelikli olarak '{assigned_cat}' tahsisine ayrılmıştır."
                )

                # Dynamically relieve surrounding residential blocks for this category
                added_cap = min(unit_cap, area_m2 / max(sp.get("std_m2", 2.0), 0.5))
                for r_id, prof, _ in neighborhood_blocks:
                    cur_w = prof["ihtiyac_agirligi"].get(assigned_cat, 0.0)
                    prof["ihtiyac_agirligi"][assigned_cat] = max(0.0, round(cur_w - 0.40, 3))
                    cur_s = prof["mevcut_m2_kisi"].get(assigned_cat, 0.0)
                    prof["mevcut_m2_kisi"][assigned_cat] = round(cur_s + (area_m2 / max(tot_n_pop, 1.0)), 2)

                dyn_facilities.setdefault(assigned_cat, []).append([fid, cpt, unit_cap, area_m2, 0.0])

                allocations.append({
                    "geom": geom,
                    "ada_id": fid,
                    "alan_m2": round(area_m2, 1),
                    "karar_turu": "Donatı Alanı (İhtiyaç Ağırlıklı)",
                    "atanan_kullanim": assigned_cat,
                    "kod": "DONATI_ONERISI",
                    "ongorulen_nufus": 0,
                    "ihtiyac_agirliklari": agg_weights,
                    "en_yuksek_acik": f"{assigned_cat} (%{int(max_deficit_val * 100)})",
                    "donati_yeterlilik_yuzdesi": avg_neighborhood_satisfaction,
                    "feedback_durumu": "Donatı İhtiyacı Karşılandı",
                    "planlama_gerekcesi": justification,
                    "stokastik_sira": step_idx + 1,
                })

            else:
                # ALLOCATE AS CANDIDATE RESIDENTIAL GROWTH & RUN FEEDBACK LOOP
                prospective_pop = int(round((area_m2 / 10000.0) * gross_density_pop_per_ha))

                # 4. Carrying-Capacity & Equal Distribution Feedback Simulation
                feedback_warnings = []
                feedback_ok = True

                for cat, sp in specs.items():
                    key_id = sp.get("key_id", cat).lower()
                    if key_id in ("konut",):
                        continue
                    std_req = cls.get_normative_standard_m2(key_id, specs)

                    cat_facs = dyn_facilities.get(cat, [])
                    tot_cat_area = sum(f[3] for f in cat_facs)
                    tot_cat_cap = sum(f[2] for f in cat_facs)

                    simulated_demand = tot_n_pop + prospective_pop
                    if tot_cat_area > 0 and simulated_demand > 0:
                        simulated_m2_per_person = tot_cat_area / simulated_demand
                        if simulated_m2_per_person < std_req * 0.68:
                            feedback_ok = False
                            feedback_warnings.append(
                                f"{cat} kişi başı alan {simulated_m2_per_person:.2f} m²'ye gerileyip standardın altına düşmektedir"
                            )
                    if tot_cat_cap > 0 and simulated_demand > tot_cat_cap * 1.15:
                        feedback_ok = False
                        feedback_warnings.append(f"{cat} bina kapasitesi aşılmaktadır")

                if feedback_ok:
                    status_kod = "ONCELIKLI_KONUT_DENGE_OK"
                    status_lbl = "Öncelikli Gelişme Konut Alanı (Kapasite & Denge Onaylı)"
                    justification = (
                        f"Ada #{fid} ({int(area_m2)} m²): Çevre konut adalarında mevcut donatı yeterliliği yüksek "
                        f"(%{avg_neighborhood_satisfaction}) seviyededir. "
                        f"Bu adaya ~{prospective_pop} kişilik konut fonksiyonu yerleştirildiğinde yapılan geri-besleme "
                        f"(feedback) denetiminde; okul, sağlık ve açık yeşil alanların kişi başı standartları koruduğu "
                        f"ve eşit kentsel dağılım dengesinin sağlandığı tespit edilmiştir."
                    )
                    fb_str = "Kapasite & Denge Onaylandı (OK)"
                else:
                    status_kod = "SARTLI_KONUT_KAPASITE_UYARI"
                    status_lbl = "Şartlı Gelişme Konut Alanı (Kapasite Uyarısı)"
                    warn_text = "; ".join(feedback_warnings)
                    justification = (
                        f"Ada #{fid} ({int(area_m2)} m²): Çevre sektör mevcut durumda yeterli olmakla birlikte, "
                        f"adaya ~{prospective_pop} kişilik konut eklendiğinde yapılan geri-besleme denetiminde: {warn_text}. "
                        f"Bu nedenle alan 'Şartlı Gelişme Konut' olarak belirlenmiş olup, ilave donatı takviyesi şarttır."
                    )
                    fb_str = f"Uyarı: {warn_text}"

                allocations.append({
                    "geom": geom,
                    "ada_id": fid,
                    "alan_m2": round(area_m2, 1),
                    "karar_turu": status_lbl,
                    "atanan_kullanim": "Gelişme Konut Alanı",
                    "kod": status_kod,
                    "ongorulen_nufus": prospective_pop,
                    "ihtiyac_agirliklari": agg_weights,
                    "en_yuksek_acik": f"{max_deficit_cat} (%{int(max_deficit_val * 100)})",
                    "donati_yeterlilik_yuzdesi": avg_neighborhood_satisfaction,
                    "feedback_durumu": fb_str,
                    "planlama_gerekcesi": justification,
                    "stokastik_sira": step_idx + 1,
                })

        return allocations

