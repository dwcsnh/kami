"""Write a ``kami.replay`` v1 folder from a finished run (sprint 03, S03-2, decisions D5, D6, D8).

The state timeline of a vehicle is built from its trajectory legs (``sim.trajectories``, sprint 02) and the gaps
between them, from the moment it goes online to the moment it goes offline:

* a leg is a moving segment: ``idle`` → ``cruising``, ``reposition`` → ``reposition``, ``stop`` without a rider on
  board → ``pickup``, with a rider on board → ``on_trip``;
* a gap is a stationary segment (one point): ``on_trip`` when the next leg carries a rider (the rider is boarding),
  ``idle`` otherwise — so the states follow the event log (``TRIP_ACCEPTED`` → pickup, ``PICKUP`` → on_trip,
  ``DROPOFF`` / matched cancel → idle, ``IDLE_MOVE`` → cruising / reposition).

Writing is deterministic: sorted keys, fixed rounding (6 decimals for lon/lat, 0.1 s for times), gzip with
``mtime=0`` and no file name, no wall-clock time in any file — the same run gives the same bytes.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from kami.replay.schema import FILES, KIND, SCHEMA_VERSION, STATES
from kami.replay.simplify import simplify

PathLike = Union[str, Path]
EPS = 1e-3                    # gaps shorter than this (s) are not segments (the event log keeps 3 decimals)
EVENT_MAP = {"REQUEST_CREATED": "request", "OFFER_ACCEPTED": "booked", "OFFER_REJECTED": "declined",
             "TRIP_ACCEPTED": "matched", "PICKUP": "pickup", "DROPOFF": "dropoff", "RIDER_CANCEL": "cancel"}


@dataclass
class SimplifyParams:
    dist_m: float = 1.0
    dt_s: float = 0.5


@dataclass
class ReplayInput:
    """Everything an export needs, independent of a live ``Simulation`` (a run folder gives the same)."""

    legs: List[Dict[str, Any]]                        # TrajectoryRecorder.rows(geometry=True)
    coords: str                                       # "lonlat" | "xy"
    events: List[Tuple[float, str, Optional[int], Optional[int], Dict[str, Any]]]
    metrics: List[Dict[str, float]]
    metrics_interval_s: Optional[float]
    vehicles: List[Dict[str, Any]]                    # id, fleet, vehicle_type, group, seats, home: (x, y)
    riders: Dict[int, Tuple[float, float, float, float]]   # rider → (origin x, y, destination x, y)
    t_start: float
    t_end: float                                      # end of the run (sim.t)
    run: Dict[str, Any] = field(default_factory=dict)
    shared: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------- input from a run
def from_simulation(sim, run: Optional[Dict[str, Any]] = None) -> ReplayInput:
    """Collect the export input from a finished ``Simulation`` run with ``record_trajectories`` and events on."""
    if sim.trajectories is None:
        raise ValueError("replay export needs trajectories: SimConfig(record_trajectories=True) or "
                         "outputs.trajectories / outputs.replay in the RunSpec")
    if not sim.log.enabled:
        raise ValueError("replay export needs the event log (SimConfig.record_events=True)")
    rows, coords = sim.trajectories.rows(geometry=True)
    net = sim.network
    nodes = sorted({d.loc for d in sim.scenario.drivers} | {r.origin for r in sim.riders.values()} |
                   {r.dest for r in sim.riders.values()})
    pos = dict(zip(nodes, _positions(net, nodes, coords)))
    vehicles = []
    for d in sorted(sim.scenario.drivers, key=lambda d: d.id):
        vehicles.append({"id": d.id, "fleet": d.attrs.get("fleet_id"), "vehicle_type": d.attrs.get("vehicle_type"),
                         "group": d.attrs.get("vehicle_group"), "seats": d.capacity, "home": pos[d.loc]})
    riders = {r.id: pos[r.origin] + pos[r.dest] for r in sim.riders.values()}
    ts = sim.timeseries
    meta = {"scenario": sim.scenario.name, "seed": sim.scenario.seed, "network": getattr(net, "name", None) or
            type(net).__name__, "policy": getattr(sim.policy, "name", type(sim.policy).__name__),
            "crn_seed": getattr(sim.crn, "seed", None)}
    meta.update(run or {})
    shared = shared_metadata(sim)
    return ReplayInput(rows, coords, list(sim.log.rows), list(ts.rows) if ts else [],
                       ts.interval if ts else None, vehicles, riders, sim.scenario.t_start, sim.t, meta, shared)


def shared_metadata(sim) -> Optional[Dict[str, Any]]:
    """Optional final observations, also persisted for run-folder replay exports."""
    shared = None
    if sim.shared_enabled:
        from kami.shared.metrics import pair_actual
        shared = {"version": 1, "fare_factor": 0.7,
                  "pairs": [dict(p, **pair_actual(p, sim.t)) for p in sim.shared_pairs.values()],
                  "riders": [{"id": r.id, "service_preference": r.service_preference,
                              "pair_history": list(r.pair_history), "fare": r.fare,
                              "exclusive_reference_fare": r.exclusive_reference_fare,
                              "booked_t": r.t_booked, "pickup_deadline": r.pickup_deadline,
                              "pickup_t": r.t_pickup, "dropoff_t": r.t_dropoff,
                              "cancel_t": r.t_cancel, "reason": r.cancellation_reason}
                             for r in sorted(sim.riders.values(), key=lambda r: r.id)]}
    return shared


def _positions(net, nodes: Sequence[int], coords: str) -> List[Tuple[float, float]]:
    if coords == "lonlat":
        if hasattr(net, "lonlats"):
            return [tuple(p) for p in net.lonlats(nodes)]
        return [tuple(net.lonlat(n)) for n in nodes]
    return [tuple(net.coords(n)) for n in nodes]


# ---------------------------------------------------------------------------- state timeline
def leg_state(leg: Dict[str, Any]) -> str:
    p = leg["purpose"]
    if p == "idle":
        return "cruising"
    if p == "reposition":
        return "reposition"
    return "on_trip" if leg["occupied"] else "pickup"


def _length(xs, ys, coords: str) -> float:
    total = 0.0
    for i in range(1, len(xs)):
        dx, dy = xs[i] - xs[i - 1], ys[i] - ys[i - 1]
        if coords == "lonlat":
            dx *= 111_320.0 * math.cos(math.radians((ys[i] + ys[i - 1]) / 2))
            dy *= 111_320.0
        total += math.hypot(dx, dy)
    return total


def timeline(inp: ReplayInput, params: SimplifyParams = SimplifyParams()) -> List[Dict[str, Any]]:
    """Segments of every vehicle, sorted by (vehicle, t0); coordinates and times not yet rounded."""
    online: Dict[int, float] = {}
    offline: Dict[int, float] = {}
    for t, ev, _, did, _ in inp.events:
        if ev == "DRIVER_ONLINE" and did not in online:
            online[did] = t
        elif ev == "DRIVER_OFFLINE":
            offline[did] = t
    legs_by: Dict[int, List[Dict[str, Any]]] = {}
    for leg in inp.legs:
        legs_by.setdefault(leg["driver_id"], []).append(leg)
    lonlat = inp.coords == "lonlat"
    segs: List[Dict[str, Any]] = []
    for v in inp.vehicles:
        vid = v["id"]
        if vid not in online:
            continue
        t_c = online[vid]
        end = offline.get(vid, inp.t_end)
        legs = sorted(legs_by.get(vid, []), key=lambda r: r["leg_seq"])
        pt = (legs[0]["path_lon"][0], legs[0]["path_lat"][0]) if legs else tuple(v["home"])
        for leg in legs:
            # a leg of zero length (stop at the vehicle's node) or cut before it departed (boarding interrupted)
            # has no movement: it only ends the gap before it, at its end time
            still = leg["t_end"] <= leg["t_depart"] + 1e-9 or len(leg["path_t"]) < 1
            gap_end = leg["t_end"] if still else leg["t_depart"]
            if gap_end > t_c + EPS:
                occ = bool(leg["occupied"])
                segs.append(_seg(vid, "on_trip" if occ else "idle", leg["rider_id"] if occ else None, t_c,
                                 gap_end, [pt[0]], [pt[1]], [t_c]))
                t_c = gap_end
            if still:
                continue
            xs, ys, ts = leg["path_lon"], leg["path_lat"], leg["path_t"]
            keep = simplify(xs, ys, ts, params.dist_m, params.dt_s, lonlat=lonlat)
            seg = _seg(vid, leg_state(leg), leg["rider_id"], leg["t_depart"], leg["t_end"],
                       [xs[i] for i in keep], [ys[i] for i in keep], [ts[i] for i in keep])
            seg["dist_m"] = _length(xs, ys, inp.coords)
            segs.append(seg)
            t_c, pt = max(t_c, leg["t_end"]), (xs[-1], ys[-1])
        if end > t_c + EPS:
            segs.append(_seg(vid, "idle", None, t_c, end, [pt[0]], [pt[1]], [t_c]))
    return segs


def _seg(vid, state, rider, t0, t1, xs, ys, ts) -> Dict[str, Any]:
    return {"vehicle": vid, "state": state, "rider": rider, "t0": t0, "t1": t1, "dist_m": 0.0,
            "xs": xs, "ys": ys, "ts": ts}


# ---------------------------------------------------------------------------- tables
def _r(x: Optional[float], nd: int):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    y = round(x, nd)
    return 0.0 if y == 0 else y            # no "-0.0"


def tables(inp: ReplayInput, params: SimplifyParams = SimplifyParams(),
           area: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The five documents of a replay (``manifest`` without the ``files`` block)."""
    nd = 6 if inp.coords == "lonlat" else 2
    segs = timeline(inp, params)
    trips: Dict[str, list] = {k: [] for k in ("vehicle", "state", "rider", "t0", "t1", "dist_m", "path", "ts")}
    xmin = ymin = math.inf
    xmax = ymax = -math.inf
    shift: Dict[int, List[float]] = {}
    n_points = 0
    for s in segs:
        path: List[float] = []
        ts: List[float] = []
        for x, y, t in zip(s["xs"], s["ys"], s["ts"]):
            x, y, t = _r(x, nd), _r(y, nd), _r(t, 1)
            if path and path[-2] == x and path[-1] == y and ts[-1] == t:
                continue                       # identical after rounding
            path += [x, y]
            ts.append(t)
            xmin, xmax, ymin, ymax = min(xmin, x), max(xmax, x), min(ymin, y), max(ymax, y)
        n_points += len(ts)
        t0, t1 = _r(s["t0"], 1), _r(s["t1"], 1)
        trips["vehicle"].append(s["vehicle"])
        trips["state"].append(s["state"])
        trips["rider"].append(s["rider"])
        trips["t0"].append(t0)
        trips["t1"].append(t1)
        trips["dist_m"].append(_r(s["dist_m"], 1))
        trips["path"].append(path)
        trips["ts"].append(ts)
        sh = shift.setdefault(s["vehicle"], [t0, t1])
        sh[0], sh[1] = min(sh[0], t0), max(sh[1], t1)

    vehicles = [{"id": v["id"], "fleet": v.get("fleet"), "vehicle_type": v.get("vehicle_type"),
                 "group": v.get("group"), "seats": v.get("seats"), "shift": shift[v["id"]]}
                for v in inp.vehicles if v["id"] in shift]

    events: Dict[str, list] = {k: [] for k in ("t", "type", "rider", "vehicle", "lon", "lat", "to_lon", "to_lat",
                                               "eta")}
    for t, ev, rid, did, info in inp.events:
        typ = EVENT_MAP.get(ev)
        if typ is None or rid is None or rid not in inp.riders:
            continue
        ox, oy, dx, dy = inp.riders[rid]
        x, y = (dx, dy) if typ == "dropoff" else (ox, oy)
        events["t"].append(_r(t, 1))
        events["type"].append(typ)
        events["rider"].append(rid)
        events["vehicle"].append(did)
        events["lon"].append(_r(x, nd))
        events["lat"].append(_r(y, nd))
        events["to_lon"].append(_r(dx, nd) if typ == "request" else None)
        events["to_lat"].append(_r(dy, nd) if typ == "request" else None)
        eta = info.get("eta") if typ == "matched" else None
        events["eta"].append(None if eta is None else _r(t + eta, 1))      # promised pick-up time (absolute)

    cols = [c for c in (inp.metrics[0] if inp.metrics else {}) if c != "t"]
    metrics = {"interval_s": inp.metrics_interval_s, "t": [r["t"] for r in inp.metrics],
               "series": {c: [_clean(r.get(c)) for r in inp.metrics] for c in cols}}

    bounds = [xmin, ymin, xmax, ymax] if n_points else None
    if area is None and bounds:
        area = {"name": inp.run.get("scenario") or "run", "bbox": bounds}
    if area is not None:
        area = dict(area)
        x0, y0, x1, y1 = area["bbox"]
        area.setdefault("center", [_r((x0 + x1) / 2, nd), _r((y0 + y1) / 2, nd)])
        if inp.coords == "lonlat":
            area.setdefault("zoom", _fit_zoom(area["bbox"]))
    fleets: Dict[str, int] = {}
    for v in vehicles:
        name = "default" if v["fleet"] is None else str(v["fleet"])
        fleets[name] = fleets.get(name, 0) + 1
    t_lo = min((v["shift"][0] for v in vehicles), default=_r(inp.t_start, 1))
    t_hi = max((v["shift"][1] for v in vehicles), default=_r(inp.t_end, 1))
    import kami

    manifest = {
        "schema_version": SCHEMA_VERSION, "kind": KIND, "kami_version": kami.__version__,
        "run": dict(inp.run), "coords": inp.coords, "area": area, "bounds": bounds,
        "time": {"start": t_lo, "end": t_hi, "scenario_start": _r(inp.t_start, 1)},
        "states": STATES, "fleets": fleets,
        "counts": {"vehicles": len(vehicles), "segments": len(segs), "points": n_points,
                   "events": len(events["t"]), "metric_rows": len(metrics["t"])},
        "simplify": {"dist_m": params.dist_m, "dt_s": params.dt_s},
    }
    if inp.shared is not None:
        manifest["shared"] = inp.shared
    return {"manifest": manifest, "vehicles": vehicles, "trips": trips, "events": events, "metrics": metrics}


