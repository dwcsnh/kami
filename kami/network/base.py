"""Network interface used by the traffic layer.

A *location* in kami is always an integer node id of a ``Network``. Travel
times returned here are **free-flow / base** values; time-of-day, weather and
incidents are applied on top by ``kami.traffic.TrafficLayer``.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

NodeFactor = Optional[Callable[[int], float]]   # multiplier on edges entering a node


class Network(ABC):
    """Minimal routing API. Implementations: ``GridNetwork``, ``RoadNetwork``."""

    name: str = "network"

    @abstractmethod
    def num_nodes(self) -> int: ...

    @abstractmethod
    def coords(self, node: int) -> Tuple[float, float]:
        """Planar coordinates in metres."""

    @abstractmethod
    def base_travel(self, o: int, d: int, node_factor: NodeFactor = None) -> Tuple[float, float]:
        """(travel_time_s, distance_m) of the fastest route.

        ``node_factor(node)`` multiplies the travel time of every edge entering
        ``node``; routing must take it into account (drivers avoid incidents).
        """

    def many_to_one(self, origins: Sequence[int], d: int, node_factor: NodeFactor = None,
                    max_tt: Optional[float] = None) -> Dict[int, Tuple[float, float]]:
        """Travel from many origins to one destination. Override for a one-pass search."""
        out = {}
        for o in origins:
            tt, dist = self.base_travel(o, d, node_factor)
            if max_tt is None or tt <= max_tt:
                out[o] = (tt, dist)
        return out

    def path(self, o: int, d: int, node_factor: NodeFactor = None) -> List[Tuple[int, float]]:
        """Nodes of the route with cumulative base travel time. Default: just the endpoints."""
        tt, _ = self.base_travel(o, d, node_factor)
        return [(o, 0.0), (d, tt)] if o != d else [(o, 0.0)]

    def lonlat(self, node: int) -> Optional[Tuple[float, float]]:
        """(lon, lat) when the network is geo-referenced, else None."""
        return None

    def crow_dist(self, o: int, d: int) -> float:
        (x1, y1), (x2, y2) = self.coords(o), self.coords(d)
        return math.hypot(x1 - x2, y1 - y2)

    @abstractmethod
    def nearest_node(self, x: float, y: float) -> int: ...

    @abstractmethod
    def bounds(self) -> Tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y) in metres."""

    def nodes(self) -> Iterable[int]:
        """Every node id (zones are defined over all of them)."""
        return range(self.num_nodes())

    def location_nodes(self) -> List[int]:
        """Nodes usable as random locations (connected, routable). Default: all nodes."""
        return list(self.nodes())


class SpatialIndex:
    """Bucket grid for nearest-node / radius queries on planar coordinates."""

    def __init__(self, points: Dict[int, Tuple[float, float]], cell: float = 250.0):
        self.cell = cell
        self.buckets: Dict[Tuple[int, int], List[int]] = {}
        self.points = points
        for n, (x, y) in points.items():
            self.buckets.setdefault((int(x // cell), int(y // cell)), []).append(n)

    def nearest(self, x: float, y: float) -> int:
        cx, cy = int(x // self.cell), int(y // self.cell)
        best, best_d = None, float("inf")
        r = 0
        while best is None or r <= 1 + int(math.sqrt(best_d) // self.cell):
            for i in range(cx - r, cx + r + 1):
                for j in range(cy - r, cy + r + 1):
                    if max(abs(i - cx), abs(j - cy)) != r:
                        continue
                    for n in self.buckets.get((i, j), ()):
                        px, py = self.points[n]
                        dd = (px - x) ** 2 + (py - y) ** 2
                        if dd < best_d:
                            best, best_d = n, dd
            r += 1
            if r > 10_000:
                break
        return best

    def within(self, x: float, y: float, radius: float) -> List[int]:
        cx, cy = int(x // self.cell), int(y // self.cell)
        k = int(radius // self.cell) + 1
        out = []
        r2 = radius * radius
        for i in range(cx - k, cx + k + 1):
            for j in range(cy - k, cy + k + 1):
                for n in self.buckets.get((i, j), ()):
                    px, py = self.points[n]
                    if (px - x) ** 2 + (py - y) ** 2 <= r2:
                        out.append(n)
        return out
