"""Small planar/spherical geometry helpers of the OSM pipeline (standard library only)."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

Point = Tuple[float, float]          # (lon, lat)
Ring = List[Point]

EARTH_R = 6_371_008.8


def haversine(a: Point, b: Point) -> float:
    """Great-circle distance in metres between two (lon, lat) points."""
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_R * math.asin(min(1.0, math.sqrt(h)))


def bbox(points: Iterable[Point]) -> Tuple[float, float, float, float]:
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def in_ring(p: Point, ring: Sequence[Point]) -> bool:
    """Even-odd rule point-in-polygon for one ring."""
    x, y = p
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


class Polygon:
    """Multipolygon: outer rings with holes (``[[outer, hole, …], …]``), bbox-accelerated containment."""

    def __init__(self, parts: List[List[Ring]]):
        self.parts = [p for p in parts if p and len(p[0]) >= 3]
        self._boxes = [bbox(p[0]) for p in self.parts]
        self.box = (min(b[0] for b in self._boxes), min(b[1] for b in self._boxes),
                    max(b[2] for b in self._boxes), max(b[3] for b in self._boxes)) if self._boxes else (0, 0, 0, 0)

    def contains(self, p: Point) -> bool:
        x, y = p
        x0, y0, x1, y1 = self.box
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return False
        for part, (a, b, c, d) in zip(self.parts, self._boxes):
            if a <= x <= c and b <= y <= d and in_ring(p, part[0]) and not any(in_ring(p, h) for h in part[1:]):
                return True
        return False

    def area_m2(self) -> float:
        """Approximate area (equirectangular projection at the polygon's mean latitude)."""
        lat0 = math.radians((self.box[1] + self.box[3]) / 2)
        kx, ky = math.cos(lat0) * math.pi / 180 * EARTH_R, math.pi / 180 * EARTH_R

        def ring_area(r):
            s = 0.0
            for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]):
                s += (x1 * kx) * (y2 * ky) - (x2 * kx) * (y1 * ky)
            return abs(s) / 2

        return sum(ring_area(p[0]) - sum(ring_area(h) for h in p[1:]) for p in self.parts)


def load_polygon(path) -> Polygon:
    """Polygon / MultiPolygon (Feature, FeatureCollection or bare geometry) of a GeoJSON file."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    geoms = []
    if doc.get("type") == "FeatureCollection":
        geoms = [f["geometry"] for f in doc["features"]]
    elif doc.get("type") == "Feature":
        geoms = [doc["geometry"]]
    else:
        geoms = [doc]
    parts: List[List[Ring]] = []
    for g in geoms:
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in polys:
            parts.append([[(float(x), float(y)) for x, y, *_ in ring] for ring in poly])
    return Polygon(parts)


def assemble_rings(ways: Sequence[List[Tuple[int, Point]]]) -> List[Ring]:
    """Join way node sequences (``[(node_id, (lon, lat)), …]``) into closed rings by matching end nodes.

    Ways that cannot be closed are dropped (incomplete relation in the extract).
    """
    pending = [list(w) for w in ways if len(w) >= 2]
    rings: List[Ring] = []
    while pending:
        cur = pending.pop(0)
        changed = True
        while cur[0][0] != cur[-1][0] and changed:
            changed = False
            for i, w in enumerate(pending):
                if w[0][0] == cur[-1][0]:
                    cur += w[1:]
                elif w[-1][0] == cur[-1][0]:
                    cur += w[::-1][1:]
                elif w[-1][0] == cur[0][0]:
                    cur = w[:-1] + cur
                elif w[0][0] == cur[0][0]:
                    cur = w[::-1][:-1] + cur
                else:
                    continue
                pending.pop(i)
                changed = True
                break
        if cur[0][0] == cur[-1][0] and len(cur) >= 4:
            rings.append([p for _, p in cur])
    return rings


def rings_to_polygon(outer: List[Ring], inner: List[Ring]) -> Optional[Polygon]:
    """Multipolygon from outer and inner rings (each hole goes to the first outer ring containing it)."""
    if not outer:
        return None
    parts = [[o] for o in outer]
    for h in inner:
        for part in parts:
            if in_ring(h[0], part[0]):
                part.append(h)
                break
    return Polygon(parts)


class GridIndex:
    """Bucket index of items with bounding boxes, for candidate lookup by point."""

    def __init__(self, cell_deg: float = 0.01):
        self.cell = cell_deg
        self.buckets: Dict[Tuple[int, int], List[int]] = {}

    def add(self, item: int, box: Tuple[float, float, float, float]) -> None:
        c = self.cell
        for i in range(int(math.floor(box[0] / c)), int(math.floor(box[2] / c)) + 1):
            for j in range(int(math.floor(box[1] / c)), int(math.floor(box[3] / c)) + 1):
                self.buckets.setdefault((i, j), []).append(item)

    def candidates(self, p: Point) -> List[int]:
        c = self.cell
        return self.buckets.get((int(math.floor(p[0] / c)), int(math.floor(p[1] / c))), [])
