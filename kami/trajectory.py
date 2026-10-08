"""Vehicle trajectories (sprint 02, S02-6, decision D14).

With ``SimConfig.record_trajectories`` the engine hands every finished leg (arrived, or cut short by a re-plan /
re-time / shift end) to a ``TrajectoryRecorder``. A leg trace is the route the engine used to place the vehicle
(``Leg.path``) with the time the vehicle passes each node: node times are interpolated along the route's cumulative
base travel time between departure and arrival, so the last node of a full leg is reached exactly at the leg's
arrival event (``ARRIVE_STOP`` → ``PICKUP`` / ``DROPOFF``). A cut leg ends at the last node passed before the cut,
which is where the engine continues from.

Recording only reads the engine state: a run gives the same results with and without it.

Export: ``save(path)`` writes one Parquet row per leg (needs ``pyarrow``) with node ids, node times, node lon/lat and
an expanded polyline (``path_lon``, ``path_lat``, ``path_t``) that follows ``edge_geometry.csv`` when the network has
it — the format of deck.gl's ``TripsLayer``. Networks without lon/lat (synthetic grid) store planar x/y in the lon/lat
columns (schema metadata ``kami.coords = "xy"``).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from kami.network.base import Network


@dataclass
class LegTrace:
    driver_id: int
    leg_seq: int
    purpose: str                  # "stop" | "idle" | "reposition"
    occupied: bool
    rider_id: Optional[int]
    group: str
    t_depart: float
    t_end: float                  # arrival, or the time the leg was cut
    cut: bool
    nodes: List[int]
    times: List[float]


def trace(leg, t_end: float, frac: Optional[float]) -> Tuple[List[int], List[float]]:
    """Nodes reached and their times; ``frac`` (share of the leg driven) for a cut leg, None for a full leg.

    The cut rule is the one of ``Simulation._leg_position`` (last node whose share of the route time ≤ ``frac``).
    """
    path = leg.path
    total = path[-1][1] or 1.0
    span = leg.t_arrive - leg.t_depart
    t0 = leg.t_depart
    if frac is None:
        nodes = [n for n, _ in path]
        times = [t0 + cum / total * span for _, cum in path]
        times[-1] = leg.t_arrive
        if len(times) == 1:
            times[0] = leg.t_arrive
        return nodes, times
    nodes, times = [], []
    if t_end <= leg.t_depart:
        return [leg.origin], [t_end]
    for n, cum in path:
        if cum / total <= frac:
            nodes.append(n)
            times.append(min(t0 + cum / total * span, t_end))
        else:
            break
    return nodes, times


class TrajectoryRecorder:
    """Collects ``LegTrace`` records during a run (``sim.trajectories``)."""

    def __init__(self, network: Network):
        self.network = network
        self.legs: List[LegTrace] = []
        self._by_driver: Dict[int, List[int]] = {}

    def record(self, driver_id: int, leg_seq: int, leg, t_end: float, frac: Optional[float]) -> None:
        nodes, times = trace(leg, t_end, frac)
        self._by_driver.setdefault(driver_id, []).append(len(self.legs))
        self.legs.append(LegTrace(driver_id, leg_seq, leg.purpose, leg.occupied, leg.rider_id, leg.group,
                                  leg.t_depart, t_end if frac is not None else leg.t_arrive, frac is not None,
                                  nodes, times))

    def __len__(self) -> int:
        return len(self.legs)

    def drivers(self) -> List[int]:
        return sorted(self._by_driver)

    def legs_of(self, driver_id: int) -> List[LegTrace]:
        return [self.legs[i] for i in self._by_driver.get(driver_id, [])]

    # ------------------------------------------------------------------ geometry
    def _positions(self, nodes: Sequence[int]) -> Tuple[Dict[int, Tuple[float, float]], str]:
        uniq = sorted(set(nodes))
        net = self.network
        try:
            if hasattr(net, "lonlats"):
                return dict(zip(uniq, net.lonlats(uniq))), "lonlat"
            ll = [net.lonlat(n) for n in uniq]
            if uniq and ll[0] is not None:
                return dict(zip(uniq, ll)), "lonlat"
        except (ImportError, ValueError):       # road network without lon/lat columns and without pyproj
            pass
        return {n: net.coords(n) for n in uniq}, "xy"

    def _expand(self, t: LegTrace, pos: Dict[int, Tuple[float, float]], coords: str):
        """Polyline (following edge geometry) with interpolated times."""
        geom = getattr(self.network, "edge_geometry", None) if coords == "lonlat" else None
        xs, ys, ts = [], [], []
        nodes, times = t.nodes, t.times
        if not nodes:
            return xs, ys, ts
        x0, y0 = pos[nodes[0]]
        xs.append(x0), ys.append(y0), ts.append(times[0])
        for (a, b), ta, tb in zip(zip(nodes[:-1], nodes[1:]), times[:-1], times[1:]):
            pts = geom(a, b) if geom else None
            if not pts or len(pts) < 2:
                pts = [pos[a], pos[b]]
            seg = [_dist(p, q, coords) for p, q in zip(pts[:-1], pts[1:])]
            total = sum(seg) or 1.0
            acc = 0.0
            for (px, py), s in zip(pts[1:-1], seg[:-1]):
                acc += s
                xs.append(px), ys.append(py), ts.append(ta + (tb - ta) * acc / total)
            bx, by = pos[b]
            xs.append(bx), ys.append(by), ts.append(tb)
        return xs, ys, ts

    def of(self, driver_id: int, geometry: bool = True) -> List[Tuple[float, float, float]]:
        """Trajectory of a driver as ``[(lon, lat, t)]`` (``(x, y, t)`` on networks without lon/lat)."""
        legs = sorted(self.legs_of(driver_id), key=lambda t: t.leg_seq)
        pos, coords = self._positions([n for t in legs for n in t.nodes])
        out: List[Tuple[float, float, float]] = []
        for t in legs:
            if geometry:
                xs, ys, ts = self._expand(t, pos, coords)
                out.extend(zip(xs, ys, ts))
            else:
                out.extend((pos[n][0], pos[n][1], tt) for n, tt in zip(t.nodes, t.times))
        return out

    # ------------------------------------------------------------------ export
    def rows(self, geometry: bool = True) -> Tuple[List[Dict[str, Any]], str]:
        """One dict per leg (Parquet columns) and the coordinate kind (``"lonlat"`` or ``"xy"``)."""
        pos, coords = self._positions([n for t in self.legs for n in t.nodes])
        rows = []
        for t in self.legs:
            row = {"driver_id": t.driver_id, "leg_seq": t.leg_seq, "purpose": t.purpose, "occupied": t.occupied,
                   "rider_id": t.rider_id, "group": t.group, "t_depart": t.t_depart, "t_end": t.t_end,
                   "cut": t.cut, "nodes": list(t.nodes), "times": list(t.times),
                   "lon": [pos[n][0] for n in t.nodes], "lat": [pos[n][1] for n in t.nodes]}
            if geometry:
                xs, ys, ts = self._expand(t, pos, coords)
                row.update(path_lon=xs, path_lat=ys, path_t=ts)
            rows.append(row)
        return rows, coords

    def save(self, path: Union[str, Path], geometry: bool = True) -> Path:
        """Write ``trajectories.parquet`` (one row per leg)."""
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as e:
            from kami.eventlog import PARQUET_HINT

            raise ImportError(PARQUET_HINT) from e
        rows, coords = self.rows(geometry)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        f64, i64 = pa.float64(), pa.int64()
        fields = [("driver_id", i64), ("leg_seq", i64), ("purpose", pa.string()), ("occupied", pa.bool_()),
                  ("rider_id", i64), ("group", pa.string()), ("t_depart", f64), ("t_end", f64), ("cut", pa.bool_()),
                  ("nodes", pa.list_(i64)), ("times", pa.list_(f64)), ("lon", pa.list_(f64)),
                  ("lat", pa.list_(f64))]
        if geometry:
            fields += [("path_lon", pa.list_(f64)), ("path_lat", pa.list_(f64)), ("path_t", pa.list_(f64))]
        schema = pa.schema(fields, metadata={"kami.coords": coords, "kami.network": getattr(self.network, "name", "")})
        table = pa.table({name: [r[name] for r in rows] for name, _ in fields}, schema=schema)
        pq.write_table(table, path)
        return path


def load(path: Union[str, Path]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Rows of a ``trajectories.parquet`` file and its metadata (``coords``, ``network``)."""
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    meta = {k.decode().replace("kami.", ""): v.decode() for k, v in (table.schema.metadata or {}).items()
            if k.decode().startswith("kami.")}
    return table.to_pylist(), meta


def _dist(p, q, coords: str) -> float:
    if coords == "xy":
        return math.hypot(p[0] - q[0], p[1] - q[1])
    kx = math.cos(math.radians((p[1] + q[1]) / 2))
    return math.hypot((p[0] - q[0]) * kx, p[1] - q[1]) * 111_320.0
