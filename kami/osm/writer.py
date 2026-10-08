"""Write a built network in the FleetPy layout + kami extension files, zone systems and the manifest.

Numbers are written with fixed precision so two builds from the same input give byte-identical files.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from kami.osm.graph import RoadGraphData
from kami.osm.zones import WEIGHT_KINDS, ZoneAssignment


def _writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "w", newline="")
    return f, csv.writer(f, lineterminator="\n")


def project(lonlat, crs: str):
    from pyproj import Transformer

    tr = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    lons, lats = zip(*lonlat)
    xs, ys = tr.transform(lons, lats)
    return list(zip(xs, ys))


def write_network(net_dir: Path, g: RoadGraphData, crs: str) -> Dict[str, str]:
    base = net_dir / "base"
    xy = project(g.lonlat, crs)
    f, w = _writer(base / "nodes.csv")
    with f:
        w.writerow(["node_index", "is_stop_only", "pos_x", "pos_y", "lon", "lat", "osm_id"])
        for i, ((x, y), (lon, lat), osm) in enumerate(zip(xy, g.lonlat, g.nodes)):
            w.writerow([i, "False", f"{x:.3f}", f"{y:.3f}", f"{lon:.7f}", f"{lat:.7f}", osm])
    f, w = _writer(base / "edges.csv")
    with f:
        w.writerow(["from_node", "to_node", "distance", "travel_time", "source_edge_id"])
        for e in g.edges:
            w.writerow([e.a, e.b, f"{e.length:.3f}", f"{e.tt:.4f}", e.way])
    f, w = _writer(base / "edge_attributes.csv")
    with f:
        w.writerow(["from_node", "to_node", "road_class", "allow_car", "allow_bike", "speed_kmh", "maxspeed_tag"])
        for e in g.edges:
            w.writerow([e.a, e.b, e.road_class, int(e.car), int(e.bike), f"{e.speed_kmh:g}", int(e.maxspeed)])
    f, w = _writer(base / "edge_geometry.csv")
    with f:
        w.writerow(["from_node", "to_node", "lons", "lats"])
        for e in g.edges:
            w.writerow([e.a, e.b, ";".join(f"{p[0]:.7f}" for p in e.geom), ";".join(f"{p[1]:.7f}" for p in e.geom)])
    (base / "crs.info").write_text(crs + "\n")
    return {p.name: str(p.relative_to(net_dir)) for p in sorted(base.iterdir())}


def write_zones(zone_dir: Path, za: ZoneAssignment, weights: Optional[List[Dict[str, Any]]]) -> None:
    f, w = _writer(zone_dir / "node_zone_info.csv")
    with f:
        w.writerow(["node_index", "zone_id", "is_centroid"])
        for i, z in enumerate(za.zone_of):
            w.writerow([i, z, 0])
    f, w = _writer(zone_dir / "zone_definitions.csv")
    with f:
        w.writerow(["zone_id", "key", "name", "lon", "lat"])
        for z in za.zones:
            w.writerow([z["zone_id"], z["key"], z["name"], f"{z['lon']:.7f}", f"{z['lat']:.7f}"])
    if weights is not None:
        f, w = _writer(zone_dir / "zone_weights.csv")
        with f:
            w.writerow(["zone_id", "nodes", *WEIGHT_KINDS])
            for row in weights:
                w.writerow([row["zone_id"], row["nodes"], *(row[k] for k in WEIGHT_KINDS)])


def write_manifest(net_dir: Path, manifest: Dict[str, Any]) -> Path:
    path = net_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return path
