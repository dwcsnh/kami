"""Adapter that reuses FleetPy's road network and Dijkstra router.

FleetPy (TUM-VT) is used *as a library*: we import
``src.routing.road.NetworkBasic`` and its ``Router`` unchanged and wrap them
behind kami's ``Network`` interface. This gives kami real OSM-based road
networks (FleetPy ``data/networks/<name>/base/{nodes,edges}.csv``) and
FleetPy's time-dependent travel-time folders, without copying code.

Incidents are passed to FleetPy's ``customized_section_cost_function`` hook,
so the shortest path is recomputed around affected nodes.
"""
from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from kami.network.base import Network, NodeFactor, SpatialIndex


@contextlib.contextmanager
def _quiet_stdout():
    """Silence FleetPy / C++ router prints (they write straight to file descriptor 1)."""
    try:
        sys.stdout.flush()
        saved = os.dup(1)
    except (OSError, ValueError):
        yield
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 1)
        yield
    finally:
        os.dup2(saved, 1)
        os.close(saved)
        os.close(devnull)


def default_fleetpy_root() -> Path:
    env = os.environ.get("KAMI_FLEETPY_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "FleetPy"


def import_fleetpy(fleetpy_root: Optional[os.PathLike] = None) -> Path:
    """Put FleetPy on ``sys.path`` so ``import src.…`` resolves to FleetPy."""
    root = Path(fleetpy_root) if fleetpy_root else default_fleetpy_root()
    if not (root / "src" / "routing" / "road" / "NetworkBasic.py").exists():
        raise FileNotFoundError(
            f"FleetPy not found at {root}. Set KAMI_FLEETPY_ROOT or pass fleetpy_root=...")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


class FleetPyNetwork(Network):
    """kami ``Network`` backed by FleetPy ``NetworkBasic`` / ``NetworkBasicCpp``.

    :param network_name: folder under ``FleetPy/data/networks`` (e.g. ``example_network``)
    :param network_dynamics_file: optional FleetPy travel-time dynamics file name
    :param backend: ``"auto"`` (C++ router if compiled, else Python), ``"cpp"`` or ``"python"``

    With the C++ backend, incidents are applied to a *second* C++ router ("live"
    state) through FleetPy's own ``updateEdgeTravelTimes`` mechanism, so the
    platform's free-flow view and the real incident-aware state coexist and
    both stay fast.
    """

    def __init__(self, network_name: str = "example_network", fleetpy_root=None,
                 network_dynamics_file: Optional[str] = None, scenario_time: Optional[int] = None,
                 cache_size: int = 200_000, backend: str = "auto"):
        root = import_fleetpy(fleetpy_root)
        cls = None
        if backend in ("auto", "cpp"):
            try:
                from src.routing.road.NetworkBasicCpp import NetworkBasicCpp as cls  # FleetPy C++ router
            except ImportError:
                if backend == "cpp":
                    raise
        if cls is None:
            from src.routing.road.NetworkBasic import NetworkBasic as cls  # FleetPy pure-Python router

        self.name = network_name
        self.fleetpy_root = root
        self.network_dir = root / "data" / "networks" / network_name
        with _quiet_stdout():
            self.nw = cls(str(self.network_dir), network_dynamics_file_name=network_dynamics_file,
                          scenario_time=scenario_time)
        self.backend = "cpp" if getattr(self.nw, "cpp_router", None) is not None else "python"
        self._live = None                       # second C++ router holding incident travel times
        self._live_edges: Dict[Tuple[int, int], float] = {}
        self._live_factor: Dict[int, float] = {}
        self._live_cache: Dict[Tuple[int, int], Tuple[float, float]] = {}
        self._coords: Dict[int, Tuple[float, float]] = {
            n.node_index: self.nw.return_node_coordinates(n.node_index) for n in self.nw.get_node_list()
        }
        self._index = SpatialIndex(self._coords, cell=250.0)
        self._cache: Dict[Tuple[int, int], Tuple[float, float]] = {}
        self._cache_size = cache_size
        xs = [c[0] for c in self._coords.values()]
        ys = [c[1] for c in self._coords.values()]
        self._bounds = (min(xs), min(ys), max(xs), max(ys))
        # random locations: largest strongly connected component, excluding FleetPy stop-only nodes
        scc = self._main_scc()
        self._locations = sorted(n.node_index for n in self.nw.get_node_list()
                                 if n.node_index in scc and not n.must_stop())
        self._loc_index = SpatialIndex({n: self._coords[n] for n in self._locations}, cell=250.0)
        self._scc = scc

    def _main_scc(self) -> set:
        """Strongly connected component around the network centre (forward ∩ backward reachability)."""
        nodes = self.nw.get_node_list()
        x0, y0, x1, y1 = self._bounds
        order = sorted(nodes, key=lambda n: (self._coords[n.node_index][0] - (x0 + x1) / 2) ** 2 +
                       (self._coords[n.node_index][1] - (y0 + y1) / 2) ** 2)
        best: set = set()
        for seed in order[:20]:
            if seed.node_index in best:
                continue
            fwd = self._reach(seed, forward=True)
            comp = fwd & self._reach(seed, forward=False)
            if len(comp) > len(best):
                best = comp
            if len(best) > 0.5 * len(nodes):
                break
        return best

    def _reach(self, start, forward: bool) -> set:
        seen = {start.node_index}
        stack = [start]
        while stack:
            n = stack.pop()
            pairs = n.get_next_node_edge_pairs() if forward else n.get_prev_node_edge_pairs()
            for other, _edge in pairs:
                if other.node_index not in seen and not (other.must_stop() and other is not start):
                    seen.add(other.node_index)
                    stack.append(other)
        return seen

    @staticmethod
    def _pos(node: int):
        return (int(node), None, None)

    def num_nodes(self) -> int:
        return self.nw.get_number_network_nodes()

    def location_nodes(self):
        return self._locations

    def coords(self, node: int) -> Tuple[float, float]:
        return self._coords[node]

    def lonlat(self, node: int):
        return tuple(self.nw.return_positions_lon_lat([self._pos(node)])[0])

    def nearest_node(self, x: float, y: float) -> int:
        """Nearest *location* node (connected, not stop-only)."""
        return self._loc_index.nearest(x, y)

    def within(self, node: int, radius_m: float) -> List[int]:
        x, y = self.coords(node)
        return self._index.within(x, y, radius_m)

    def bounds(self):
        return self._bounds

    @staticmethod
    def _cost_fn(node_factor: NodeFactor):
        if node_factor is None:
            return None
        # FleetPy signature: (travel_time, travel_distance, next_node_index) -> cost
        return lambda tt, dis, node: tt * node_factor(node)

    def base_travel(self, o: int, d: int, node_factor: NodeFactor = None) -> Tuple[float, float]:
        if o == d:
            return 0.0, 0.0
        if node_factor is None:
            hit = self._cache.get((o, d))
            if hit is not None:
                return hit
        cost, _tt, dist = self.nw.return_travel_costs_1to1(self._pos(o), self._pos(d),
                                                            customized_section_cost_function=self._cost_fn(node_factor))
        if cost is None or not (float(cost) < float("inf")) or (float(cost) <= 0 and o != d):
            res = self._fallback(o, d)
        else:
            res = (float(cost), float(dist))
        if node_factor is None:
            if len(self._cache) >= self._cache_size:
                self._cache.clear()
            self._cache[(o, d)] = res
        return res

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
            res = self.nw.return_travel_costs_Xto1([self._pos(o) for o in todo], self._pos(d),
                                                   max_cost_value=max_tt,
                                                   customized_section_cost_function=self._cost_fn(node_factor))
            for pos, cost, _tt, dist in res:
                out[pos[0]] = (float(cost), float(dist))
                if node_factor is None:
                    self._cache[(pos[0], d)] = (float(cost), float(dist))
        return out

    def _fallback(self, o: int, d: int) -> Tuple[float, float]:
        """Unreachable pair (disconnected network part): crow-fly × 1.4 at 8 m/s."""
        dist = self.crow_dist(o, d) * 1.4
        return dist / 8.0, dist

    def path(self, o: int, d: int, node_factor: NodeFactor = None) -> List[Tuple[int, float]]:
        if o == d:
            return [(o, 0.0)]
        route = self.nw.return_best_route_1to1(self._pos(o), self._pos(d),
                                               customized_section_cost_function=self._cost_fn(node_factor))
        out, acc = [(route[0], 0.0)], 0.0
        for a, b in zip(route[:-1], route[1:]):
            try:
                tt, _dist = self.nw.get_section_infos(a, b)
            except KeyError:   # FleetPy returns [o, d] when no route exists
                return [(o, 0.0), (d, self._fallback(o, d)[0])]
            acc += tt * (node_factor(b) if node_factor else 1.0)
            out.append((b, acc))
        return out

    # ------------------------------------------------------------------ live (incident) state, C++ only
    @property
    def supports_live_factors(self) -> bool:
        return self.backend == "cpp"

    def apply_live_factors(self, node_factor: Dict[int, float]) -> None:
        """Set the incident multipliers of the live router (edges *entering* a node are slowed)."""
        from src.routing.road.cpp_router.PyNetwork import PyNetwork

        if self._live is None:
            base = self.network_dir / "base"
            with _quiet_stdout():
                self._live = PyNetwork(str(base / "nodes.csv").encode(), str(base / "edges.csv").encode())
        changes: Dict[Tuple[int, int], float] = {}
        for (a, b) in list(self._live_edges):
            if b not in node_factor:          # restore edges no longer affected
                changes[(a, b)] = self.nw.get_section_infos(a, b)[0]
                del self._live_edges[(a, b)]
        for b, f in node_factor.items():
            for other, _edge in self.nw.nodes[b].get_prev_node_edge_pairs():
                a = other.node_index
                tt = self.nw.get_section_infos(a, b)[0] * f
                if self._live_edges.get((a, b)) != tt:
                    changes[(a, b)] = tt
                    self._live_edges[(a, b)] = tt
        if changes:
            import tempfile

            with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
                fh.write("from_node,to_node,edge_tt\n")
                for (a, b), tt in changes.items():
                    fh.write(f"{a},{b},{tt}\n")
                path = fh.name
            with _quiet_stdout():
                self._live.updateEdgeTravelTimes(path.encode())
            os.unlink(path)
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
                tt, _ = self.nw.get_section_infos(a, b)
            except KeyError:
                return [(o, 0.0), (d, self._fallback(o, d)[0])]
            acc += tt * self._live_factor.get(b, 1.0)
            out.append((b, acc))
        return out

    def update_network(self, sim_time: float) -> bool:
        """Load FleetPy time-dependent travel times if a new file applies at ``sim_time``."""
        changed = bool(self.nw.update_network(int(sim_time)))
        if changed:
            self._cache.clear()
        return changed
