"""Road graph read from a network folder (``<network>/base/{nodes,edges}.csv`` + ``crs.info``).

The folder layout is the one introduced by FleetPy (TUM-VT, MIT licence, see ``LICENSE-FleetPy``); this module is a
standard-library port of the parts of FleetPy's ``NetworkBasic`` that kami uses:

* ``nodes.csv``: ``node_index,is_stop_only,pos_x,pos_y`` — ``node_index`` must be ``0..N-1``; stop-only nodes can
  start or end a route but are never passed through;
* ``edges.csv``: ``from_node,to_node,distance,travel_time[,…]`` (metres, seconds);
* ``crs.info``: projected CRS of ``pos_x``/``pos_y`` (for lon/lat conversion, needs ``pyproj`` unless ``nodes.csv``
  has ``lon``/``lat`` columns);
* time-dependent travel times: numbered sub-folders ``<network>/<sim_time>/edges_td_att.csv``
  (``from_node,to_node,edge_tt``) or a *network dynamics file* with columns ``simulation_time`` and either
  ``travel_time_folder`` or ``travel_time_factor``.

kami extensions (optional files, ignored by FleetPy; see ``docs/engine/16-fleetpy-integration.md``):

* ``nodes.csv`` columns ``lon,lat`` (WGS84) — lon/lat without ``pyproj``;
* ``edge_attributes.csv``: ``from_node,to_node,road_class,allow_car,allow_bike[,…]`` — road class and vehicle-group
  restrictions per edge (missing file = every edge open to every group);
* ``edge_geometry.csv``: ``from_node,to_node,lons,lats`` (``;``-separated WGS84 polyline including both end nodes).
"""
from __future__ import annotations

import copy
import csv
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


def _bool(text: str) -> bool:
    return text.strip().lower() in ("1", "true", "1.0")


