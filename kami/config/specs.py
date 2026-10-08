"""Declarative specs (sprint 01, S01-1): everything a user configures is data, not Python code.

Each spec is a dataclass with ``from_dict`` / ``to_dict`` (JSON-compatible) and is
validated field by field; invalid documents raise one ``SpecError`` listing every
wrong field by its dotted path. Where a spec may live in the database, a
``Ref`` (``{"ref": <id or name>}``) can stand in its place; ``Repository.resolve``
replaces references by their content before a run (NFR-4).

Units follow the engine: seconds, metres, VND.
"""
from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from kami.config.validate import (Errors, SpecError, check_value, dataclass_overrides, default_kind, join, suggest,
                                  unknown_keys)

SCHEMA_VERSION = 1


def f(default=None, *, required: bool = False, typ=None, factory: Optional[Callable] = None, parse=None,
      spec=None, list_of=None, nullable: bool = False, ge=None, gt=None, le=None, choices=None, key=None,
      omit_none: bool = False):
    """Spec field. Every field has a Python default; ``required`` means it must appear in the document."""
    md = dict(required=required, typ=typ, parse=parse, spec=spec, list_of=list_of, nullable=nullable, ge=ge, gt=gt,
              le=le, choices=choices, key=key, omit_none=omit_none)
    if factory is not None:
        return field(default_factory=factory, metadata=md)
    return field(default=default, metadata=md)


def _dump(v):
    if isinstance(v, Spec):
        return v.to_dict()
    if isinstance(v, (list, tuple)):
        return [_dump(x) for x in v]
    if isinstance(v, dict):
        return {k: _dump(x) for k, x in v.items()}
    return v


class Spec:
    """Base of every spec dataclass: generic validation and (de)serialisation."""

    @classmethod
    def parse(cls, d: Any, path: str, errs: Errors):
        if not isinstance(d, dict):
            errs.add(path, f"sai kiểu: cần object, nhận {type(d).__name__}")
            return cls()
        keys = {fl.metadata.get("key") or fl.name: fl for fl in fields(cls)}
        unknown_keys(d, keys, path, errs)
        kw = {}
        for key, fl in keys.items():
            md = fl.metadata
            p = join(path, key)
            if key not in d:
                if md.get("required"):
                    errs.add(p, "thiếu trường bắt buộc")
                continue
            v = d[key]
            if v is None:
                if md.get("nullable"):
                    kw[fl.name] = None
                else:
                    errs.add(p, "không được để null")
                continue
            if md.get("parse"):
                kw[fl.name] = md["parse"](v, p, errs)
            elif md.get("spec"):
                kw[fl.name] = md["spec"].parse(v, p, errs)
            elif md.get("list_of"):
                if check_value(v, p, errs, list):
                    item = md["list_of"]
                    kw[fl.name] = [item(x, join(p, i), errs) if not isinstance(item, type) else item.parse(x, join(p, i), errs)
                                   for i, x in enumerate(v)]
            elif check_value(v, p, errs, md.get("typ"), ge=md.get("ge"), gt=md.get("gt"), le=md.get("le"),
                             choices=md.get("choices")):
                kw[fl.name] = v
        obj = cls(**kw)
        obj.check(path, errs)
        return obj

    def check(self, path: str, errs: Errors) -> None:
        """Cross-field checks (override)."""

    @classmethod
    def from_dict(cls, d: Any, path: str = ""):
        errs = Errors()
        obj = cls.parse(d, path, errs)
        errs.check()
        return obj

    def to_dict(self) -> Dict[str, Any]:
        out = {}
        for fl in fields(self):
            v = getattr(self, fl.name)
            if v is None and fl.metadata.get("omit_none"):
                continue
            out[fl.metadata.get("key") or fl.name] = _dump(v)
        return out

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# =========================================================================== references
@dataclass
class Ref(Spec):
    """Reference to an entity stored in the database: ``{"ref": 3}`` or ``{"ref": "fleet_a", "version": 2}``."""

    ref: Union[int, str] = f(required=True, typ=(int, str))
    version: Optional[int] = f(typ=int, nullable=True, ge=1, omit_none=True)


def is_ref(d: Any) -> bool:
    return isinstance(d, dict) and "ref" in d


def ref_or(spec_cls):
    """Parser accepting either a ``Ref`` or an inline ``spec_cls`` document."""

    def parse(d, path, errs):
        return Ref.parse(d, path, errs) if is_ref(d) else spec_cls.parse(d, path, errs)

    return parse


def union(kinds: Dict[str, type], default: Optional[str] = None):
    """Parser for a ``{"kind": ...}``-discriminated union of spec classes."""

    def parse(d, path, errs):
        if not isinstance(d, dict):
            errs.add(path, f"sai kiểu: cần object, nhận {type(d).__name__}")
            return kinds[default]() if default else None
        kind = d.get("kind", default)
        if kind not in kinds:
            errs.add(join(path, "kind"), ("thiếu trường bắt buộc" if kind is None else f"giá trị {kind!r} không hợp lệ")
                     + suggest(kind or "", kinds))
            return kinds[default]() if default else None
        return kinds[kind].parse(d, path, errs)

    return parse


# =========================================================================== network & zones
@dataclass
class GridNetworkSpec(Spec):
    """Synthetic Manhattan grid (``GridNetwork``)."""

    kind: str = f("grid", choices=("grid",))
    width_m: float = f(8000.0, typ=float, gt=0)
    height_m: float = f(8000.0, typ=float, gt=0)
    spacing_m: float = f(250.0, typ=float, gt=0)
    speed_kmh: float = f(25.0, typ=float, gt=0)


