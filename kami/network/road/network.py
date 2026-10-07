"""``RoadNetwork``: kami ``Network`` on a real road graph (OSM-derived network folder).

Routing runs on the C++ Dijkstra router when its extension is built (``python -m kami.network.road.cpp.build``),
otherwise on the pure-Python router; both give the same routes. Network folders use the FleetPy layout
(``<data_root>/networks/<name>/base/{nodes,edges}.csv``, see ``kami.network.road.graph``); the code is a port of
FleetPy's ``NetworkBasic`` / ``NetworkBasicCpp`` (MIT licence, TUM-VT), no FleetPy installation is needed.

Incidents enter routing as a per-node cost multiplier. With the C++ backend they are applied to a *second* C++ router
("live" state) through ``updateEdgeTravelTimes``, so the platform's free-flow view and the real incident-aware state
coexist and both stay fast; with the Python backend they go through the router's cost function.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from kami.network.base import Network, NodeFactor, SpatialIndex
from kami.network.road.graph import RoadGraph
from kami.network.road.router import Router

PathLike = Union[str, os.PathLike]


def default_data_root() -> Path:
    """``$KAMI_DATA_ROOT`` if set, else the ``data/`` folder next to the ``kami`` package."""
    env = os.environ.get("KAMI_DATA_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "data"


def resolve_data_root(data_root: Optional[PathLike] = None, fleetpy_root: Optional[PathLike] = None) -> Path:
    """Data root from the arguments; ``fleetpy_root`` (kami 0.1 API) points at a folder that *contains* ``data/``."""
    if data_root is not None:
        return Path(data_root)
    if fleetpy_root is not None:
        return Path(fleetpy_root) / "data"
    return default_data_root()


def network_path(network: PathLike, data_root: Optional[PathLike] = None,
                 fleetpy_root: Optional[PathLike] = None) -> Path:
    """Network folder: ``network`` itself if it is a folder with ``base/nodes.csv``, else ``<data_root>/networks/<network>``."""
    p = Path(network)
    if (p / "base" / "nodes.csv").exists():
        return p
    p = resolve_data_root(data_root, fleetpy_root) / "networks" / str(network)
    if not (p / "base" / "nodes.csv").exists():
        raise FileNotFoundError(f"road network not found: {p} (set KAMI_DATA_ROOT or pass data_root=...)")
    return p


def _cpp_router():
    from kami.network.road.cpp import PyNetwork

    return PyNetwork


class RoadNetwork(Network):
    """kami ``Network`` backed by a road graph.

    :param network_name: network name under ``<data_root>/networks`` or path of a network folder
    :param data_root: data folder (default ``$KAMI_DATA_ROOT`` or ``<repo>/data``)
    :param network_dynamics_file: optional travel-time dynamics file in the network folder
    :param scenario_time: apply the travel-time set in force at this time when loading
    :param backend: ``"auto"`` (C++ router if built, else Python), ``"cpp"`` or ``"python"``
    :param fleetpy_root: kami 0.1 compatibility — folder containing ``data/`` (same as ``data_root=<folder>/data``)
    """

    def __init__(self, network_name: PathLike = "example_network", data_root: Optional[PathLike] = None,
                 network_dynamics_file: Optional[str] = None, scenario_time: Optional[int] = None,
                 cache_size: int = 200_000, backend: str = "auto", fleetpy_root: Optional[PathLike] = None):
        if backend not in ("auto", "cpp", "python"):
            raise ValueError(f"backend must be auto | cpp | python, got {backend!r}")
        self.network_dir = network_path(network_name, data_root, fleetpy_root)
        self.name = self.network_dir.name
        self.data_root = self.network_dir.parent.parent
        self.graph = RoadGraph(self.network_dir, network_dynamics_file)
        self.router = Router(self.graph)
        self._cpp = None
        if backend in ("auto", "cpp"):
            cls = _cpp_router()
            if cls is None and backend == "cpp":
                raise ImportError("C++ road router not built: run `python -m kami.network.road.cpp.build`")
            if cls is not None:
                base = self.network_dir / "base"
                self._cpp = cls(str(base / "nodes.csv"), str(base / "edges.csv"))
        self.backend = "cpp" if self._cpp is not None else "python"
        if scenario_time is not None and self.graph.tt_sources:
            latest = self.graph.latest_tt_time(scenario_time)
            if latest is not None:
                self._load_tt(latest)

        self._live = None                       # second C++ router holding incident travel times
        self._live_edges: Dict[Tuple[int, int], float] = {}
        self._live_factor: Dict[int, float] = {}
        self._live_cache: Dict[Tuple[int, int], Tuple[float, float]] = {}
        g = self.graph
        self._coords: Dict[int, Tuple[float, float]] = {n: (g.x[n], g.y[n]) for n in range(len(g))}
        self._index = SpatialIndex(self._coords, cell=250.0)
        self._cache: Dict[Tuple[int, int], Tuple[float, float]] = {}
        self._cache_size = cache_size
        xs = g.x
        ys = g.y
        self._bounds = (min(xs), min(ys), max(xs), max(ys))
        # random locations: largest strongly connected component, excluding stop-only nodes
        scc = self._main_scc()
        self._locations = sorted(n for n in range(len(g)) if n in scc and not g.stop_only[n])
        self._loc_index = SpatialIndex({n: self._coords[n] for n in self._locations}, cell=250.0)
        self._scc = scc

    # ------------------------------------------------------------------ structure
    def _main_scc(self) -> set:
        """Strongly connected component around the network centre (forward ∩ backward reachability)."""
        n_nodes = len(self.graph)
        x0, y0, x1, y1 = self._bounds
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        order = sorted(range(n_nodes), key=lambda n: (self._coords[n][0] - cx) ** 2 + (self._coords[n][1] - cy) ** 2)
        best: set = set()
        for seed in order[:20]:
            if seed in best:
                continue
            comp = self._reach(seed, forward=True) & self._reach(seed, forward=False)
            if len(comp) > len(best):
                best = comp
            if len(best) > 0.5 * n_nodes:
                break
        return best

    def _reach(self, start: int, forward: bool) -> set:
        edges = self.graph.out_edges if forward else self.graph.in_edges
        stop = self.graph.stop_only
        seen = {start}
        stack = [start]
        while stack:
            n = stack.pop()
            for other in edges[n]:
                if other not in seen and not (stop[other] and other != start):
                    seen.add(other)
                    stack.append(other)
        return seen

    def num_nodes(self) -> int:
        return len(self.graph)

    def location_nodes(self):
        return self._locations

    def coords(self, node: int) -> Tuple[float, float]:
        return self._coords[node]

    def lonlat(self, node: int):
        return self.graph.lonlat([node])[0]

    def nearest_node(self, x: float, y: float) -> int:
        """Nearest *location* node (connected, not stop-only)."""
        return self._loc_index.nearest(x, y)

    def within(self, node: int, radius_m: float) -> List[int]:
        x, y = self.coords(node)
        return self._index.within(x, y, radius_m)

    def bounds(self):
        return self._bounds

    # ------------------------------------------------------------------ routing
    @staticmethod
    def _cost_fn(node_factor: NodeFactor):
        if node_factor is None:
            return None
        return lambda tt, dis, node: tt * node_factor(node)

    def _travel_1to1(self, o: int, d: int, node_factor: NodeFactor) -> Tuple[float, float]:
        """(cost, distance); cost is the travel time unless ``node_factor`` is given. inf if unreachable."""
        f = self.graph.tt_factor
        if self._cpp is not None and node_factor is None:
            tt, dist = self._cpp.computeTravelCosts1To1(o, d)
            if f is not None:
                tt *= f
            if tt < -0.001:
                return float("inf"), float("inf")
            return tt, dist
        cost, _route = self.router.one_to_one(o, d, self._cost_fn(node_factor))
        if f is not None:
            return cost[0] * f, cost[2]
        return cost[0], cost[2]

    def base_travel(self, o: int, d: int, node_factor: NodeFactor = None) -> Tuple[float, float]:
        if o == d:
            return 0.0, 0.0
        if node_factor is None:
            hit = self._cache.get((o, d))
            if hit is not None:
                return hit
        cost, dist = self._travel_1to1(o, d, node_factor)
        if not (float(cost) < float("inf")) or float(cost) <= 0:
            res = self._fallback(o, d)
        else:
            res = (float(cost), float(dist))
        if node_factor is None:
            if len(self._cache) >= self._cache_size:
                self._cache.clear()
            self._cache[(o, d)] = res
        return res

    def _travel_xto1(self, origins: List[int], d: int, max_tt: Optional[float],
                     node_factor: NodeFactor) -> List[Tuple[int, float, float]]:
        f = self.graph.tt_factor
        radius = max_tt / f if (max_tt is not None and f is not None) else max_tt
        out = []
        if self._cpp is not None and node_factor is None:
            for o, tt, dist in self._cpp.computeTravelCostsXto1(d, origins, max_time_range=radius):
                if f is not None:
                    tt *= f
                if tt < -0.0001 or (max_tt is not None and tt > max_tt):
                    continue
                out.append((o, tt, dist))
            return out
        for o, (cost, _tt, dist), _ in self.router.search(d, origins, forward=False, radius=radius,
                                                          fn=self._cost_fn(node_factor)):
            if f is not None:
                cost *= f
            if cost < 0 or cost == float("inf") or (max_tt is not None and cost > max_tt):
                continue
            out.append((o, cost, dist))
        return out

    def many_to_one(self, origins: Sequence[int], d: int, node_factor: NodeFactor = None,
                    max_tt: Optional[float] = None) -> Dict[int, Tuple[float, float]]:
        out: Dict[int, Tuple[float, float]] = {}
        todo = []
        for o in set(origins):
            if o == d:
                out[o] = (0.0, 0.0)
            elif node_factor is None and (o, d) in self._cache:
                tt, dist = self._cache[(o, d)]
                if max_tt is None or tt <= max_tt:
                    out[o] = (tt, dist)
            else:
                todo.append(o)
        if todo:
            for o, cost, dist in self._travel_xto1(todo, d, max_tt, node_factor):
                out[o] = (float(cost), float(dist))
                if node_factor is None:
                    self._cache[(o, d)] = (float(cost), float(dist))
        return out

    def _fallback(self, o: int, d: int) -> Tuple[float, float]:
        """Unreachable pair (disconnected network part): crow-fly × 1.4 at 8 m/s."""
        dist = self.crow_dist(o, d) * 1.4
        return dist / 8.0, dist

    def _route(self, o: int, d: int, node_factor: NodeFactor) -> List[int]:
        if self._cpp is not None and node_factor is None:
            return self._cpp.computeRoute1To1(o, d)
        _cost, route = self.router.one_to_one(o, d, self._cost_fn(node_factor), with_route=True)
        return route or []

    def path(self, o: int, d: int, node_factor: NodeFactor = None) -> List[Tuple[int, float]]:
        if o == d:
            return [(o, 0.0)]
        route = self._route(o, d, node_factor)
        return self._timed(route, o, d, node_factor)

    def _timed(self, route: List[int], o: int, d: int, node_factor) -> List[Tuple[int, float]]:
        if len(route) < 2:
            return [(o, 0.0), (d, self._fallback(o, d)[0])]
        out, acc = [(route[0], 0.0)], 0.0
        for a, b in zip(route[:-1], route[1:]):
            try:
                tt, _dist = self.graph.section(a, b)
            except KeyError:
                return [(o, 0.0), (d, self._fallback(o, d)[0])]
            acc += tt * (node_factor(b) if node_factor else 1.0)
            out.append((b, acc))
        return out

    # ------------------------------------------------------------------ live (incident) state, C++ only
    @property
    def supports_live_factors(self) -> bool:
        return self.backend == "cpp"

    def _apply_tt_csv(self, router, changes: Dict[Tuple[int, int], float]) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("from_node,to_node,edge_tt\n")
            for (a, b), tt in changes.items():
                fh.write(f"{a},{b},{tt}\n")
            path = fh.name
        try:
            router.updateEdgeTravelTimes(path)
        finally:
            os.unlink(path)

    def apply_live_factors(self, node_factor: Dict[int, float]) -> None:
        """Set the incident multipliers of the live router (edges *entering* a node are slowed)."""
        if self._live is None:
            base = self.network_dir / "base"
            self._live = _cpp_router()(str(base / "nodes.csv"), str(base / "edges.csv"))
        changes: Dict[Tuple[int, int], float] = {}
        for (a, b) in list(self._live_edges):
            if b not in node_factor:          # restore edges no longer affected
                changes[(a, b)] = self.graph.section(a, b)[0]
                del self._live_edges[(a, b)]
        for b, f in node_factor.items():
            for a in self.graph.in_edges[b]:
                tt = self.graph.section(a, b)[0] * f
                if self._live_edges.get((a, b)) != tt:
                    changes[(a, b)] = tt
                    self._live_edges[(a, b)] = tt
        if changes:
            self._apply_tt_csv(self._live, changes)
        self._live_factor = dict(node_factor)
        self._live_cache.clear()

    def live_travel(self, o: int, d: int) -> Tuple[float, float]:
        if not self._live_factor:
            return self.base_travel(o, d)
        if o == d:
            return 0.0, 0.0
        hit = self._live_cache.get((o, d))
        if hit is None:
            tt, dist = self._live.computeTravelCosts1To1(o, d)
            hit = (tt, dist) if tt >= 0 else self._fallback(o, d)
            self._live_cache[(o, d)] = hit
        return hit

    def live_many_to_one(self, origins: Sequence[int], d: int, max_tt: Optional[float] = None):
        if not self._live_factor:
            return self.many_to_one(origins, d, None, max_tt)
        out = {o: (0.0, 0.0) for o in origins if o == d}
        rest = [o for o in set(origins) if o != d]
        if rest:
            for o, tt, dist in self._live.computeTravelCostsXto1(d, rest, max_time_range=max_tt):
                if tt >= 0:
                    out[o] = (tt, dist)
        return out

    def live_path(self, o: int, d: int) -> List[Tuple[int, float]]:
        if not self._live_factor:
            return self.path(o, d)
        if o == d:
            return [(o, 0.0)]
        route = list(self._live.computeRoute1To1(o, d))
        if len(route) < 2:
            return [(o, 0.0), (d, self._fallback(o, d)[0])]
        out, acc = [(route[0], 0.0)], 0.0
        for a, b in zip(route[:-1], route[1:]):
            try:
                tt, _ = self.graph.section(a, b)
            except KeyError:
                return [(o, 0.0), (d, self._fallback(o, d)[0])]
            acc += tt * self._live_factor.get(b, 1.0)
            out.append((b, acc))
        return out

    # ------------------------------------------------------------------ dynamic travel times
    def _load_tt(self, sim_time: int) -> None:
        self.graph.load_tt(sim_time)
        path = self.graph.tt_file(sim_time)
        if self._cpp is not None and path is not None:
            self._cpp.updateEdgeTravelTimes(str(path))

    def update_network(self, sim_time: float) -> bool:
        """Load the time-dependent travel times that start exactly at ``sim_time`` (if any)."""
        key = int(sim_time)
        if self.graph.tt_sources.get(key) is None:
            return False
        self._load_tt(key)
        self._cache.clear()
        return True
