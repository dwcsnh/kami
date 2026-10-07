"""Synthetic Manhattan-style grid city (no external data, instant routing)."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from kami.network.base import Network, NodeFactor, SpatialIndex


class GridNetwork(Network):
    """Rectangular lattice; travel follows an L-shaped (x then y) route.

    Distance is Manhattan distance; free-flow speed is uniform. Node factors
    (incidents) are applied by sampling the nodes along both L-shaped routes
    and keeping the faster one, which reproduces "drivers route around an
    incident" at a fraction of the cost of a real shortest-path search.
    """

    name = "grid"

    def __init__(self, width_m: float = 8000, height_m: float = 8000, spacing_m: float = 250,
                 speed_kmh: float = 25.0):
        self.nx = int(width_m // spacing_m) + 1
        self.ny = int(height_m // spacing_m) + 1
        self.spacing = float(spacing_m)
        self.speed = speed_kmh / 3.6
        self.width, self.height = width_m, height_m
        self._index: Optional[SpatialIndex] = None

    # --- geometry -----------------------------------------------------
    def num_nodes(self) -> int:
        return self.nx * self.ny

    def ij(self, node: int) -> Tuple[int, int]:
        return divmod(node, self.ny)

    def node_at(self, i: int, j: int) -> int:
        return i * self.ny + j

    def coords(self, node: int) -> Tuple[float, float]:
        i, j = divmod(node, self.ny)
        return i * self.spacing, j * self.spacing

    def nearest_node(self, x: float, y: float) -> int:
        i = min(max(int(round(x / self.spacing)), 0), self.nx - 1)
        j = min(max(int(round(y / self.spacing)), 0), self.ny - 1)
        return self.node_at(i, j)

    def bounds(self):
        return 0.0, 0.0, (self.nx - 1) * self.spacing, (self.ny - 1) * self.spacing

    # --- routing ------------------------------------------------------
    def _l_route(self, o: int, d: int, x_first: bool) -> List[int]:
        (i1, j1), (i2, j2) = self.ij(o), self.ij(d)
        nodes = []
        si = 1 if i2 >= i1 else -1
        sj = 1 if j2 >= j1 else -1
        if x_first:
            nodes += [self.node_at(i, j1) for i in range(i1 + si, i2 + si, si)] if i1 != i2 else []
            nodes += [self.node_at(i2, j) for j in range(j1 + sj, j2 + sj, sj)] if j1 != j2 else []
        else:
            nodes += [self.node_at(i1, j) for j in range(j1 + sj, j2 + sj, sj)] if j1 != j2 else []
            nodes += [self.node_at(i, j2) for i in range(i1 + si, i2 + si, si)] if i1 != i2 else []
        return nodes

    def base_travel(self, o: int, d: int, node_factor: NodeFactor = None) -> Tuple[float, float]:
        if o == d:
            return 0.0, 0.0
        (i1, j1), (i2, j2) = self.ij(o), self.ij(d)
        steps = abs(i1 - i2) + abs(j1 - j2)
        dist = steps * self.spacing
        edge_tt = self.spacing / self.speed
        if node_factor is None:
            return steps * edge_tt, dist
        best = min(sum(node_factor(n) for n in self._l_route(o, d, xf)) for xf in (True, False))
        return best * edge_tt, dist

    def path(self, o: int, d: int, node_factor: NodeFactor = None) -> List[Tuple[int, float]]:
        if o == d:
            return [(o, 0.0)]
        edge_tt = self.spacing / self.speed
        routes = [self._l_route(o, d, xf) for xf in (True, False)]
        if node_factor is not None:
            route = min(routes, key=lambda r: sum(node_factor(n) for n in r))
        else:
            route = routes[0]
        out, acc = [(o, 0.0)], 0.0
        for n in route:
            acc += edge_tt * (node_factor(n) if node_factor else 1.0)
            out.append((n, acc))
        return out

    def within(self, node: int, radius_m: float) -> List[int]:
        if self._index is None:
            self._index = SpatialIndex({n: self.coords(n) for n in self.nodes()}, cell=max(self.spacing * 2, 250))
        x, y = self.coords(node)
        return self._index.within(x, y, radius_m)