@dataclass
class RoadNetworkSpec(Spec):
    """Real road network (``RoadNetwork``): a name under ``<data_root>/networks`` or a folder path."""

    kind: str = f("road", choices=("road",))
    name: str = f("example_network", typ=str)
    data_root: Optional[str] = f(typ=str, nullable=True)
    dynamics_file: Optional[str] = f(typ=str, nullable=True)
    scenario_time: Optional[int] = f(typ=int, nullable=True)
    backend: str = f("auto", choices=("auto", "cpp", "python"))


NetworkSpec = Union[GridNetworkSpec, RoadNetworkSpec]
parse_network = union({"grid": GridNetworkSpec, "road": RoadNetworkSpec}, default="grid")


@dataclass
class SquareZoneSpec(Spec):
    kind: str = f("square", choices=("square",))
    cell_m: float = f(1000.0, typ=float, gt=0)


@dataclass
class H3ZoneSpec(Spec):
    kind: str = f("h3", choices=("h3",))
    resolution: int = f(8, typ=int, ge=0, le=15)


@dataclass
class FileZoneSpec(Spec):
    """Zones from ``node_zone_info.csv`` (name under ``<data_root>/zones`` or file path)."""

    kind: str = f("file", choices=("file",))
    name: str = f("example_zones", typ=str)
    neighbor_radius_m: float = f(1500.0, typ=float, gt=0)


ZoneSpec = Union[SquareZoneSpec, H3ZoneSpec, FileZoneSpec]
parse_zones = union({"square": SquareZoneSpec, "h3": H3ZoneSpec, "file": FileZoneSpec}, default="square")


def _profiles(v, path, errs):
    if not check_value(v, path, errs, dict):
        return None
    return {k: _floats(x, join(path, k), errs, n=24) for k, x in v.items()}


def _zone_groups(v, path, errs):
    if isinstance(v, str):
        check_value(v, path, errs, str, choices=("ring",))
        return v
    if not check_value(v, path, errs, dict):
        return "ring"
    for k, x in v.items():
        check_value(x, join(path, k), errs, str)
    return {str(k): x for k, x in v.items()}


def _lonlat(v, path, errs):
    if not check_value(v, path, errs, dict):
        return None
    unknown_keys(v, ("lon", "lat"), path, errs)
    ok = True
    for k, lo, hi in (("lon", -180, 180), ("lat", -90, 90)):
        if k not in v:
            errs.add(join(path, k), "thiếu trường bắt buộc")
            ok = False
        else:
            ok = check_value(v[k], join(path, k), errs, float, ge=lo, le=hi) and ok
    return {"lon": float(v["lon"]), "lat": float(v["lat"])} if ok else None


@dataclass
class CongestionSpec(Spec):
    """Zone × hour congestion (``kami.congestion.CongestionModel``, sprint 02). Every field is optional.

    ``kind="zone_group"``: 24 hourly factors per zone group (``profiles``; default Hà Nội profiles core/inner/outer),
    zones assigned to groups by distance bands from ``center`` (``zone_groups="ring"``) or explicitly
    (``zone_groups={zone: group}`` / ``zone_groups_file`` CSV ``zone,group``). ``kind="file"``: CSV
    ``zone,hour,factor`` in ``file``. Files: path as given, or relative to the network's data root.
    """

    kind: str = f("zone_group", choices=("zone_group", "file"))
    period_s: float = f(3600.0, typ=float, gt=0)
    profiles: Optional[Dict[str, List[float]]] = f(nullable=True, parse=_profiles, omit_none=True)
    zone_groups: Any = f("ring", parse=_zone_groups)
    zone_groups_file: Optional[str] = f(typ=str, nullable=True, omit_none=True)
    center: Optional[Dict[str, float]] = f(nullable=True, parse=_lonlat, omit_none=True)
    ring_radii_m: Optional[List[float]] = f(nullable=True, parse=lambda v, p, e: _floats(v, p, e), omit_none=True)
    ring_groups: Optional[List[str]] = f(nullable=True, parse=lambda v, p, e: _strs(v, p, e, n=None),
                                         omit_none=True)
    road_class_scale: Optional[Dict[str, float]] = f(nullable=True, parse=lambda v, p, e: _float_map(v, p, e),
                                                     omit_none=True)
    file: Optional[str] = f(typ=str, nullable=True, omit_none=True)

    def check(self, path, errs):
        if self.kind == "file" and not self.file:
            errs.add(join(path, "file"), "kind 'file' cần file CSV zone,hour,factor")
        groups = self.ring_groups or ["core", "inner", "outer"]
        if self.ring_radii_m is not None and len(self.ring_radii_m) != len(groups) - 1:
            errs.add(join(path, "ring_radii_m"), f"cần {len(groups) - 1} bán kính cho {len(groups)} nhóm")
        if self.kind == "zone_group" and self.profiles is not None:
            from kami.congestion import DEFAULT_GROUP_PROFILES

            names = set(groups) if self.zone_groups == "ring" and not self.zone_groups_file else set()
            if isinstance(self.zone_groups, dict):
                names = set(self.zone_groups.values())
            missing = sorted(g for g in names if g not in self.profiles and g not in DEFAULT_GROUP_PROFILES)
            if missing:
                errs.add(join(path, "profiles"), f"thiếu profile cho nhóm {missing}")

    def model_kwargs(self, resolve=lambda p: p) -> Dict[str, Any]:
        """Keyword arguments of ``CongestionModel`` (``resolve`` maps file paths)."""
        from kami.congestion import DEFAULT_GROUP_PROFILES

        kw: Dict[str, Any] = {"kind": self.kind, "period_s": self.period_s}
        if self.profiles is not None:
            kw["profiles"] = dict({k: list(v) for k, v in DEFAULT_GROUP_PROFILES.items()}, **self.profiles)
        kw["zone_groups"] = resolve(self.zone_groups_file) if self.zone_groups_file else self.zone_groups
        if self.center is not None:
            kw["center"] = (self.center["lon"], self.center["lat"])
        if self.ring_radii_m is not None:
            kw["ring_radii_m"] = list(self.ring_radii_m)
        if self.ring_groups is not None:
            kw["ring_groups"] = list(self.ring_groups)
        if self.road_class_scale is not None:
            kw["road_class_scale"] = dict(self.road_class_scale)
        if self.file:
            kw["file"] = resolve(self.file)
        return kw


