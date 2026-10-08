"""Zone × hour congestion (sprint 02, S02-4, decision D9).

Replaces the city-wide ``hour_profile`` of ``TrafficLayer`` when configured. The travel time of an edge (road
network) or of a node's incoming edges (grid) is multiplied by::

    factor = 1 + (P_g(h) − 1) × s_class × s_vehicle

* ``g``: congestion group of the zone holding the edge's *end* node (``core`` / ``inner`` / ``outer`` by default,
  assigned by distance from a centre — Hoàn Kiếm for geo-referenced networks — or read from a ``zone,group`` file);
* ``P_g(h)``: 24 hourly factors of the group (``kind="zone_group"``), or ``P_z(h)`` read per zone from a
  ``zone,hour,factor`` file (``kind="file"``, e.g. calibrated from GPS);
* ``s_class``: scale of the edge's OSM road class (``edge_attributes.csv``; 1 when unknown or on a grid);
* ``s_vehicle``: ``congestion_scale`` of the vehicle group (motorbikes feel less congestion than cars).

All default numbers are **assumptions** for Hà Nội (no GPS calibration yet, see docs/engine/08-network-traffic.md).
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Hashable, List, Mapping, Optional, Sequence, Tuple

from kami.network.base import Network
from kami.network.zones import ZoneSystem

# Hoàn Kiếm lake (lon, lat): centre of the default ring groups on geo-referenced networks
HANOI_CENTER = (105.8522, 21.0287)

# Peak 7–9h and 16h30–19h; 1.0 = free flow. ``core`` peaks at ≈ 2.2 (assumption).
_CORE = [1.0, 1.0, 1.0, 1.0, 1.0, 1.05, 1.3, 1.9, 2.2, 1.7, 1.4, 1.4,
         1.45, 1.35, 1.35, 1.45, 1.7, 2.1, 2.2, 1.7, 1.4, 1.25, 1.1, 1.0]
DEFAULT_GROUP_PROFILES: Dict[str, List[float]] = {
    "core": _CORE,
    "inner": [round(1 + (p - 1) * 0.7, 3) for p in _CORE],
    "outer": [round(1 + (p - 1) * 0.4, 3) for p in _CORE],
}
DEFAULT_RING_RADII_M = (3000.0, 8000.0)         # core < 3 km ≤ inner < 8 km ≤ outer
DEFAULT_RING_GROUPS = ("core", "inner", "outer")
# Arterials congest fully, small streets / alleys less (assumption)
DEFAULT_ROAD_CLASS_SCALE: Dict[str, float] = {
    "motorway": 0.6, "trunk": 0.9, "primary": 1.0, "secondary": 1.0, "tertiary": 0.9,
    "unclassified": 0.7, "residential": 0.6, "living_street": 0.4,
}


@dataclass
class VehicleGroup:
    """Network behaviour of a vehicle group (sprint 02, S02-7).

    ``speed_factor``: free-flow speed relative to a car (travel time ÷ ``speed_factor``);
    ``congestion_scale``: share of the car congestion felt (``s_vehicle``).
    """

    speed_factor: float = 1.0
    congestion_scale: float = 1.0


# Used when a scenario declares ``vehicle_groups`` without parameters for a group (assumption)
DEFAULT_VEHICLE_GROUPS: Dict[str, VehicleGroup] = {
    "car": VehicleGroup(1.0, 1.0),
    "bike": VehicleGroup(0.9, 0.5),
}


def road_class_key(road_class: str) -> str:
    """``primary_link`` → ``primary``."""
    return road_class[:-5] if road_class.endswith("_link") else road_class


@dataclass
class CongestionModel:
    """Hourly congestion factor per zone; see the module docstring.

    :param kind: ``"zone_group"`` (profiles per zone group) or ``"file"`` (``zone,hour,factor`` file)
    :param profiles: ``{group: [24 factors]}`` (default ``DEFAULT_GROUP_PROFILES``)
    :param zone_groups: ``"ring"`` (distance bands from ``center``) or ``{zone: group}`` / a ``zone,group`` CSV path
    :param center: ring centre as ``(lon, lat)`` on networks with lon/lat (planar ``(x, y)`` otherwise) — default
        Hoàn Kiếm when the network covers it, else the centre of the network bounds
    :param ring_radii_m: band limits, one less than ``ring_groups``
    :param road_class_scale: ``s_class`` per road class (unknown classes: 1)
    :param file: ``zone,hour,factor`` CSV for ``kind="file"`` (missing zone/hour: factor 1)
    :param period_s: length of a congestion period (travel times are re-set at multiples of it)
    """

    kind: str = "zone_group"
    profiles: Dict[str, List[float]] = field(default_factory=lambda: {k: list(v) for k, v in
                                                                       DEFAULT_GROUP_PROFILES.items()})
    zone_groups: Any = "ring"
    center: Optional[Tuple[float, float]] = None
    ring_radii_m: Sequence[float] = DEFAULT_RING_RADII_M
    ring_groups: Sequence[str] = DEFAULT_RING_GROUPS
    road_class_scale: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_ROAD_CLASS_SCALE))
    file: Optional[str] = None
    period_s: float = 3600.0

    def __post_init__(self):
        if self.kind not in ("zone_group", "file"):
            raise ValueError(f"congestion kind must be zone_group | file, got {self.kind!r}")
        if len(self.ring_radii_m) != len(self.ring_groups) - 1:
            raise ValueError("ring_radii_m needs one value less than ring_groups")
        self._zones: Optional[ZoneSystem] = None
        self._group_of: Dict[Hashable, str] = {}
        self._zone_hour: Dict[Hashable, List[float]] = {}
        self._edge_cache: Dict[Tuple[int, float], List[float]] = {}
        self._edge_base: Optional[Tuple[List[Hashable], List[float]]] = None

    # ------------------------------------------------------------------ binding to a world
    def bind(self, network: Network, zones: ZoneSystem) -> "CongestionModel":
        """Resolve zone groups / zone factors for this network and zone system (called by ``TrafficLayer``)."""
        self._network, self._zones = network, zones
        self._edge_cache.clear()
        self._edge_base = None
        if self.kind == "file":
            self._zone_hour = _read_zone_hour(self.file, zones)
            return self
        groups = self.zone_groups
        if groups == "ring":
            self._group_of = self._ring_groups(network, zones)
        else:
            mapping = _read_zone_group(groups) if isinstance(groups, (str, Path)) else dict(groups)
            by_str = {str(k): v for k, v in mapping.items()}
            self._group_of = {z: by_str.get(str(z), self.ring_groups[-1]) for z in zones.zones()}
        unknown = sorted({g for g in self._group_of.values() if g not in self.profiles})
        if unknown:
            raise ValueError(f"congestion groups without a profile: {unknown}")
        return self

    def _ring_groups(self, network: Network, zones: ZoneSystem) -> Dict[Hashable, str]:
        cx, cy = self._center_xy(network)
        out = {}
        for z in zones.zones():
            zx, zy = zones.centers[z]
            r = math.hypot(zx - cx, zy - cy)
            k = sum(1 for lim in self.ring_radii_m if r >= lim)
            out[z] = self.ring_groups[k]
        return out

    def _center_xy(self, network: Network) -> Tuple[float, float]:
        center = self.center
        if center is None and _covers(network, *HANOI_CENTER):
            center = HANOI_CENTER
        if center is not None and hasattr(network, "node_at_lonlat"):
            return network.coords(network.node_at_lonlat(*center))
        if center is not None:
            return float(center[0]), float(center[1])     # planar coordinates on networks without lon/lat
        x0, y0, x1, y1 = network.bounds()
        return (x0 + x1) / 2, (y0 + y1) / 2

    # ------------------------------------------------------------------ queries
    def hour(self, t: float) -> int:
        """Hour of day whose factors apply in the period containing ``t``."""
        start = math.floor(t / self.period_s) * self.period_s
        return int(start // 3600) % 24

    def zone_group(self, zone: Hashable) -> Optional[str]:
        return self._group_of.get(zone)

    def zone_factor(self, zone: Hashable, hour: int) -> float:
        """``P(h)`` of a zone."""
        if self.kind == "file":
            prof = self._zone_hour.get(zone)
            return prof[hour] if prof else 1.0
        return self.profiles[self._group_of[zone]][hour]

    def node_factor(self, node: int, hour: int, vehicle_scale: float = 1.0) -> float:
        """Multiplier of the edges entering ``node`` (no road class: grid networks)."""
        p = self.zone_factor(self._zones.zone_of(node), hour)
        return 1.0 + (p - 1.0) * vehicle_scale

    def edge_factors(self, hour: int, vehicle_scale: float = 1.0) -> List[float]:
        """Multiplier per edge of ``network.edge_list()`` (cached per hour and vehicle scale)."""
        key = (hour, vehicle_scale)
        hit = self._edge_cache.get(key)
        if hit is not None:
            return hit
        if self._edge_base is None:
            net, zones = self._network, self._zones
            classes = net.edge_road_class() if hasattr(net, "edge_road_class") else None
            ends = [b for _, b in net.edge_list()]
            ezones = [zones.zone_of(b) for b in ends]
            scale = self.road_class_scale
            cls_scale = ([scale.get(road_class_key(c), 1.0) for c in classes] if classes is not None
                         else [1.0] * len(ends))
            self._edge_base = (ezones, cls_scale)
        ezones, cls_scale = self._edge_base
        zp = {z: self.zone_factor(z, hour) - 1.0 for z in set(ezones)}
        out = [1.0 + zp[z] * c * vehicle_scale for z, c in zip(ezones, cls_scale)]
        if len(self._edge_cache) > 64:
            self._edge_cache.clear()
        self._edge_cache[key] = out
        return out

    def summary(self) -> Dict[str, Any]:
        """Zones per group (for logs and docs)."""
        counts: Dict[str, int] = {}
        for g in self._group_of.values():
            counts[g] = counts.get(g, 0) + 1
        return {"kind": self.kind, "period_s": self.period_s, "zones_per_group": counts}


def _covers(network: Network, lon: float, lat: float) -> bool:
    """True if the network has lon/lat columns and the point lies in their bounding box."""
    g = getattr(network, "graph", None)
    lons, lats = getattr(g, "lons", None), getattr(g, "lats", None)
    return bool(lons) and min(lons) <= lon <= max(lons) and min(lats) <= lat <= max(lats)


def build_congestion(spec: Any) -> CongestionModel:
    """``CongestionModel`` from a model or a dict of its fields (``TrafficLayer(congestion=...)``)."""
    if isinstance(spec, CongestionModel):
        return spec
    if isinstance(spec, Mapping):
        kw = dict(spec)
        if kw.get("center") is not None:
            c = kw["center"]
            kw["center"] = (float(c["lon"]), float(c["lat"])) if isinstance(c, Mapping) else tuple(c)
        if "profiles" in kw and kw["profiles"] is not None:
            kw["profiles"] = {k: list(v) for k, v in kw["profiles"].items()}
        if kw.get("road_class_scale") is not None:
            kw["road_class_scale"] = dict(DEFAULT_ROAD_CLASS_SCALE, **kw["road_class_scale"])
        return CongestionModel(**{k: v for k, v in kw.items() if v is not None})
    raise TypeError(f"congestion must be a CongestionModel or a dict, got {type(spec).__name__}")


def _zone_key(text: str, zones: ZoneSystem) -> Hashable:
    known = {str(z): z for z in zones.zones()}
    return known.get(text.strip(), text.strip())


def _read_zone_hour(path, zones: ZoneSystem) -> Dict[Hashable, List[float]]:
    if path is None:
        raise ValueError("congestion kind 'file' needs file=<zone,hour,factor CSV>")
    out: Dict[Hashable, List[float]] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            z = _zone_key(row["zone"], zones)
            out.setdefault(z, [1.0] * 24)[int(row["hour"]) % 24] = float(row["factor"])
    return out


def _read_zone_group(path) -> Dict[str, str]:
    with open(path, newline="") as f:
        return {row["zone"].strip(): row["group"].strip() for row in csv.DictReader(f)}
