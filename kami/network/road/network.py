"""``RoadNetwork``: kami ``Network`` on a real road graph (OSM-derived network folder).

Routing runs on the C++ Dijkstra router when its extension is built (``python -m kami.network.road.cpp.build``),
otherwise on the pure-Python router; both give the same routes. Network folders use the FleetPy layout
(``<data_root>/networks/<name>/base/{nodes,edges}.csv``, see ``kami.network.road.graph``); the code is a port of
FleetPy's ``NetworkBasic`` / ``NetworkBasicCpp`` (MIT licence, TUM-VT), no FleetPy installation is needed.

Incidents enter routing as a per-node cost multiplier. With the C++ backend they are applied to a *second* C++ router
("live" state) through ``updateEdgeTravelTimes``, so the platform's free-flow view and the real incident-aware state
coexist and both stay fast; with the Python backend they go through the router's cost function.

Vehicle groups (sprint 02, decision D13): every group (``"car"``, ``"bike"``…) has its own router state — Python graph
copy, C++ router, cache and live router — so per-group edge travel times (speed factor, zone × hour congestion) and
per-group forbidden edges (``edge_attributes.csv``) keep the plain Dijkstra and the C++ speed. Group ``"car"`` *is* the
default state of kami 0.1 (``self.graph``, ``self._cpp``…); other groups are created on first use. Edge travel times
are set from the free-flow times of ``edges.csv`` with ``set_edge_factors`` (decision D10).
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from kami.network.base import Network, NodeFactor, SpatialIndex
from kami.network.road.graph import RoadGraph
from kami.network.road.router import Router

PathLike = Union[str, os.PathLike]
DEFAULT_GROUP = "car"
FORBIDDEN_TT = 1e7       # travel time given to an edge a vehicle group may not use
UNREACHABLE_TT = 1e6     # routes at least this long went through a forbidden edge: treated as "no route"


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


class _GroupState:
    """Router state of one non-default vehicle group (same attribute names as the default state on ``RoadNetwork``)."""

    def __init__(self, graph: RoadGraph, cpp):
        self.graph = graph
        self.router = Router(graph)
        self._cpp = cpp
        self._cache: Dict[Tuple[int, int], Tuple[float, float]] = {}
        self._live = None
        self._live_edges: Dict[Tuple[int, int], float] = {}
        self._live_factor: Dict[int, float] = {}
        self._live_cache: Dict[Tuple[int, int], Tuple[float, float]] = {}
        self._factors: Optional[List[float]] = None


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
        self._groups: Dict[str, _GroupState] = {}
        if scenario_time is not None and self.graph.tt_sources:
            latest = self.graph.latest_tt_time(scenario_time)
            if latest is not None:
                self._load_tt(latest)

        self._live = None                       # second C++ router holding incident travel times
        self._live_edges: Dict[Tuple[int, int], float] = {}
        self._live_factor: Dict[int, float] = {}
        self._live_cache: Dict[Tuple[int, int], Tuple[float, float]] = {}
        self._factors: Optional[List[float]] = None    # edge factors of the default group (None = free flow)
        g = self.graph
        self._coords: Dict[int, Tuple[float, float]] = {n: (g.x[n], g.y[n]) for n in range(len(g))}
        self._index = SpatialIndex(self._coords, cell=250.0)
        self._cache: Dict[Tuple[int, int], Tuple[float, float]] = {}
        self._cache_size = cache_size
        if DEFAULT_GROUP in g.allow:            # edges closed to cars (edge_attributes.csv)
            self._set_times(self, self._group_times(DEFAULT_GROUP, None))
        xs = g.x
        ys = g.y
        self._bounds = (min(xs), min(ys), max(xs), max(ys))
        # random locations: largest strongly connected component, excluding stop-only nodes
        scc = self._main_scc()
        for allowed in g.allow.values():        # with group restrictions: reachable by every group
            scc = scc & self._main_scc(allowed)
        self._locations = sorted(n for n in range(len(g)) if n in scc and not g.stop_only[n])
        self._loc_index = SpatialIndex({n: self._coords[n] for n in self._locations}, cell=250.0)
        self._scc = scc

    # ------------------------------------------------------------------ structure
    def _main_scc(self, allowed: Optional[List[bool]] = None) -> set:
        """Strongly connected component around the network centre (forward ∩ backward reachability).

        ``allowed`` (per edge of ``graph.edges``) restricts the search to the edges a vehicle group may use.
        """
        n_nodes = len(self.graph)
        x0, y0, x1, y1 = self._bounds
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        order = sorted(range(n_nodes), key=lambda n: (self._coords[n][0] - cx) ** 2 + (self._coords[n][1] - cy) ** 2)
        best: set = set()
        for seed in order[:20]:
            if seed in best:
                continue
            comp = self._reach(seed, True, allowed) & self._reach(seed, False, allowed)
            if len(comp) > len(best):
                best = comp
            if len(best) > 0.5 * n_nodes:
                break
        return best

    def _reach(self, start: int, forward: bool, allowed: Optional[List[bool]] = None) -> set:
        edges = self.graph.out_edges if forward else self.graph.in_edges
        stop = self.graph.stop_only
        index = self.graph.edge_index
        seen = {start}
        stack = [start]
        while stack:
            n = stack.pop()
            for other in edges[n]:
                if other not in seen and not (stop[other] and other != start):
                    if allowed is not None and not allowed[index[(n, other) if forward else (other, n)]]:
                        continue
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

    def lonlats(self, nodes: Iterable[int]) -> List[Tuple[float, float]]:
        """(lon, lat) of many nodes in one call."""
        return self.graph.lonlat(list(nodes))

    def node_at_lonlat(self, lon: float, lat: float) -> int:
        """Nearest location node to a WGS84 point."""
        g = self.graph
        if g.lons is None:
            from kami.scenario import _lonlat_transformer

            return self.nearest_node(*_lonlat_transformer(self)(lon, lat))
        kx = math.cos(math.radians(lat))
        return min(self._locations, key=lambda n: ((g.lons[n] - lon) * kx) ** 2 + (g.lats[n] - lat) ** 2)

    def edge_geometry(self, a: int, b: int) -> Optional[List[Tuple[float, float]]]:
        """WGS84 polyline of edge ``a → b`` (both end nodes included); straight segment without geometry file."""
        geom = self.graph.edge_geometry(a, b)
        if geom is not None:
            return geom
        if self.graph.lons is None and not self.graph.crs:
            return None
        return self.graph.lonlat([a, b])

    def nearest_node(self, x: float, y: float) -> int:
        """Nearest *location* node (connected, not stop-only)."""
        return self._loc_index.nearest(x, y)

    def within(self, node: int, radius_m: float) -> List[int]:
        x, y = self.coords(node)
        return self._index.within(x, y, radius_m)

    def bounds(self):
        return self._bounds

    # ------------------------------------------------------------------ vehicle groups
    supports_groups = True

    def _st(self, group: str):
        """Router state of ``group`` (the network itself for the default group); created on first use."""
        if group == DEFAULT_GROUP:
            return self
        st = self._groups.get(group)
        if st is None:
            cpp = None
            if self._cpp is not None:
                base = self.network_dir / "base"
                cpp = _cpp_router()(str(base / "nodes.csv"), str(base / "edges.csv"))
            st = self._groups[group] = _GroupState(self.graph.clone(), cpp)
            st.graph.tt_factor = self.graph.tt_factor
            times = self._group_times(group, None)
            if times != self.graph.ff_tt:
                self._set_times(st, times)
        return st

    def groups(self) -> List[str]:
        """Vehicle groups with a router state."""
        return [DEFAULT_GROUP] + list(self._groups)

    def edge_list(self) -> List[Tuple[int, int]]:
        """Edges ``(from, to)`` in ``edges.csv`` order — the order of ``set_edge_factors`` vectors."""
        return self.graph.edges

    def edge_road_class(self) -> Optional[List[str]]:
        """OSM road class per edge (``edge_attributes.csv``), None if unknown."""
        return self.graph.road_class

    def edge_allowed(self, group: str) -> Optional[List[bool]]:
        """Per-edge permission of ``group`` (None = every edge allowed)."""
        return self.graph.allow.get(group)

    def _group_times(self, group: str, factors: Optional[Sequence[float]]) -> List[float]:
        ff = self.graph.ff_tt
        times = list(ff) if factors is None else [t * f for t, f in zip(ff, factors)]
        allowed = self.graph.allow.get(group)
        if allowed is not None:
            for i, ok in enumerate(allowed):
                if not ok:
                    times[i] = FORBIDDEN_TT
        return times

    def _set_times(self, st, times: List[float]) -> None:
        """Write edge travel times into the Python graph and the C++ router(s) of a group state."""
        g = st.graph
        out = g.out_edges
        changed_a, changed_b, changed_t = [], [], []
        for (a, b), tt in zip(self.graph.edges, times):
            e = out[a][b]
            if e[0] != tt:
                e[0] = tt
                changed_a.append(a)
                changed_b.append(b)
                changed_t.append(tt)
        if st._cpp is not None and changed_a:
            st._cpp.setEdgeTravelTimes(changed_a, changed_b, changed_t)
        st._cache.clear()
        if st._live is not None:
            self._sync_live(st)

    def set_edge_factors(self, group: str, factors: Optional[Sequence[float]]) -> None:
        """Edge travel times of ``group`` = free-flow time (``edges.csv``) × ``factors[i]`` (aligned with ``edge_list``).

        ``None`` restores free flow. Edges the group may not use stay closed. Incident (live) factors are kept.
        """
        if factors is not None and len(factors) != len(self.graph.edges):
            raise ValueError(f"need {len(self.graph.edges)} edge factors, got {len(factors)}")
        st = self._st(group)
        if factors is None and st._factors is None:
            return
        st._factors = None if factors is None else list(factors)
        self._set_times(st, self._group_times(group, factors))

    def reset_groups(self) -> None:
        """Every group back to free flow, no incident factors (a fresh ``TrafficLayer`` starts from here)."""
        for group in self.groups():
            st = self._st(group)
            if st._live_factor:
                self.apply_live_factors({}, group)
            self.set_edge_factors(group, None)

    # ------------------------------------------------------------------ routing
    @staticmethod
    def _cost_fn(node_factor: NodeFactor):
        if node_factor is None:
            return None
        return lambda tt, dis, node: tt * node_factor(node)

    def _travel_1to1(self, st, o: int, d: int, node_factor: NodeFactor) -> Tuple[float, float]:
        """(cost, distance); cost is the travel time unless ``node_factor`` is given. inf if unreachable."""
        f = st.graph.tt_factor
        if st._cpp is not None and node_factor is None:
            tt, dist = st._cpp.computeTravelCosts1To1(o, d)
            if f is not None:
                tt *= f
            if tt < -0.001 or tt >= UNREACHABLE_TT:
                return float("inf"), float("inf")
            return tt, dist
        cost, _route = st.router.one_to_one(o, d, self._cost_fn(node_factor))
        if cost[0] >= UNREACHABLE_TT:
            return float("inf"), float("inf")
        if f is not None:
            return cost[0] * f, cost[2]
        return cost[0], cost[2]

    def base_travel(self, o: int, d: int, node_factor: NodeFactor = None,
                    group: str = DEFAULT_GROUP) -> Tuple[float, float]:
        if o == d:
            return 0.0, 0.0
        st = self._st(group)
        if node_factor is None:
            hit = st._cache.get((o, d))
            if hit is not None:
                return hit
        cost, dist = self._travel_1to1(st, o, d, node_factor)
        if not (float(cost) < float("inf")) or float(cost) <= 0:
            res = self._fallback(o, d)
        else:
            res = (float(cost), float(dist))
        if node_factor is None:
            if len(st._cache) >= self._cache_size:
                st._cache.clear()
            st._cache[(o, d)] = res
        return res

    def _travel_xto1(self, st, origins: List[int], d: int, max_tt: Optional[float],
                     node_factor: NodeFactor) -> List[Tuple[int, float, float]]:
        f = st.graph.tt_factor
        radius = max_tt / f if (max_tt is not None and f is not None) else max_tt
        out = []
        if st._cpp is not None and node_factor is None:
            for o, tt, dist in st._cpp.computeTravelCostsXto1(d, origins, max_time_range=radius):
                if f is not None:
                    tt *= f
                if tt < -0.0001 or (max_tt is not None and tt > max_tt) or tt >= UNREACHABLE_TT:
                    continue
                out.append((o, tt, dist))
            return out
        for o, (cost, _tt, dist), _ in st.router.search(d, origins, forward=False, radius=radius,
                                                        fn=self._cost_fn(node_factor)):
            if f is not None:
                cost *= f
            if cost < 0 or cost >= UNREACHABLE_TT or (max_tt is not None and cost > max_tt):
                continue
            out.append((o, cost, dist))
        return out

    def many_to_one(self, origins: Sequence[int], d: int, node_factor: NodeFactor = None,
                    max_tt: Optional[float] = None, group: str = DEFAULT_GROUP) -> Dict[int, Tuple[float, float]]:
        st = self._st(group)
        cache = st._cache
        out: Dict[int, Tuple[float, float]] = {}
        todo = []
        for o in set(origins):
            if o == d:
                out[o] = (0.0, 0.0)
            elif node_factor is None and (o, d) in cache:
                tt, dist = cache[(o, d)]
                if max_tt is None or tt <= max_tt:
                    out[o] = (tt, dist)
            else:
                todo.append(o)
        if todo:
            for o, cost, dist in self._travel_xto1(st, todo, d, max_tt, node_factor):
                out[o] = (float(cost), float(dist))
                if node_factor is None:
                    cache[(o, d)] = (float(cost), float(dist))
        return out

    def _fallback(self, o: int, d: int) -> Tuple[float, float]:
        """Unreachable pair (disconnected network part): crow-fly × 1.4 at 8 m/s."""
        dist = self.crow_dist(o, d) * 1.4
        return dist / 8.0, dist

    def _route(self, st, o: int, d: int, node_factor: NodeFactor) -> List[int]:
        if st._cpp is not None and node_factor is None:
            return st._cpp.computeRoute1To1(o, d)
        _cost, route = st.router.one_to_one(o, d, self._cost_fn(node_factor), with_route=True)
        return route or []

    def path(self, o: int, d: int, node_factor: NodeFactor = None,
             group: str = DEFAULT_GROUP) -> List[Tuple[int, float]]:
        if o == d:
            return [(o, 0.0)]
        st = self._st(group)
        route = self._route(st, o, d, node_factor)
        return self._timed(st, route, o, d, node_factor)

    def _timed(self, st, route: List[int], o: int, d: int, node_factor) -> List[Tuple[int, float]]:
        if len(route) < 2:
            return [(o, 0.0), (d, self._fallback(o, d)[0])]
        out, acc = [(route[0], 0.0)], 0.0
        section = st.graph.section
        for a, b in zip(route[:-1], route[1:]):
            try:
                tt, _dist = section(a, b)
            except KeyError:
                return [(o, 0.0), (d, self._fallback(o, d)[0])]
            acc += tt * (node_factor(b) if node_factor else 1.0)
            out.append((b, acc))
        if acc >= UNREACHABLE_TT:                # only possible through a forbidden edge
            return [(o, 0.0), (d, self._fallback(o, d)[0])]
        return out

    # ------------------------------------------------------------------ live (incident) state, C++ only
    @property
    def supports_live_factors(self) -> bool:
        return self.backend == "cpp"

    def _sync_live(self, st) -> None:
        """Live router of ``st`` = its current base travel times × incident factors (after a base change)."""
        out = st.graph.out_edges
        lf = st._live_factor
        a_s, b_s, t_s = [], [], []
        st._live_edges = {}
        for a, b in self.graph.edges:
            tt = out[a][b][0]
            f = lf.get(b)
            if f is not None:
                tt *= f
                st._live_edges[(a, b)] = tt
            a_s.append(a)
            b_s.append(b)
            t_s.append(tt)
        st._live.setEdgeTravelTimes(a_s, b_s, t_s)
        st._live_cache.clear()

    def apply_live_factors(self, node_factor: Dict[int, float], group: str = DEFAULT_GROUP) -> None:
        """Set the incident multipliers of the live router (edges *entering* a node are slowed)."""
        st = self._st(group)
        if st._live is None:
            base = self.network_dir / "base"
            st._live = _cpp_router()(str(base / "nodes.csv"), str(base / "edges.csv"))
            if st is not self or self._factors is not None or DEFAULT_GROUP in self.graph.allow:
                st._live_factor = {}
                self._sync_live(st)            # base differs from edges.csv: start from the group's times
        changes: Dict[Tuple[int, int], float] = {}
        section = st.graph.section
        for (a, b) in list(st._live_edges):
            if b not in node_factor:          # restore edges no longer affected
                changes[(a, b)] = section(a, b)[0]
                del st._live_edges[(a, b)]
        in_edges = st.graph.in_edges
        for b, f in node_factor.items():
            for a in in_edges[b]:
                tt = section(a, b)[0] * f
                if st._live_edges.get((a, b)) != tt:
                    changes[(a, b)] = tt
                    st._live_edges[(a, b)] = tt
        if changes:
            ks = list(changes)
            st._live.setEdgeTravelTimes([a for a, _ in ks], [b for _, b in ks], [changes[k] for k in ks])
        st._live_factor = dict(node_factor)
        st._live_cache.clear()

    def live_travel(self, o: int, d: int, group: str = DEFAULT_GROUP) -> Tuple[float, float]:
        st = self._st(group)
        if not st._live_factor:
            return self.base_travel(o, d, group=group)
        if o == d:
            return 0.0, 0.0
        hit = st._live_cache.get((o, d))
        if hit is None:
            tt, dist = st._live.computeTravelCosts1To1(o, d)
            hit = (tt, dist) if 0 <= tt < UNREACHABLE_TT else self._fallback(o, d)
            st._live_cache[(o, d)] = hit
        return hit

    def live_many_to_one(self, origins: Sequence[int], d: int, max_tt: Optional[float] = None,
                         group: str = DEFAULT_GROUP):
        st = self._st(group)
        if not st._live_factor:
            return self.many_to_one(origins, d, None, max_tt, group=group)
        out = {o: (0.0, 0.0) for o in origins if o == d}
        rest = [o for o in set(origins) if o != d]
        if rest:
            for o, tt, dist in st._live.computeTravelCostsXto1(d, rest, max_time_range=max_tt):
                if 0 <= tt < UNREACHABLE_TT:
                    out[o] = (tt, dist)
        return out

    def live_path(self, o: int, d: int, group: str = DEFAULT_GROUP) -> List[Tuple[int, float]]:
        st = self._st(group)
        if not st._live_factor:
            return self.path(o, d, group=group)
        if o == d:
            return [(o, 0.0)]
        route = list(st._live.computeRoute1To1(o, d))
        if len(route) < 2:
            return [(o, 0.0), (d, self._fallback(o, d)[0])]
        out, acc = [(route[0], 0.0)], 0.0
        section = st.graph.section
        for a, b in zip(route[:-1], route[1:]):
            try:
                tt, _ = section(a, b)
            except KeyError:
                return [(o, 0.0), (d, self._fallback(o, d)[0])]
            acc += tt * st._live_factor.get(b, 1.0)
            out.append((b, acc))
        if acc >= UNREACHABLE_TT:
            return [(o, 0.0), (d, self._fallback(o, d)[0])]
        return out

    # ------------------------------------------------------------------ dynamic travel times
    def _load_tt(self, sim_time: int) -> None:
        """Dynamics files act on the default group only (factor files: every group)."""
        self.graph.load_tt(sim_time)
        path = self.graph.tt_file(sim_time)
        if self._cpp is not None and path is not None:
            self._cpp.updateEdgeTravelTimes(str(path))
        for st in self._groups.values():
            st.graph.tt_factor = self.graph.tt_factor
            st._cache.clear()

    def update_network(self, sim_time: float) -> bool:
        """Load the time-dependent travel times that start exactly at ``sim_time`` (if any)."""
        key = int(sim_time)
        if self.graph.tt_sources.get(key) is None:
            return False
        self._load_tt(key)
        self._cache.clear()
        return True
