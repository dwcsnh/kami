"""Read the parts of an OSM PBF file the pipeline needs (``pyosmium``; build-time only).

Two passes over the file:

1. highway ways (kept classes, motor-vehicle access), buildings and points of interest around the area, and the
   administrative boundary relations of the configured ``admin_level`` (members only — relations come last in a PBF);
2. geometry of the boundary member ways near the area.

Everything outside the area's bounding box (plus a margin) is skipped; clipping to the polygon happens in
``kami.osm.graph``. Results are sorted by OSM id so the output does not depend on the file's object order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from kami.osm.geo import Point, Polygon, assemble_rings, rings_to_polygon

WAY_TAGS = ("highway", "oneway", "junction", "maxspeed", "access", "motor_vehicle", "motorcar", "motorcycle",
            "name", "area", "lanes")
NO = ("no", "private", "agricultural", "forestry", "delivery", "discouraged")

RESIDENTIAL_BUILDINGS = {"yes", "house", "residential", "apartments", "detached", "terrace", "dormitory",
                         "semidetached_house", "bungalow", "hut"}
WORK_BUILDINGS = {"office", "commercial", "retail", "industrial", "warehouse", "school", "university", "college",
                  "hospital", "government", "public", "civic", "kindergarten", "hotel", "supermarket", "factory"}
WORK_AMENITIES = {"school", "university", "college", "hospital", "clinic", "bank", "townhall", "courthouse",
                  "kindergarten", "police", "post_office"}


@dataclass
class OsmWay:
    id: int
    tags: Dict[str, str]
    refs: List[int]


@dataclass
class Boundary:
    id: int
    name: str
    admin_level: str
    polygon: Polygon


@dataclass
class OsmData:
    ways: List[OsmWay] = field(default_factory=list)
    node_ll: Dict[int, Point] = field(default_factory=dict)
    boundaries: List[Boundary] = field(default_factory=list)
    pois: List[Tuple[float, float, str]] = field(default_factory=list)   # (lon, lat, residential|work|poi)
    stats: Dict[str, int] = field(default_factory=dict)


def motor_access(tags: Dict[str, str]) -> Tuple[bool, bool]:
    """(car allowed, motorbike allowed) from OSM access tags (decision D7): the most specific tag wins."""
    car = bike = tags.get("access") not in NO
    if "motor_vehicle" in tags:
        car = bike = tags["motor_vehicle"] not in NO
    if "motorcar" in tags:
        car = tags["motorcar"] not in NO
    if "motorcycle" in tags:
        bike = tags["motorcycle"] not in NO
    return car, bike


def poi_kind(tags) -> Optional[str]:
    b = tags.get("building")
    if tags.get("office") is not None or tags.get("amenity") in WORK_AMENITIES or b in WORK_BUILDINGS:
        return "work"
    if tags.get("amenity") is not None or tags.get("shop") is not None:
        return "poi"
    if b in RESIDENTIAL_BUILDINGS:
        return "residential"
    return None


def extract(pbf: str, area: Polygon, highway: Sequence[str], admin_level: Optional[str],
            margin_deg: float = 0.02, boundary_margin_deg: float = 0.12) -> OsmData:
    import osmium

    keep = set(highway)
    x0, y0, x1, y1 = area.box
    bx0, by0, bx1, by1 = x0 - margin_deg, y0 - margin_deg, x1 + margin_deg, y1 + margin_deg
    data = OsmData()
    stats = data.stats
    rel_members: Dict[int, Tuple[str, List[Tuple[int, str]]]] = {}
    ways: List[OsmWay] = []
    node_ll: Dict[int, Point] = {}
    pois: List[Tuple[int, float, float, str]] = []

    fp = (osmium.FileProcessor(pbf).with_locations()
          .with_filter(osmium.filter.KeyFilter("highway", "building", "amenity", "shop", "office", "boundary")))
    for o in fp:
        if o.is_way():
            tags = o.tags
            hw = tags.get("highway")
            if hw is not None:
                if hw not in keep or tags.get("area") == "yes":
                    continue
                pts = [(n.ref, n.lon, n.lat) for n in o.nodes]
                if not any(bx0 <= lon <= bx1 and by0 <= lat <= by1 for _, lon, lat in pts):
                    continue
                t = {k: tags[k] for k in WAY_TAGS if k in tags}
                car, bike = motor_access(t)
                if not (car or bike):
                    stats["ways_no_motor_access"] = stats.get("ways_no_motor_access", 0) + 1
                    continue
                ways.append(OsmWay(o.id, t, [r for r, _, _ in pts]))
                for r, lon, lat in pts:
                    node_ll[r] = (lon, lat)
                continue
            kind = poi_kind(tags)
            if kind is None:
                continue
            nodes = o.nodes
            if len(nodes) == 0:
                continue
            lon = sum(n.lon for n in nodes) / len(nodes)
            lat = sum(n.lat for n in nodes) / len(nodes)
            if x0 <= lon <= x1 and y0 <= lat <= y1:
                pois.append((o.id * 4 + 1, lon, lat, kind))
        elif o.is_relation():
            tags = o.tags
            if (admin_level is not None and tags.get("boundary") == "administrative"
                    and tags.get("admin_level") == admin_level and tags.get("name")):
                rel_members[o.id] = (tags.get("name"), [(m.ref, m.role) for m in o.members if m.type == "w"])
        else:
            kind = poi_kind(o.tags)
            if kind is not None and x0 <= o.lon <= x1 and y0 <= o.lat <= y1:
                pois.append((o.id * 4, o.lon, o.lat, kind))
    ways.sort(key=lambda w: w.id)
    pois.sort()
    data.ways, data.node_ll = ways, node_ll
    data.pois = [(lon, lat, k) for _, lon, lat, k in pois]
    stats.update(highway_ways=len(ways), pois=len(pois), boundary_relations=len(rel_members))

    if rel_members:
        need = {ref for _, members in rel_members.values() for ref, _ in members}
        geom: Dict[int, List[Tuple[int, Point]]] = {}
        cx0, cy0 = x0 - boundary_margin_deg, y0 - boundary_margin_deg
        cx1, cy1 = x1 + boundary_margin_deg, y1 + boundary_margin_deg
        fp = (osmium.FileProcessor(pbf).with_locations()
              .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
              .with_filter(osmium.filter.IdFilter(need)))
        for w in fp:
            pts = [(n.ref, (n.lon, n.lat)) for n in w.nodes]
            if any(cx0 <= p[0] <= cx1 and cy0 <= p[1] <= cy1 for _, p in pts):
                geom[w.id] = pts
        for rid in sorted(rel_members):
            name, members = rel_members[rid]
            if not any(ref in geom for ref, _ in members):
                continue
            outer = assemble_rings([geom[r] for r, role in members if r in geom and role != "inner"])
            inner = assemble_rings([geom[r] for r, role in members if r in geom and role == "inner"])
            poly = rings_to_polygon(outer, inner)
            if poly is None or not _boxes_overlap(poly.box, area.box):
                continue
            data.boundaries.append(Boundary(rid, name, admin_level, poly))
        stats["boundaries"] = len(data.boundaries)
    return data


def _boxes_overlap(a, b) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]
