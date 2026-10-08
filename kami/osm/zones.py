"""Zone systems of a built network (decision D8) and demand weights per zone (decision D15).

* H3 cells (``h3``, build-time only) at the configured resolution; zone ids are the cells sorted, numbered ``0..Z-1``;
* administrative areas (OSM ``boundary=administrative`` of one ``admin_level``; for Hà Nội level 6 = the wards after
  the 2025 reform), point-in-polygon. A node outside every polygon takes the zone of the nearest node that has one.

Every node gets exactly one zone. Zone weights count residential buildings, workplaces and other points of interest
falling in each zone (they feed the ``zonal`` demand source).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from kami.osm.extract import Boundary
from kami.osm.geo import GridIndex, Point

WEIGHT_KINDS = ("residential", "work", "poi")


class ZoneAssignment:
    """``zone_of[i]`` for every node, zone metadata rows and the zone → id mapping."""

    def __init__(self, name: str, zone_of: List[int], zones: List[Dict[str, object]]):
        self.name = name
        self.zone_of = zone_of
        self.zones = zones


def h3_zones(name: str, lonlat: Sequence[Point], resolution: int) -> ZoneAssignment:
    import h3

    to_cell = getattr(h3, "latlng_to_cell", None) or getattr(h3, "geo_to_h3")
    to_ll = getattr(h3, "cell_to_latlng", None) or getattr(h3, "h3_to_geo")
    cells = [to_cell(lat, lon, resolution) for lon, lat in lonlat]
    ids = {c: i for i, c in enumerate(sorted(set(cells)))}
    zones = []
    for c, i in sorted(ids.items(), key=lambda kv: kv[1]):
        lat, lon = to_ll(c)
        zones.append({"zone_id": i, "key": c, "name": c, "lon": round(lon, 7), "lat": round(lat, 7)})
    return ZoneAssignment(name, [ids[c] for c in cells], zones)


def admin_zones(name: str, lonlat: Sequence[Point], boundaries: Sequence[Boundary]) -> Optional[ZoneAssignment]:
    if not boundaries:
        return None
    index = GridIndex(0.01)
    for k, b in enumerate(boundaries):
        index.add(k, b.polygon.box)
    raw: List[Optional[int]] = []
    for p in lonlat:
        hit = None
        for k in index.candidates(p):
            if boundaries[k].polygon.contains(p):
                hit = k if hit is None else min(hit, k)
        raw.append(hit)
    used = sorted({k for k in raw if k is not None}, key=lambda k: boundaries[k].id)
    if not used:
        return None
    ids = {k: i for i, k in enumerate(used)}
    # nodes outside every polygon: nearest zoned node (bucket search in degrees, fine at city scale)
    zoned = [i for i, k in enumerate(raw) if k is not None]
    cell = 0.005
    buckets: Dict[Tuple[int, int], List[int]] = {}
    for i in zoned:
        lon, lat = lonlat[i]
        buckets.setdefault((int(lon // cell), int(lat // cell)), []).append(i)
    zone_of: List[int] = []
    outside = 0
    for i, k in enumerate(raw):
        if k is not None:
            zone_of.append(ids[k])
            continue
        outside += 1
        zone_of.append(ids[raw[_nearest(lonlat, buckets, cell, lonlat[i])]])
    zones = []
    for k in used:
        b = boundaries[k]
        x0, y0, x1, y1 = b.polygon.box
        zones.append({"zone_id": ids[k], "key": f"r{b.id}", "name": b.name, "lon": round((x0 + x1) / 2, 7),
                      "lat": round((y0 + y1) / 2, 7)})
    za = ZoneAssignment(name, zone_of, zones)
    za.outside = outside
    return za


def _nearest(lonlat, buckets, cell, p) -> int:
    cx, cy = int(p[0] // cell), int(p[1] // cell)
    kx = math.cos(math.radians(p[1]))
    best, best_d, r = None, float("inf"), 0
    while best is None or r <= 1 + int(math.sqrt(best_d) / cell):
        for i in range(cx - r, cx + r + 1):
            for j in range(cy - r, cy + r + 1):
                if max(abs(i - cx), abs(j - cy)) != r:
                    continue
                for n in buckets.get((i, j), ()):
                    q = lonlat[n]
                    d = ((q[0] - p[0]) * kx) ** 2 + (q[1] - p[1]) ** 2
                    if d < best_d or (d == best_d and n < best):
                        best, best_d = n, d
        r += 1
    return best


def zone_weights(za: ZoneAssignment, lonlat: Sequence[Point], pois: Sequence[Tuple[float, float, str]],
                 resolution: Optional[int] = None) -> List[Dict[str, object]]:
    """Counts per zone: nodes, residential buildings, workplaces, other points of interest.

    POIs go to the H3 cell they fall in (``resolution`` given) — or to the zone of the nearest network node.
    """
    counts = {z["zone_id"]: {"zone_id": z["zone_id"], "nodes": 0, **{k: 0 for k in WEIGHT_KINDS}} for z in za.zones}
    for z in za.zone_of:
        counts[z]["nodes"] += 1
    if resolution is not None:
        import h3

        to_cell = getattr(h3, "latlng_to_cell", None) or getattr(h3, "geo_to_h3")
        by_key = {z["key"]: z["zone_id"] for z in za.zones}
        for lon, lat, kind in pois:
            zid = by_key.get(to_cell(lat, lon, resolution))
            if zid is not None:
                counts[zid][kind] += 1
    else:
        cell = 0.005
        buckets: Dict[Tuple[int, int], List[int]] = {}
        for i, (lon, lat) in enumerate(lonlat):
            buckets.setdefault((int(lon // cell), int(lat // cell)), []).append(i)
        for lon, lat, kind in pois:
            counts[za.zone_of[_nearest(lonlat, buckets, cell, (lon, lat))]][kind] += 1
    return [counts[z["zone_id"]] for z in za.zones]