@dataclass
class VehicleGroupSpec(Spec):
    """Network behaviour of a vehicle group (``kami.congestion.VehicleGroup``); missing fields: group default."""

    speed_factor: Optional[float] = f(typ=float, nullable=True, gt=0, omit_none=True)
    congestion_scale: Optional[float] = f(typ=float, nullable=True, ge=0, omit_none=True)

    def kwargs(self) -> Dict[str, float]:
        return {k: getattr(self, k) for k in ("speed_factor", "congestion_scale") if getattr(self, k) is not None}


def _vehicle_groups(v, path, errs):
    if not check_value(v, path, errs, dict):
        return None
    out = {}
    for k, x in v.items():
        p = join(path, k)
        check_value(k, p, errs, str, choices=("bike", "car"))
        out[k] = VehicleGroupSpec.parse(x if x is not None else {}, p, errs)
    return out


@dataclass
class TrafficSpec(Spec):
    """``TrafficLayer`` parameters; ``null`` = engine default.

    Sprint 02: ``congestion`` (zone × hour, replaces ``hour_profile``) and ``vehicle_groups`` (per-group speed /
    congestion scale / forbidden edges; without it every vehicle drives as a car).
    """

    hour_profile: Optional[List[float]] = f(nullable=True, parse=lambda v, p, e: _floats(v, p, e, n=24))
    weather_factor: Optional[Dict[str, float]] = f(nullable=True, parse=lambda v, p, e: _float_map(v, p, e))
    platform_sees_incidents: bool = f(False, typ=bool)
    congestion: Optional[CongestionSpec] = f(nullable=True, spec=CongestionSpec, omit_none=True)
    vehicle_groups: Optional[Dict[str, VehicleGroupSpec]] = f(nullable=True, parse=_vehicle_groups, omit_none=True)

    def kwargs(self, resolve=lambda p: p) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if self.hour_profile is not None:
            out["hour_profile"] = list(self.hour_profile)
        if self.weather_factor is not None:
            out["weather_factor"] = dict(self.weather_factor)
        if self.platform_sees_incidents:
            out["platform_sees_incidents"] = True
        if self.congestion is not None:
            out["congestion"] = self.congestion.model_kwargs(resolve)
        if self.vehicle_groups is not None:
            out["vehicle_groups"] = {k: g.kwargs() for k, g in self.vehicle_groups.items()}
        return out


def _floats(v, path, errs, n: Optional[int] = None):
    if not check_value(v, path, errs, list):
        return None
    if n is not None and len(v) != n:
        errs.add(path, f"cần đúng {n} phần tử, nhận {len(v)}")
    ok = [check_value(x, join(path, i), errs, float, ge=0) for i, x in enumerate(v)]
    return [float(x) for x in v] if all(ok) else None


def _float_map(v, path, errs):
    if not check_value(v, path, errs, dict):
        return None
    for k, x in v.items():
        check_value(x, join(path, k), errs, float, ge=0)
    return dict(v)


# =========================================================================== demand / supply sources
WEATHER_STATES = ("clear", "rain", "heavy_rain")
INCIDENT_KEYS = {"id": str, "t_offset": float, "duration": float, "at": (str, int, dict), "radius_m": float,
                 "factor": float, "cancel_multiplier": float}


def _weather(v, path, errs):
    """``[[t_seconds, state], ...]`` → list of tuples (the engine's format)."""
    if not check_value(v, path, errs, list):
        return []
    out = []
    for i, item in enumerate(v):
        p = join(path, i)
        if not (isinstance(item, (list, tuple)) and len(item) == 2):
            errs.add(p, "cần cặp [thời điểm (s), trạng thái thời tiết]")
            continue
        if check_value(item[0], join(p, 0), errs, float, ge=0) and check_value(item[1], join(p, 1), errs, str):
            out.append((item[0], item[1]))
    return out


def _incidents(v, path, errs):
    if not check_value(v, path, errs, list):
        return []
    out = []
    for i, item in enumerate(v):
        p = join(path, i)
        if not check_value(item, p, errs, dict):
            continue
        unknown_keys(item, INCIDENT_KEYS, p, errs)
        for k, typ in INCIDENT_KEYS.items():
            if k in item:
                ge = 0 if typ is float else None
                check_value(item[k], join(p, k), errs, typ, ge=ge)
        at = item.get("at", "hotspot0")
        if isinstance(at, str) and not (at.startswith("hotspot") and (at[7:] == "" or at[7:].isdigit())):
            errs.add(join(p, "at"), f"cần 'hotspot<N>', id node hoặc {{lon, lat}}, nhận {at!r}")
        item = dict(item)
        if isinstance(at, dict):
            item["at"] = _lonlat(at, join(p, "at"), errs)
        out.append(item)
    return out


def _profile(v, path, errs):
    if isinstance(v, str):
        check_value(v, path, errs, str, choices=("weekday", "weekend"))
        return v
    return _floats(v, path, errs, n=24)


# Parameters of ScenarioBuilder.synthetic that a spec may set (also the keys allowed in preset ``overrides``).
SYNTHETIC_FIELDS: Dict[str, Dict[str, Any]] = {
    "t_start": dict(typ=float, ge=0), "t_end": dict(typ=float, gt=0),
    "profile": dict(parse=_profile), "n_hotspots": dict(typ=int, ge=1), "hotspot_sigma_m": dict(typ=float, gt=0),
    "min_trip_m": dict(typ=float, ge=0), "weather": dict(parse=_weather),
    "demand_weather_multiplier": dict(typ=float, ge=0), "incidents": dict(parse=_incidents),
    "supply_multiplier": dict(typ=float, gt=0), "warmup_s": dict(typ=float, ge=0),
}


