"""Pure-Python Dijkstra router on a ``RoadGraph``.

Port of FleetPy's ``routing_imports/Router.py`` (TUM-VT, MIT licence, see ``LICENSE-FleetPy``), restricted to what
kami needs: one-to-one bidirectional search and one-to-many / many-to-one searches with a cost radius. The search
order, tie-breaking and stopping rules are kept identical, so routes and costs match FleetPy's ``NetworkBasic``.
Search state lives in per-query dicts instead of node attributes.

A *cost function* ``f(travel_time, distance, next_node) -> cost`` replaces travel time as the objective (kami uses it
for incident slow-downs); costs are tuples ``(cost, travel_time, distance)``.
"""
from __future__ import annotations

import heapq
import itertools
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from kami.network.road.graph import RoadGraph

Cost = Tuple[float, float, float]
CostFn = Callable[[float, float, int], float]
INF_COST: Cost = (float("inf"), float("inf"), float("inf"))
_REMOVED = -1


class _PQ:
    """Priority queue with decrease-key by lazy removal; ties broken by insertion order."""

    __slots__ = ("pq", "entries", "counter")

    def __init__(self):
        self.pq: List[list] = []
        self.entries: Dict[int, list] = {}
        self.counter = itertools.count()

    def add(self, node: int, priority: float) -> None:
        old = self.entries.pop(node, None)
        if old is not None:
            old[2] = _REMOVED
        entry = [priority, next(self.counter), node]
        self.entries[node] = entry
        heapq.heappush(self.pq, entry)

    def __bool__(self) -> bool:
        pq = self.pq
        while pq and pq[0][2] == _REMOVED:
            heapq.heappop(pq)
        return bool(pq)

    def pop(self) -> Tuple[int, float]:
        while True:
            priority, _, node = heapq.heappop(self.pq)
            if node != _REMOVED:
                del self.entries[node]
                return node, priority


class _Search:
    """State of one directional search (forward follows out-edges, backward follows in-edges)."""

    __slots__ = ("edges", "settled", "cost", "pred", "pq")

    def __init__(self, edges):
        self.edges = edges
        self.settled = set()
        self.cost: Dict[int, Cost] = {}
        self.pred: Dict[int, Optional[int]] = {}
        self.pq = _PQ()

    def start(self, node: int) -> None:
        self.settled.add(node)
        self.cost[node] = (0, 0, 0)
        self.pred[node] = None
        self.pq.add(node, 0)


class Router:
    def __init__(self, graph: RoadGraph):
        self.g = graph

    # ------------------------------------------------------------------ expansion
    def _step(self, s: _Search, node: int, cost: float, root: int, fn: Optional[CostFn],
              radius: Optional[float] = None) -> None:
        s.settled.add(node)
        if node != root and self.g.stop_only[node]:
            return
        if radius is not None and radius < cost:
            return
        cur = s.cost[node]
        for nxt, (tt, dist) in s.edges[node].items():
            new = cost + (tt if fn is None else fn(tt, dist, nxt))
            if nxt in s.settled:
                continue
            old = s.cost.get(nxt)
            if old is None or old[0] > new:
                s.cost[nxt] = (new, cur[1] + tt, cur[2] + dist)
                s.pred[nxt] = node
                s.pq.add(nxt, new)

    # ------------------------------------------------------------------ one-to-many / many-to-one
    def search(self, root: int, targets: Iterable[int], forward: bool = True, radius: Optional[float] = None,
               max_targets: Optional[int] = None, fn: Optional[CostFn] = None,
               with_route: bool = False) -> List[Tuple[int, Cost, Optional[List[int]]]]:
        """Dijkstra from ``root`` until all targets (or ``max_targets``) are settled or ``radius`` is exceeded.

        Returns ``(target, cost, route)`` for every target in input order; ``cost`` is ``INF_COST`` if the target was
        not reached. As in FleetPy, a target touched but not yet settled when the search stops keeps its tentative cost.
        Forward routes run ``root → target``, backward routes ``target → root``.
        """
        targets = list(dict.fromkeys(targets))
        tset = set(targets)
        to_reach = len(targets) if max_targets is None else min(max_targets, len(targets))
        s = _Search(self.g.out_edges if forward else self.g.in_edges)
        s.start(root)
        reached = 0
        while s.pq:
            node, cost = s.pq.pop()
            if node in tset:
                reached += 1
                s.settled.add(node)
                if reached == to_reach:
                    break
            if radius is not None and cost > radius:
                break
            self._step(s, node, cost, root, fn, radius if forward else None)
        out = []
        for t in targets:
            c = s.cost.get(t)
            if c is None:
                out.append((t, INF_COST, None))
                continue
            route = None
            if with_route:
                route, n = [], t
                while n is not None:
                    route.append(n)
                    n = s.pred[n]
                if forward:
                    route.reverse()
            out.append((t, c, route))
        return out

    # ------------------------------------------------------------------ one-to-one
    def one_to_one(self, start: int, end: int, fn: Optional[CostFn] = None,
                   with_route: bool = False) -> Tuple[Cost, Optional[List[int]]]:
        """Bidirectional Dijkstra; ``(INF_COST, None)`` if there is no route."""
        if start == end:
            return (0.0, 0.0, 0.0), [start]
        fw = _Search(self.g.out_edges)
        bw = _Search(self.g.in_edges)
        fw.start(start)
        bw.start(end)
        stop = self.g.stop_only
        f_node = b_node = None
        f_cost = b_cost = -1.0
        common = None
        while True:
            if f_cost < 0:
                if fw.pq:
                    f_node, f_cost = fw.pq.pop()
                else:
                    f_cost = float("inf")
            if b_cost < 0:
                if bw.pq:
                    b_node, b_cost = bw.pq.pop()
                else:
                    b_cost = float("inf")
            if b_node is None and f_node is None:
                return INF_COST, None
            if f_cost < b_cost:
                self._step(fw, f_node, f_cost, start, fn)
                if f_node in bw.settled and (not stop[f_node] or f_node == start or f_node == end):
                    common = f_node
                    break
                f_cost, f_node = -1.0, None
            else:
                self._step(bw, b_node, b_cost, end, fn)
                if b_node in fw.settled and (not stop[b_node] or b_node == end or b_node == start):
                    common = b_node
                    break
                b_cost, b_node = -1.0, None
        if common not in fw.cost or common not in bw.cost:
            return INF_COST, None
        # the fastest route does not necessarily pass the meeting node: check nodes touched by both searches
        cands = [(common, fw.cost[common][0] + bw.cost[common][0])]
        while fw.pq:
            n, c = fw.pq.pop()
            if n in bw.cost and (not stop[n] or n == end or n == start):
                cands.append((n, c + bw.cost[n][0]))
        while bw.pq:
            n, c = bw.pq.pop()
            if n in fw.cost and (not stop[n] or n == end or n == start):
                cands.append((n, c + fw.cost[n][0]))
        common = min(cands, key=lambda x: x[1])[0]
        if common not in fw.cost or common not in bw.cost:
            return INF_COST, None
        cf, cb = fw.cost[common], bw.cost[common]
        cost = (cf[0] + cb[0], cf[1] + cb[1], cf[2] + cb[2])
        route = None
        if with_route:
            head, n = [], fw.pred[common]
            while n is not None:
                head.append(n)
                n = fw.pred[n]
            head.reverse()
            route, n = head, common
            while n is not None:
                route.append(n)
                n = bw.pred[n]
        return cost, route