def _clean(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _fit_zoom(bbox, width_px: float = 1280.0, height_px: float = 800.0) -> float:
    x0, y0, x1, y1 = bbox
    lon_span = max(x1 - x0, 1e-6)
    lat_rad = math.radians((y0 + y1) / 2)
    lat_span = max((y1 - y0) / math.cos(lat_rad), 1e-6)
    z = min(math.log2(360.0 * width_px / (512.0 * lon_span)), math.log2(360.0 * height_px / (512.0 * lat_span)))
    return round(z, 2)


# ---------------------------------------------------------------------------- writing
def _dump(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def _gzip(raw: bytes) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=9) as f:
        f.write(raw)
    return buf.getvalue()


def write(docs: Dict[str, Any], out_dir: PathLike, compress: bool = True) -> Path:
    """Write the documents of ``tables`` into ``out_dir`` (replacing older replay files there)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in FILES:
        for old in (out / f"{name}.json", out / f"{name}.json.gz"):
            if old.exists():
                old.unlink()
        raw = _dump(docs[name])
        fname = f"{name}.json.gz" if compress else f"{name}.json"
        data = _gzip(raw) if compress else raw
        (out / fname).write_bytes(data)
        files[name] = {"path": fname, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                       "raw_bytes": len(raw)}
    manifest = dict(docs["manifest"], files=files)
    (out / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8")
    return out


def export(source, out_dir: PathLike, area: Optional[Dict[str, Any]] = None,
           simplify_params: SimplifyParams = SimplifyParams(), compress: bool = True,
           run: Optional[Dict[str, Any]] = None) -> Path:
    """Export a finished ``Simulation`` (or a ``ReplayInput``) to a replay folder; returns the folder."""
    inp = source if isinstance(source, ReplayInput) else from_simulation(source, run)
    if run and isinstance(source, ReplayInput):
        inp.run.update(run)
    return write(tables(inp, simplify_params, area), out_dir, compress)


def spec_sha256(spec) -> str:
    """sha256 of a resolved RunSpec's canonical JSON."""
    return hashlib.sha256(json.dumps(spec.to_dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def area_of(bbox: Iterable[float], name: str) -> Dict[str, Any]:
    return {"name": name, "bbox": [float(x) for x in bbox]}
