"""OSM → road network pipeline (sprint 02, S02-1/S02-3): ``python -m kami.osm build hanoi``.

Build-time tool, not used by the engine: needs ``osmium`` (pyosmium), ``pyproj`` and ``h3``
(``pip install kami[osm]``); the network it writes is read by ``RoadNetwork`` / ``FileZoneSystem`` with the standard
library only. A build is described by a JSON config (``data/osm/<name>.json``): the dated source PBF and its sha256,
the area polygon, kept road classes, free-flow speeds, target CRS and zone systems. See
``docs/engine/19-osm-pipeline.md``.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

PIPELINE_VERSION = 1
CONFIG_DIR = Path(__file__).resolve().parents[2] / "data" / "osm"


def load_config(name_or_path: Union[str, Path]) -> Dict[str, Any]:
    """Build config by name (``data/osm/<name>.json``) or path; relative paths in it are resolved."""
    p = Path(name_or_path)
    if not p.suffix:
        p = CONFIG_DIR / f"{name_or_path}.json"
    cfg = json.loads(p.read_text(encoding="utf-8"))
    cfg["_dir"] = str(p.resolve().parent)
    cfg["_path"] = str(p.resolve())
    return cfg


def _resolve(cfg, rel: str) -> Path:
    q = Path(rel)
    return q if q.is_absolute() else Path(cfg["_dir"]) / q


def source_path(cfg) -> Path:
    src = cfg["source"]
    if src.get("path"):
        return _resolve(cfg, src["path"])
    return _resolve(cfg, src.get("cache_dir", "cache")) / src["file"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(cfg, log=print) -> Path:
    """Download the source PBF into the cache (if missing) and check its sha256."""
    path = source_path(cfg)
    src = cfg["source"]
    if not path.exists():
        if not src.get("url"):
            raise FileNotFoundError(f"source file {path} missing and no url in the config")
        import urllib.request

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        log(f"downloading {src['url']} → {path}")
        urllib.request.urlretrieve(src["url"], tmp)
        tmp.rename(path)
    want = src.get("sha256")
    got = sha256(path)
    if want and got != want:
        raise ValueError(f"{path}: sha256 {got} does not match the config ({want}); "
                         "the source changed — refusing to build a different network under the same version")
    return path


def build(cfg, data_root: Optional[Union[str, Path]] = None, log=print) -> Dict[str, Any]:
    """Run the pipeline; returns the manifest. Output: ``<data_root>/networks/<name>/`` and ``zones/<zone>/<name>/``."""
    from kami.network.road.network import resolve_data_root
    from kami.osm.extract import extract
    from kami.osm.geo import load_polygon
    from kami.osm.graph import build_graph
    from kami.osm.writer import write_manifest, write_network, write_zones
    from kami.osm.zones import admin_zones, h3_zones, zone_weights

    t0 = time.perf_counter()
    root = resolve_data_root(data_root)
    pbf = fetch(cfg, log)
    area = load_polygon(_resolve(cfg, cfg["area"]))
    zcfg = cfg.get("zones", {})
    admin = zcfg.get("admin")
    log(f"extract {pbf.name} …")
    data = extract(str(pbf), area, cfg["highway"], admin.get("admin_level") if admin else None)
    log(f"  {data.stats}")
    g = build_graph(data, area, cfg["speeds_kmh"])
    log(f"  graph: {g.stats}")
    name = cfg["name"]
    net_dir = root / "networks" / name
    files = write_network(net_dir, g, cfg["crs"])
    zones_out: Dict[str, Any] = {}
    if zcfg.get("h3"):
        h = zcfg["h3"]
        za = h3_zones(h["name"], g.lonlat, int(h["resolution"]))
        write_zones(root / "zones" / h["name"] / name, za,
                    zone_weights(za, g.lonlat, data.pois, int(h["resolution"])))
        zones_out[h["name"]] = {"kind": "h3", "resolution": int(h["resolution"]), "zones": len(za.zones)}
    if admin:
        za = admin_zones(admin["name"], g.lonlat, data.boundaries)
        if za is None:
            log("  no administrative boundary inside the area: admin zones skipped")
        else:
            write_zones(root / "zones" / admin["name"] / name, za, zone_weights(za, g.lonlat, data.pois))
            zones_out[admin["name"]] = {"kind": "admin", "admin_level": admin["admin_level"], "zones": len(za.zones),
                                        "nodes_outside_polygons": getattr(za, "outside", 0)}
    src = cfg["source"]
    manifest = {
        "name": name,
        "pipeline_version": PIPELINE_VERSION,
        "config": Path(cfg["_path"]).name,
        "source": {"url": src.get("url"), "file": pbf.name, "date": src.get("date"), "sha256": sha256(pbf),
                   "license": src.get("license", "© OpenStreetMap contributors, ODbL 1.0")},
        "area": {"file": cfg["area"], "bbox": [round(v, 5) for v in area.box],
                 "km2": round(area.area_m2() / 1e6, 1)},
        "crs": cfg["crs"],
        "highway": list(cfg["highway"]),
        "speeds_kmh": dict(cfg["speeds_kmh"]),
        "extract": data.stats,
        "graph": g.stats,
        "zones": zones_out,
        "files": files,
    }
    write_manifest(net_dir, manifest)
    log(f"wrote {net_dir} ({g.stats['nodes']} nodes, {g.stats['edges']} edges) in {time.perf_counter() - t0:.0f}s")
    return manifest