class RoadGraph:
    """Directed road graph with mutable edge travel times.

    ``out_edges[a][b]`` and ``in_edges[b][a]`` share one ``[travel_time, distance]`` list, so a travel-time update is
    seen from both sides. Neighbour iteration follows the row order of ``edges.csv`` (routing tie-breaks depend on it).
    """

    def __init__(self, network_dir: Union[str, os.PathLike], network_dynamics_file: Optional[str] = None):
        self.network_dir = Path(network_dir)
        base = self.network_dir / "base"
        self.x: List[float] = []
        self.y: List[float] = []
        self.stop_only: List[bool] = []
        self.lons: Optional[List[float]] = None
        self.lats: Optional[List[float]] = None
        with open(base / "nodes.csv", newline="") as f:
            reader = csv.DictReader(f)
            has_ll = "lon" in (reader.fieldnames or ()) and "lat" in (reader.fieldnames or ())
            lons, lats = [], []
            for i, row in enumerate(reader):
                if int(row["node_index"]) != i:
                    raise ValueError(f"{base / 'nodes.csv'}: node_index must be 0..N-1 in file order (row {i})")
                self.stop_only.append(_bool(row["is_stop_only"]))
                self.x.append(float(row["pos_x"]))
                self.y.append(float(row["pos_y"]))
                if has_ll:
                    lons.append(float(row["lon"]))
                    lats.append(float(row["lat"]))
            if has_ll:
                self.lons, self.lats = lons, lats
        n = len(self.x)
        self.out_edges: List[Dict[int, List[float]]] = [{} for _ in range(n)]
        self.in_edges: List[Dict[int, List[float]]] = [{} for _ in range(n)]
        self.edges: List[Tuple[int, int]] = []          # file order (duplicates keep the last row, like FleetPy)
        with open(base / "edges.csv", newline="") as f:
            for row in csv.DictReader(f):
                a, b = int(row["from_node"]), int(row["to_node"])
                e = [float(row["travel_time"]), float(row["distance"])]
                if b not in self.out_edges[a]:
                    self.edges.append((a, b))
                self.out_edges[a][b] = e
                self.in_edges[b][a] = e
        self.ff_tt: List[float] = [self.out_edges[a][b][0] for a, b in self.edges]   # travel times of edges.csv
        self.edge_index: Dict[Tuple[int, int], int] = {e: i for i, e in enumerate(self.edges)}
        self.road_class: Optional[List[str]] = None
        self.allow: Dict[str, List[bool]] = {}          # vehicle group -> allowed per edge (empty = all allowed)
        self._read_edge_attributes(base / "edge_attributes.csv")
        self._geometry_file = base / "edge_geometry.csv"
        self._geometry: Optional[Dict[Tuple[int, int], List[Tuple[float, float]]]] = None
        crs_file = base / "crs.info"
        self.crs = crs_file.read_text().strip() if crs_file.exists() else None
        self._to_lonlat = None
        self.tt_factor: Optional[float] = None          # set by a "travel_time_factor" dynamics file
        self._tt_from_folder = True
        self.tt_sources: Dict[int, Union[Path, float]] = self._dynamics(network_dynamics_file)

    def _read_edge_attributes(self, path: Path) -> None:
        if not path.exists():
            return
        classes: List[str] = [""] * len(self.edges)
        allow: Dict[str, List[bool]] = {}
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            groups = [c[len("allow_"):] for c in (reader.fieldnames or ()) if c.startswith("allow_")]
            for g in groups:
                allow[g] = [True] * len(self.edges)
            for row in reader:
                i = self.edge_index.get((int(row["from_node"]), int(row["to_node"])))
                if i is None:
                    continue
                classes[i] = row.get("road_class", "") or ""
                for g in groups:
                    allow[g][i] = _bool(row["allow_" + g])
        self.road_class = classes
        self.allow = {g: a for g, a in allow.items() if not all(a)}

    def clone(self) -> "RoadGraph":
        """Same structure, independent travel times (one per vehicle group)."""
        g = copy.copy(self)
        g.out_edges = [{b: list(e) for b, e in out.items()} for out in self.out_edges]
        # same in-edge iteration order as the original graph (routing tie-breaks depend on it)
        g.in_edges = [{a: g.out_edges[a][b] for a in self.in_edges[b]} for b in range(len(self.x))]
        return g

    def edge_geometry(self, a: int, b: int) -> Optional[List[Tuple[float, float]]]:
        """WGS84 polyline of edge ``a → b`` from ``edge_geometry.csv`` (None if the file or the edge is missing)."""
        if self._geometry is None:
            self._geometry = {}
            if self._geometry_file.exists():
                with open(self._geometry_file, newline="") as f:
                    for row in csv.DictReader(f):
                        lons = [float(v) for v in row["lons"].split(";")]
                        lats = [float(v) for v in row["lats"].split(";")]
                        self._geometry[(int(row["from_node"]), int(row["to_node"]))] = list(zip(lons, lats))
        return self._geometry.get((a, b))

    # ------------------------------------------------------------------ structure
    def __len__(self) -> int:
        return len(self.x)

    def coords(self, node: int) -> Tuple[float, float]:
        return self.x[node], self.y[node]

    def section(self, a: int, b: int) -> Tuple[float, float]:
        """``(travel_time, distance)`` of edge ``a → b`` (current travel times); ``KeyError`` if there is no edge."""
        tt, dist = self.out_edges[a][b]
        if self.tt_factor is not None:
            tt *= self.tt_factor
        return tt, dist

    def lonlat(self, nodes) -> List[Tuple[float, float]]:
        if self.lons is not None:
            return [(self.lons[n], self.lats[n]) for n in nodes]
        if self._to_lonlat is None:
            if not self.crs:
                raise ValueError(f"{self.network_dir}: no base/crs.info, lon/lat unavailable")
            from pyproj import Transformer

            self._to_lonlat = Transformer.from_crs(self.crs, "EPSG:4326", always_xy=True)
        xs = [self.x[n] for n in nodes]
        ys = [self.y[n] for n in nodes]
        lons, lats = self._to_lonlat.transform(xs, ys)
        return list(zip(lons, lats))

    # ------------------------------------------------------------------ dynamic travel times
    def _dynamics(self, dynamics_file: Optional[str]) -> Dict[int, Union[Path, float]]:
        sources: Dict[int, Union[Path, float]] = {}
        if dynamics_file is None:
            for p in self.network_dir.iterdir():
                if p.is_dir():
                    try:
                        sources[int(p.name)] = p
                    except ValueError:
                        continue
            return sources
        with open(self.network_dir / dynamics_file, newline="") as f:
            rows = list(csv.DictReader(f))
        cols = rows[0].keys() if rows else ()
        if "travel_time_folder" in cols:
            for r in rows:
                sources[int(float(r["simulation_time"]))] = self.network_dir / r["travel_time_folder"]
        elif "travel_time_factor" in cols:
            self._tt_from_folder = False
            for r in rows:
                sources[int(float(r["simulation_time"]))] = float(r["travel_time_factor"])
        return sources

    def latest_tt_time(self, sim_time: float) -> Optional[int]:
        """Start time of the travel-time set in force at ``sim_time`` (None if none starts before it)."""
        latest = None
        for t in sorted(self.tt_sources):
            if t > sim_time:
                break
            latest = t
        return latest

    def tt_file(self, sim_time: int) -> Optional[Path]:
        """Edge travel-time file that applies from ``sim_time`` (None for factor-based dynamics)."""
        src = self.tt_sources[sim_time]
        return Path(src) / "edges_td_att.csv" if self._tt_from_folder else None

    def load_tt(self, sim_time: int) -> None:
        """Apply the travel times registered for ``sim_time``."""
        path = self.tt_file(sim_time)
        if path is None:
            self.tt_factor = float(self.tt_sources[sim_time])
            return
        self.load_tt_csv(path)

    def load_tt_csv(self, path: Union[str, os.PathLike]) -> None:
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                self.out_edges[int(row["from_node"])][int(row["to_node"])][0] = float(row["edge_tt"])
