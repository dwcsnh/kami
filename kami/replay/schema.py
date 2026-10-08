"""Replay data contract ``kami.replay`` v1 (sprint 03, S03-1; docs/engine/20-visualizer.md).

A replay is a folder of JSON files (each one optionally gzip-compressed, ``<name>.json.gz``):

* ``manifest.json`` (never compressed): ``schema_version``, ``kind``, run / area / time metadata, the vehicle
  ``states`` (id, label, colour token), the files with their sha256;
* ``vehicles.json``: one object per vehicle;
* ``trips.json``: vehicle *segments* by column, sorted by (vehicle, t0) — a moving leg or a stationary gap, each with
  one state; ``path`` is a flat ``[lon, lat, lon, lat, …]`` list and ``ts`` the time of every point;
* ``events.json``: rider events by column (``to_lon``/``to_lat``: destination of a ``request``; ``eta``: promised
  pick-up time of a ``matched`` event);
* ``metrics.json``: the engine's time-series rows (``sim.timeseries``) by column, NaN as ``null``.

Compatibility: readers ignore unknown fields; a new field or a new state keeps ``schema_version``; a change of
meaning bumps it. ``validate`` refuses a newer major version with a clear message.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

SCHEMA_VERSION = 1
KIND = "kami.replay"
FILES = ("vehicles", "trips", "events", "metrics")

# id, label (Vietnamese UI text), colour token (web/src/design/tokens.json → color.state.<id>)
STATES: List[Dict[str, str]] = [
    {"id": "idle", "label": "Rảnh – đứng yên", "color": "state.idle"},
    {"id": "cruising", "label": "Rảnh – đang chạy", "color": "state.cruising"},
    {"id": "pickup", "label": "Đi đón khách", "color": "state.pickup"},
    {"id": "on_trip", "label": "Chở khách", "color": "state.on_trip"},
    {"id": "reposition", "label": "Điều xe", "color": "state.reposition"},
]
EVENT_TYPES = ("request", "booked", "declined", "matched", "pickup", "dropoff", "cancel")
TRIP_COLUMNS = ("vehicle", "state", "rider", "t0", "t1", "dist_m", "path", "ts")
EVENT_COLUMNS = ("t", "type", "rider", "vehicle", "lon", "lat")

PathLike = Union[str, Path]


# ---------------------------------------------------------------------------- reading
def file_path(folder: PathLike, name: str) -> Optional[Path]:
    """``<name>.json`` or ``<name>.json.gz`` inside ``folder`` (None when neither exists)."""
    folder = Path(folder)
    for p in (folder / f"{name}.json", folder / f"{name}.json.gz"):
        if p.exists():
            return p
    return None


def read_json(path: PathLike) -> Any:
    raw = Path(path).read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def load(folder: PathLike) -> Dict[str, Any]:
    """``{"manifest": …, "vehicles": …, "trips": …, "events": …, "metrics": …}`` (no validation)."""
    out = {"manifest": read_json(Path(folder) / "manifest.json")}
    for name in FILES:
        p = file_path(folder, name)
        out[name] = read_json(p) if p else None
    return out


def sha256(path: PathLike) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------- validation
def validate(folder: PathLike, tol_s: float = 0.05) -> List[str]:
    """Problems of the replay in ``folder`` (empty list = valid). Standard library only."""
    folder = Path(folder)
    errs: List[str] = []
    mpath = folder / "manifest.json"
    if not mpath.exists():
        return [f"{folder}: thiếu manifest.json"]
    try:
        man = read_json(mpath)
    except ValueError as e:
        return [f"manifest.json: JSON lỗi ({e})"]
    if man.get("kind") != KIND:
        errs.append(f"manifest.kind = {man.get('kind')!r}, cần {KIND!r}")
    ver = man.get("schema_version")
    if not isinstance(ver, int):
        return errs + ["manifest.schema_version thiếu hoặc không phải số nguyên"]
    if ver > SCHEMA_VERSION:
        return errs + [f"schema_version {ver} mới hơn bản kami này hỗ trợ ({SCHEMA_VERSION}); hãy nâng cấp kami"]

    data: Dict[str, Any] = {}
    files = man.get("files") or {}
    for name in FILES:
        meta = files.get(name)
        if meta is None:
            errs.append(f"manifest.files thiếu {name!r}")
            continue
        p = folder / meta.get("path", "")
        if not p.is_file():
            errs.append(f"thiếu file {meta.get('path')!r}")
            continue
        if meta.get("sha256") and sha256(p) != meta["sha256"]:
            errs.append(f"{meta['path']}: sha256 không khớp manifest")
        try:
            data[name] = read_json(p)
        except (ValueError, OSError) as e:
            errs.append(f"{meta['path']}: JSON lỗi ({e})")
    states = {s.get("id") for s in man.get("states") or []}
    if not states:
        errs.append("manifest.states rỗng")
    t = man.get("time") or {}
    if not isinstance(t.get("start"), (int, float)) or not isinstance(t.get("end"), (int, float)) \
            or t["start"] > t["end"]:
        errs.append("manifest.time cần start ≤ end (giây từ 0h)")
    bounds = man.get("bounds")
    if "vehicles" in data:
        errs += _check_vehicles(data["vehicles"])
    if "trips" in data:
        vids = {v.get("id") for v in data.get("vehicles") or []}
        errs += _check_trips(data["trips"], states, vids, bounds, tol_s)
    if "events" in data:
        errs += _check_columns("events.json", data["events"], EVENT_COLUMNS)
        bad = sorted({x for x in data["events"].get("type", []) if x not in EVENT_TYPES})
        if bad:
            errs.append(f"events.json: loại sự kiện lạ {bad}")
        ts = data["events"].get("t", [])
        if any(b < a for a, b in zip(ts, ts[1:])):
            errs.append("events.json: thời gian giảm")
    if "metrics" in data:
        m = data["metrics"]
        n = len(m.get("t", []))
        for k, col in (m.get("series") or {}).items():
            if len(col) != n:
                errs.append(f"metrics.json: cột {k!r} có {len(col)} giá trị, cần {n}")
    return errs


def _check_columns(name: str, table: Dict[str, list], columns) -> List[str]:
    if not isinstance(table, dict):
        return [f"{name}: cần object theo cột"]
    missing = [c for c in columns if c not in table]
    if missing:
        return [f"{name}: thiếu cột {missing}"]
    lens = {c: len(table[c]) for c in columns}
    if len(set(lens.values())) > 1:
        return [f"{name}: các cột dài khác nhau {lens}"]
    return []


def _check_vehicles(vehicles) -> List[str]:
    if not isinstance(vehicles, list):
        return ["vehicles.json: cần một mảng"]
    errs = []
    ids = [v.get("id") for v in vehicles]
    if len(set(ids)) != len(ids):
        errs.append("vehicles.json: trùng id xe")
    for v in vehicles:
        sh = v.get("shift")
        if not (isinstance(sh, list) and len(sh) == 2 and sh[0] <= sh[1]):
            errs.append(f"vehicles.json: xe {v.get('id')}: shift cần [t0, t1] với t0 ≤ t1")
    return errs


def _check_trips(trips, states, vids, bounds, tol: float) -> List[str]:
    errs = _check_columns("trips.json", trips, TRIP_COLUMNS)
    if errs:
        return errs
    if bounds:
        x0, y0, x1, y1 = bounds
        mx, my = (x1 - x0) * 0.01 + 1e-6, (y1 - y0) * 0.01 + 1e-6
    prev_v, prev_end, prev_pt = None, None, None
    for i, (v, st, t0, t1, path, ts) in enumerate(zip(trips["vehicle"], trips["state"], trips["t0"], trips["t1"],
                                                      trips["path"], trips["ts"])):
        where = f"trips.json[{i}] (xe {v})"
        if vids and v not in vids:
            errs.append(f"{where}: xe không có trong vehicles.json")
        if st not in states:
            errs.append(f"{where}: trạng thái lạ {st!r}")
        if len(path) != 2 * len(ts) or not ts:
            errs.append(f"{where}: path cần 2 × len(ts) số, ts không rỗng")
            prev_v = None
            continue
        if t1 < t0 or ts[0] < t0 - tol or ts[-1] > t1 + tol:
            errs.append(f"{where}: thời gian ngoài [t0, t1]")
        if any(b < a for a, b in zip(ts, ts[1:])):
            errs.append(f"{where}: thời gian giảm trong segment")
        if bounds and any(not (x0 - mx <= x <= x1 + mx and y0 - my <= y <= y1 + my)
                          for x, y in zip(path[0::2], path[1::2])):
            errs.append(f"{where}: toạ độ ngoài manifest.bounds")
        if v == prev_v:
            if t0 < prev_end - tol:
                errs.append(f"{where}: bắt đầu trước khi segment trước kết thúc")
            if (path[0], path[1]) != prev_pt:
                errs.append(f"{where}: không nối tiếp điểm cuối của segment trước")
        elif prev_v is not None and _key(v) < _key(prev_v):
            errs.append(f"{where}: segment chưa sắp theo xe")
        prev_v, prev_end, prev_pt = v, t1, (path[-2], path[-1])
        if len(errs) > 50:
            errs.append("… (dừng sau 50 lỗi)")
            break
    return errs


def _key(v):
    return (0, v) if isinstance(v, (int, float)) else (1, str(v))