def _synthetic_overrides(v, path, errs):
    if not check_value(v, path, errs, dict):
        return {}
    unknown_keys(v, SYNTHETIC_FIELDS, path, errs)
    out = {}
    for k, x in v.items():
        if k not in SYNTHETIC_FIELDS:
            continue
        rule = dict(SYNTHETIC_FIELDS[k])
        p = join(path, k)
        parse = rule.pop("parse", None)
        if parse:
            out[k] = parse(x, p, errs)
        elif check_value(x, p, errs, **rule):
            out[k] = x
    return out


@dataclass
class PresetSourceSpec(Spec):
    """``ScenarioBuilder.preset``: a named preset, optionally with synthetic-parameter overrides."""

    kind: str = f("preset", choices=("preset",))
    preset: str = f("weekday_am_peak", required=True, typ=str)
    demand_per_hour: float = f(200.0, typ=float, ge=0)
    overrides: Dict[str, Any] = f(factory=dict, parse=_synthetic_overrides)

    def check(self, path, errs):
        from kami.scenario import PRESETS

        if self.preset not in PRESETS:
            errs.add(join(path, "preset"), f"preset {self.preset!r} không tồn tại" + suggest(self.preset, PRESETS))
            return
        kw = dict(PRESETS[self.preset], **self.overrides)
        if kw["t_start"] >= kw["t_end"]:
            errs.add(join(path, "overrides"), f"khung giờ rỗng: t_start {kw['t_start']} ≥ t_end {kw['t_end']}")

    def synthetic_kwargs(self) -> Dict[str, Any]:
        return dict(self.overrides)


@dataclass
class SyntheticSourceSpec(Spec):
    """``ScenarioBuilder.synthetic`` with explicit parameters (seconds since 0h of the scenario day)."""

    kind: str = f("synthetic", choices=("synthetic",))
    t_start: float = f(7 * 3600.0, **SYNTHETIC_FIELDS["t_start"])
    t_end: float = f(10 * 3600.0, **SYNTHETIC_FIELDS["t_end"])
    demand_per_hour: float = f(200.0, typ=float, ge=0)
    profile: Union[str, List[float]] = f("weekday", **SYNTHETIC_FIELDS["profile"])
    n_hotspots: int = f(4, **SYNTHETIC_FIELDS["n_hotspots"])
    hotspot_sigma_m: float = f(900.0, **SYNTHETIC_FIELDS["hotspot_sigma_m"])
    min_trip_m: float = f(1000.0, **SYNTHETIC_FIELDS["min_trip_m"])
    weather: List = f(factory=list, **SYNTHETIC_FIELDS["weather"])
    demand_weather_multiplier: float = f(1.0, **SYNTHETIC_FIELDS["demand_weather_multiplier"])
    incidents: List[Dict[str, Any]] = f(factory=list, **SYNTHETIC_FIELDS["incidents"])
    supply_multiplier: float = f(1.0, **SYNTHETIC_FIELDS["supply_multiplier"])
    warmup_s: float = f(0.0, **SYNTHETIC_FIELDS["warmup_s"])

    def check(self, path, errs):
        if self.t_start >= self.t_end:
            errs.add(join(path, "t_end"), f"khung giờ rỗng: t_start {self.t_start} ≥ t_end {self.t_end}")

    def synthetic_kwargs(self) -> Dict[str, Any]:
        out = {k: getattr(self, k) for k in SYNTHETIC_FIELDS}
        out["demand_per_hour"] = self.demand_per_hour
        return out


@dataclass
class FleetPyDemandSourceSpec(Spec):
    """Replay a FleetPy demand file (``rq_time,start,end,request_id``; nodes of the same road network).

    ``file``: absolute path, path relative to the working directory, or path relative to the network's data root.
    """

    kind: str = f("fleetpy_demand", choices=("fleetpy_demand",))
    file: str = f("", required=True, typ=str)
    t_start: Optional[float] = f(typ=float, nullable=True, ge=0)
    t_end: Optional[float] = f(typ=float, nullable=True, gt=0)
    time_offset: float = f(0.0, typ=float)
    capacity: int = f(4, typ=int, ge=1)


@dataclass
class CsvSourceSpec(Spec):
    """Replay historical orders (``ScenarioBuilder.from_csv``)."""

    kind: str = f("csv", choices=("csv",))
    file: str = f("", required=True, typ=str)
    time_col: str = f("t", typ=str)
    origin: List[str] = f(factory=lambda: ["o_x", "o_y"], parse=lambda v, p, e: _strs(v, p, e))
    dest: List[str] = f(factory=lambda: ["d_x", "d_y"], parse=lambda v, p, e: _strs(v, p, e))
    coords: str = f("xy", choices=("xy", "node", "lonlat"))
    t_start: Optional[float] = f(typ=float, nullable=True, ge=0)
    t_end: Optional[float] = f(typ=float, nullable=True, gt=0)


def _strs(v, path, errs, n=2):
    if not check_value(v, path, errs, list):
        return []
    if n is not None and not 1 <= len(v) <= n:
        errs.add(path, f"cần 1 hoặc 2 tên cột, nhận {len(v)}")
    return [x for i, x in enumerate(v) if check_value(x, join(path, i), errs, str)]


def _hour_range(v, path, errs):
    if not check_value(v, path, errs, list) or len(v) != 2:
        if isinstance(v, list):
            errs.add(path, "cần [giờ bắt đầu, giờ kết thúc]")
        return None
    if all(check_value(x, join(path, i), errs, float, ge=0, le=24) for i, x in enumerate(v)):
        return [float(v[0]), float(v[1])]
    return None


def _area(v, path, errs):
    """``{"bbox": [lon0, lat0, lon1, lat1], "name": optional}`` (sprint 03)."""
    if v is None:
        return None
    if not check_value(v, path, errs, dict):
        return None
    unknown = sorted(set(v) - {"bbox", "name"})
    if unknown:
        errs.add(path, f"khoá lạ {unknown}; cho phép: bbox, name")
    bbox = v.get("bbox")
    p = join(path, "bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        errs.add(p, "cần [lon0, lat0, lon1, lat1]")
        return None
    if not all(check_value(x, join(p, i), errs, float) for i, x in enumerate(bbox)):
        return None
    if not (bbox[0] < bbox[2] and bbox[1] < bbox[3]):
        errs.add(p, "cần lon0 < lon1 và lat0 < lat1")
        return None
    out = {"bbox": [float(x) for x in bbox]}
    if "name" in v and check_value(v["name"], join(path, "name"), errs, str):
        out["name"] = v["name"]
    return out


@dataclass
class ZonalSourceSpec(Spec):
    """Demand by zone × hour (``ScenarioBuilder.zonal``, sprint 02, decision D15).

    Pick-ups by zone weight (residential in the morning peak ``am_hours``, workplaces in the evening peak
    ``pm_hours``, everything otherwise), drop-offs by a gravity model ``w_dest × exp(−distance / gravity_lambda_m)``,
    nodes uniform inside a zone. ``weights``: ``zone_weights.csv`` (``zone_id,nodes,residential,work,poi``); default:
    the file next to the scenario's zone file (``FileZoneSpec``), else node counts.
    """

    kind: str = f("zonal", choices=("zonal",))
    t_start: float = f(7 * 3600.0, typ=float, ge=0)
    t_end: float = f(10 * 3600.0, typ=float, gt=0)
    demand_per_hour: float = f(1000.0, typ=float, ge=0)
    profile: Union[str, List[float]] = f("weekday", parse=_profile)
    weights: Optional[str] = f(typ=str, nullable=True, omit_none=True)
    am_hours: List[float] = f(factory=lambda: [6.0, 10.0], parse=_hour_range)
    pm_hours: List[float] = f(factory=lambda: [16.0, 20.0], parse=_hour_range)
    gravity_lambda_m: float = f(3000.0, typ=float, gt=0)
    smoothing: float = f(0.1, typ=float, ge=0)
    min_trip_m: float = f(1000.0, typ=float, ge=0)
    weather: List = f(factory=list, parse=_weather)
    demand_weather_multiplier: float = f(1.0, typ=float, ge=0)
    incidents: List[Dict[str, Any]] = f(factory=list, parse=_incidents)
    supply_multiplier: float = f(1.0, typ=float, gt=0)
    warmup_s: float = f(0.0, typ=float, ge=0)
    area: Optional[Dict[str, Any]] = f(parse=_area, nullable=True, omit_none=True)   # sprint 03: {"bbox": [...]}

    def check(self, path, errs):
        if self.t_start >= self.t_end:
            errs.add(join(path, "t_end"), f"khung giờ rỗng: t_start {self.t_start} ≥ t_end {self.t_end}")
        for i, inc in enumerate(self.incidents):
            at = inc.get("at", "hotspot0")
            if isinstance(at, str):
                errs.add(join(join(join(path, "incidents"), i), "at"), "nguồn zonal không có hotspot: dùng id node "
                                                                       "hoặc {lon, lat}")

    def zonal_kwargs(self) -> Dict[str, Any]:
        keys = ("t_start", "t_end", "demand_per_hour", "profile", "am_hours", "pm_hours", "gravity_lambda_m",
                "smoothing", "min_trip_m", "weather", "demand_weather_multiplier", "incidents", "supply_multiplier",
                "warmup_s")
        kw = {k: getattr(self, k) for k in keys}
        if self.area is not None:
            kw["area"] = self.area["bbox"]
        return kw


SourceSpec = Union[PresetSourceSpec, SyntheticSourceSpec, FleetPyDemandSourceSpec, CsvSourceSpec, ZonalSourceSpec]
parse_source = union({"preset": PresetSourceSpec, "synthetic": SyntheticSourceSpec,
                      "fleetpy_demand": FleetPyDemandSourceSpec, "csv": CsvSourceSpec, "zonal": ZonalSourceSpec})


def _schema_version(v, path, errs):
    if check_value(v, path, errs, int, ge=1) and v > SCHEMA_VERSION:
        errs.add(path, f"schema_version {v} mới hơn bản kami này hỗ trợ ({SCHEMA_VERSION}); hãy nâng cấp kami")
    return v


@dataclass
class ScenarioSpec(Spec):
    """The exogenous world: network, zones, traffic, demand/supply source, seed.

    For a ``synthetic`` source, ``name`` is part of the random stream (same name + seed = same scenario);
    a ``preset`` source is named after its preset, exactly as ``ScenarioBuilder.preset``.
    ``n_drivers`` is used when the run declares no fleet.
    """

    schema_version: int = f(SCHEMA_VERSION, parse=_schema_version)
    name: str = f("scenario", typ=str)
    network: NetworkSpec = f(factory=GridNetworkSpec, parse=parse_network)
    zones: ZoneSpec = f(factory=SquareZoneSpec, parse=parse_zones)
    traffic: TrafficSpec = f(factory=TrafficSpec, spec=TrafficSpec)
    source: SourceSpec = f(factory=PresetSourceSpec, required=True, parse=parse_source)
    n_drivers: int = f(150, typ=int, ge=1)
    seed: int = f(0, typ=int)

    def check(self, path, errs):
        if isinstance(self.source, (FleetPyDemandSourceSpec,)) and not isinstance(self.network, RoadNetworkSpec):
            errs.add(join(path, "source"), "nguồn fleetpy_demand cần mạng đường (network.kind = 'road')")


# =========================================================================== vehicles, fleets, charging
@dataclass
class VehicleTypeSpec(Spec):
    """A vehicle type. ``range_km`` is stored and validated; the engine uses it from sprint 05 (EV)."""

    name: str = f("", required=True, typ=str)
    group: str = f("car", choices=("bike", "car"))
    seats: int = f(4, typ=int, ge=1)
    range_km: Optional[float] = f(typ=float, nullable=True, gt=0)


@dataclass
class FleetComposition(Spec):
    vehicle_type: str = f("", required=True, typ=str)
    count: int = f(1, required=True, typ=int, ge=1)


@dataclass
class FleetSpec(Spec):
    """A fleet: vehicles by type. Total vehicles of all fleets replaces the scenario's ``n_drivers``."""

    name: str = f("", required=True, typ=str)
    composition: List[FleetComposition] = f(factory=list, required=True, list_of=FleetComposition)

    def check(self, path, errs):
        if not self.composition:
            errs.add(join(path, "composition"), "fleet cần ít nhất một loại xe")
        seen = set()
        for i, c in enumerate(self.composition):
            if c.vehicle_type in seen:
                errs.add(join(join(path, "composition"), i), f"loại xe {c.vehicle_type!r} lặp lại")
            seen.add(c.vehicle_type)

    def size(self) -> int:
        return sum(c.count for c in self.composition)


@dataclass
class ChargingStationSpec(Spec):
    """A charging station at ``lon``/``lat`` or at a network ``node``. Used by the engine from sprint 05."""

    name: str = f("", required=True, typ=str)
    lon: Optional[float] = f(typ=float, nullable=True, ge=-180, le=180)
    lat: Optional[float] = f(typ=float, nullable=True, ge=-90, le=90)
    node: Optional[int] = f(typ=int, nullable=True, ge=0)
    ports: int = f(1, typ=int, ge=1)
    power_kw: float = f(60.0, typ=float, gt=0)

    def check(self, path, errs):
        has_ll = self.lon is not None or self.lat is not None
        if has_ll and (self.lon is None or self.lat is None):
            errs.add(path, "cần cả lon và lat")
        if has_ll == (self.node is not None):
            errs.add(path, "cần đúng một vị trí: (lon, lat) hoặc node")


# =========================================================================== policies
COMMON_POLICY_PARAMS = ("matching", "batch_window")
MATCHING_CONSTRAINTS = {"max_pickup_eta": dict(gt=0), "candidates_per_job": dict(ge=1), "max_speed_mps": dict(gt=0),
                        "solver": dict(choices=("hungarian", "greedy"))}


def policy_params_schema(plugin_cls) -> Dict[str, Any]:
    """``{param: default}`` accepted by a policy class, read from its constructor chain (decision D4)."""
    out: Dict[str, Any] = {}
    for klass in plugin_cls.__mro__:
        init = klass.__dict__.get("__init__")
        if init is None:
            continue
        has_kw = False
        for name, p in inspect.signature(init).parameters.items():
            if name == "self" or p.kind == p.VAR_POSITIONAL:
                continue
            if p.kind == p.VAR_KEYWORD:
                has_kw = True
                continue
            out.setdefault(name, None if p.default is inspect.Parameter.empty else p.default)
        if not has_kw:
            break
    return out


def check_policy_params(plugin: str, params: Dict[str, Any], path: str, errs: Errors) -> None:
    from kami.matching import MatchingParams
    from kami.policy import POLICIES

    schema = policy_params_schema(POLICIES[plugin])
    unknown_keys(params, schema, path, errs)
    for k, v in params.items():
        if k not in schema:
            continue
        p = join(path, k)
        if k == "matching":
            if v is not None:
                dataclass_overrides(v, MatchingParams, p, errs, MATCHING_CONSTRAINTS)
        elif k == "batch_window":
            check_value(v, p, errs, float, nullable=True, gt=0)
        else:
            dv = schema[k]
            kind = default_kind(dv) if dv is not None else (float, str, bool)
            if kind is int:   # money / counts given as int defaults: accept any number
                kind = float
            check_value(v, p, errs, kind, nullable=dv is None)


def _params(v, path, errs):
    return dict(v) if check_value(v, path, errs, dict) else {}


@dataclass
class PolicySpec(Spec):
    """A policy plug-in (key of ``POLICIES``) and its constructor parameters.

    ``params.matching`` (fields of ``MatchingParams``) and ``params.batch_window`` are common to every policy.
    ``name``/``version`` identify a stored policy version (filled in by ``Repository.resolve``).
    """

    plugin: str = f("baseline", required=True, typ=str)
    params: Dict[str, Any] = f(factory=dict, parse=_params)
    name: Optional[str] = f(typ=str, nullable=True, omit_none=True)
    version: Optional[int] = f(typ=int, nullable=True, ge=1, omit_none=True)

    def check(self, path, errs):
        from kami.policy import POLICIES

        if self.plugin not in POLICIES:
            errs.add(join(path, "plugin"), f"policy {self.plugin!r} không tồn tại" + suggest(self.plugin, POLICIES))
            return
        check_policy_params(self.plugin, self.params, join(path, "params"), errs)


@dataclass
class PolicyGroupMember(Spec):
    """One member of a group: an inline policy or a reference to a stored policy (version optional).

    ``params`` override the policy's parameters for this group only.
    """

    policy: Union[PolicySpec, Ref] = f(factory=PolicySpec, required=True, parse=ref_or(PolicySpec))
    params: Dict[str, Any] = f(factory=dict, parse=_params)
    enabled: bool = f(True, typ=bool)

    def check(self, path, errs):
        if self.params and isinstance(self.policy, PolicySpec) and self.policy.plugin:
            from kami.policy import POLICIES

            if self.policy.plugin in POLICIES:
                check_policy_params(self.policy.plugin, self.params, join(path, "params"), errs)

    def effective_params(self) -> Dict[str, Any]:
        assert isinstance(self.policy, PolicySpec), "unresolved reference"
        return dict(self.policy.params, **self.params)


@dataclass
class PolicyGroupSpec(Spec):
    """Ordered policies acting together. 0 enabled → ``Baseline``; 1 → that policy; ≥ 2 → ``Composite`` (D5)."""

    name: str = f("default", typ=str)
    members: List[PolicyGroupMember] = f(factory=list, list_of=PolicyGroupMember)


# =========================================================================== behaviour
SLOT_METHOD = {"booking": "p_book", "cancel_wait": "hazard", "cancel_matched": "hazard", "pool_accept": "p_accept",
               "driver_accept": "p_accept", "idle_move": "distribution", "driver_shift": "p_stop"}


def _model_classes() -> Dict[str, Any]:
    from kami.behavior import models as M

    return {n: getattr(M, n) for n in ("LogitBooking", "WeibullCancel", "OverrunCancel", "LogitPoolAccept",
                                       "LogitDriverAccept", "AlwaysAccept", "HomeBiasIdleMove",
                                       "TransitionMatrixIdleMove", "ScheduledShift", "IncomeTargetShift",
                                       "ProbabilityScaler", "HazardScaler")}


def model_params_class(cls) -> Optional[type]:
    """The ``*Params`` dataclass a model is built from (``None`` for parameterless/special models)."""
    hint = inspect.signature(cls.__init__).parameters.get("params")
    if hint is None:
        return None
    import kami.behavior.models as M

    names = re.findall(r"(\w+Params)\b", str(hint.annotation))
    return getattr(M, names[-1], None) if names else None


WRAPPERS = ("ProbabilityScaler", "HazardScaler")


@dataclass
class ModelSpec(Spec):
    """A behaviour model of ``kami.behavior.models``: ``{"class": "LogitBooking", "params": {...}}``.

    Wrappers take ``{"inner": <model>, "factor": x}``; ``TransitionMatrixIdleMove`` takes ``{"matrix": {...}}``.
    """

    cls: str = f("", required=True, typ=str, key="class")
    params: Dict[str, Any] = f(factory=dict, parse=_params)

    def check(self, path, errs):
        classes = _model_classes()
        if self.cls not in classes:
            errs.add(join(path, "class"), f"model {self.cls!r} không tồn tại" + suggest(self.cls, classes))
            return
        p = join(path, "params")
        if self.cls in WRAPPERS:
            unknown_keys(self.params, ("inner", "factor"), p, errs)
            if "inner" not in self.params:
                errs.add(join(p, "inner"), "thiếu trường bắt buộc")
            else:
                ModelSpec.parse(self.params["inner"], join(p, "inner"), errs)
            check_value(self.params.get("factor"), join(p, "factor"), errs, float, ge=0)
        elif self.cls == "TransitionMatrixIdleMove":
            unknown_keys(self.params, ("matrix", "fallback"), p, errs)
            check_value(self.params.get("matrix"), join(p, "matrix"), errs, dict)
            if self.params.get("fallback") is not None:
                ModelSpec.parse(self.params["fallback"], join(p, "fallback"), errs)
        else:
            pc = model_params_class(classes[self.cls])
            if pc is None:
                unknown_keys(self.params, (), p, errs)
            else:
                dataclass_overrides(self.params, pc, p, errs)

    def method_class(self):
        """Innermost class (the one that answers the slot's question)."""
        if self.cls in WRAPPERS:
            return ModelSpec.from_dict(self.params["inner"]).method_class()
        return _model_classes()[self.cls]


def _slot_versions(v, path, errs):
    if not check_value(v, path, errs, dict):
        return {}
    unknown_keys(v, SLOT_METHOD, path, errs)
    return {k: x for k, x in v.items() if k in SLOT_METHOD and check_value(x, join(path, k), errs, str)}


def _slot_models(v, path, errs):
    if not check_value(v, path, errs, dict):
        return {}
    unknown_keys(v, SLOT_METHOD, path, errs)
    out = {}
    for slot, m in v.items():
        if slot not in SLOT_METHOD:
            continue
        p = join(path, slot)
        n = len(errs)
        spec = ModelSpec.parse(m, p, errs)
        if len(errs) == n:
            method = SLOT_METHOD[slot]
            if not hasattr(spec.method_class(), method):
                errs.add(join(p, "class"), f"model {spec.cls} không dùng được cho slot {slot} (thiếu {method})")
        out[slot] = spec
    return out


@dataclass
class BehaviorSpec(Spec):
    """Behaviour suite: a base preset, then registry checkpoints, then explicit models (later wins).

    ``registry`` without ``slots`` loads the latest checkpoint of every slot folder (like ``--registry``).
    """

    preset: str = f("default", choices=("default", "employed_drivers"))
    registry: Optional[str] = f(typ=str, nullable=True)
    slots: Dict[str, str] = f(factory=dict, parse=_slot_versions)
    models: Dict[str, ModelSpec] = f(factory=dict, parse=_slot_models)

    def check(self, path, errs):
        if self.slots and not self.registry:
            errs.add(join(path, "slots"), "cần khai báo registry")


# =========================================================================== engine configuration
SIMCONFIG_CONSTRAINTS = {k: dict(gt=0) for k in ("batch_window", "cancel_step_s", "traffic_update_s",
                                                  "cancel_lookahead_s")}
SIMCONFIG_CONSTRAINTS.update({k: dict(ge=0) for k in ("boarding_s", "alighting_s", "idle_decision_s",
                                                       "idle_recheck_s", "drain_s", "default_quote_eta")})
SIMCONFIG_CONSTRAINTS["timeseries_interval_s"] = dict(gt=0)
SIMCONFIG_CONSTRAINTS.update(retime_threshold=dict(ge=0), retime_min_s=dict(ge=0))
FARE_CONSTRAINTS = {k: dict(ge=0) for k in ("base", "per_km", "per_min", "min_fare", "surcharge_to_driver")}
FARE_CONSTRAINTS["take_rate"] = dict(ge=0, le=1)
DEFAULT_TIMESERIES_INTERVAL_S = 300.0


def _sim_config(v, path, errs):
    from kami.core.engine import SimConfig
    from kami.pooling import PoolingParams
    from kami.pricing import FareModel

    return dataclass_overrides(
        v, SimConfig, path, errs, SIMCONFIG_CONSTRAINTS,
        nested={"fare": lambda d, p, e: dataclass_overrides(d, FareModel, p, e, FARE_CONSTRAINTS),
                "pooling": lambda d, p, e: dataclass_overrides(d, PoolingParams, p, e)})


@dataclass
class SimConfigSpec(Spec):
    """Sparse overrides of ``SimConfig`` (+ nested ``fare`` = ``FareModel``, ``pooling`` = ``PoolingParams``).

    Missing keys keep the engine default, except ``timeseries_interval_s`` which defaults to 300 s for spec
    runs (``null`` disables the time-series sampler). ``pooling`` only represents kami 0.1 configurations.
    """

    values: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse(cls, d, path, errs):
        return cls(_sim_config(d, path, errs))

    def to_dict(self):
        return _dump(self.values)


@dataclass
class OutputSpec(Spec):
    """What a run writes besides metrics. ``parquet`` needs ``pyarrow`` (``pip install kami[store]``)."""

    event_log: str = f("parquet", choices=("parquet", "csv.gz", "none"))
    trajectories: str = f("none", choices=("none", "parquet"))   # sprint 02: turns on SimConfig.record_trajectories
    # sprint 03: replay folder for the web visualizer (kami.replay); omitted = "none"
    replay: Optional[str] = f(None, typ=str, choices=("none", "json"), nullable=True, omit_none=True)


# =========================================================================== run
def _named_list(item_cls):
    parse_item = ref_or(item_cls)

    def parse(v, path, errs):
        if not check_value(v, path, errs, list):
            return []
        return [parse_item(x, join(path, i), errs) for i, x in enumerate(v)]

    return parse


@dataclass
class RunSpec(Spec):
    """One simulation run: scenario + vehicles/fleets + policy group + behaviour + engine config + seed.

    ``seed`` overrides ``scenario.seed``; ``crn_seed`` (default: the scenario seed) seeds the CRN streams.
    """

    schema_version: int = f(SCHEMA_VERSION, parse=_schema_version)
    name: str = f("run", typ=str)
    scenario: Union[ScenarioSpec, Ref] = f(factory=ScenarioSpec, required=True, parse=ref_or(ScenarioSpec))
    vehicle_types: List[Union[VehicleTypeSpec, Ref]] = f(factory=list, parse=_named_list(VehicleTypeSpec))
    fleets: List[Union[FleetSpec, Ref]] = f(factory=list, parse=_named_list(FleetSpec))
    charging_stations: List[Union[ChargingStationSpec, Ref]] = f(factory=list,
                                                                 parse=_named_list(ChargingStationSpec))
    policy_group: Union[PolicyGroupSpec, Ref] = f(factory=PolicyGroupSpec, parse=ref_or(PolicyGroupSpec))
    behavior: BehaviorSpec = f(factory=BehaviorSpec, spec=BehaviorSpec)
    sim_config: SimConfigSpec = f(factory=SimConfigSpec, spec=SimConfigSpec)
    seed: Optional[int] = f(typ=int, nullable=True)
    crn_seed: Optional[int] = f(typ=int, nullable=True)
    outputs: OutputSpec = f(factory=OutputSpec, spec=OutputSpec)

    def check(self, path, errs):
        self.check_references(path, errs)

    def check_references(self, path: str, errs: Errors) -> None:
        """Names unique per kind; fleets only use declared vehicle types (skipped while references remain)."""
        for kind in ("vehicle_types", "fleets", "charging_stations"):
            seen = set()
            for i, x in enumerate(getattr(self, kind)):
                if isinstance(x, Ref):
                    continue
                if x.name in seen:
                    errs.add(join(join(path, kind), i), f"tên {x.name!r} lặp lại")
                seen.add(x.name)
        if any(isinstance(x, Ref) for x in self.vehicle_types):
            return
        types = {v.name for v in self.vehicle_types}
        for i, fl in enumerate(self.fleets):
            if isinstance(fl, Ref):
                continue
            for j, c in enumerate(fl.composition):
                if c.vehicle_type not in types:
                    p = join(join(join(join(path, "fleets"), i), "composition"), j)
                    errs.add(join(p, "vehicle_type"), f"loại xe {c.vehicle_type!r} không được khai báo trong "
                                                      f"vehicle_types" + suggest(c.vehicle_type, types))

    def has_refs(self) -> bool:
        if isinstance(self.scenario, Ref) or isinstance(self.policy_group, Ref):
            return True
        if any(isinstance(x, Ref) for k in ("vehicle_types", "fleets", "charging_stations") for x in getattr(self, k)):
            return True
        return any(isinstance(m.policy, Ref) for m in self.policy_group.members)

    @property
    def effective_seed(self) -> int:
        assert isinstance(self.scenario, ScenarioSpec)
        return self.scenario.seed if self.seed is None else self.seed


def load_run_spec(path: Union[str, Path]) -> RunSpec:
    """Read and validate a RunSpec JSON file."""
    path = Path(path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SpecError([(str(path), f"JSON không hợp lệ: {e}")]) from None
    return RunSpec.from_dict(doc)
