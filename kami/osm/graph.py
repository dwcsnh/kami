"""OSM ways → directed, simplified road graph (decisions D3–D7).

1. clip every way to the area polygon (runs of consecutive nodes inside it);
2. split runs at *important* nodes — shared by several ways, or run ends;
3. one directed edge per direction allowed by ``oneway`` / ``junction=roundabout`` (``-1`` reverses), with the
   road class, car/motorbike permission, free-flow speed and the full polyline;
4. merge chains through degree-2 nodes whose edges have identical attributes (the polyline keeps every point);
5. keep the largest strongly connected component of the car ∪ motorbike graph;
6. number nodes ``0..N-1`` by OSM id and sort edges, so the output is deterministic.

Parallel edges and loops (not representable in the FleetPy format) are split at an inner OSM node, or the slower
duplicate is dropped when the way has no inner node.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from kami.osm.extract import OsmData, motor_access
from kami.osm.geo import Point, Polygon, haversine

YES = ("yes", "true", "1")
REVERSE = ("-1", "reverse")


@dataclass
class Edge:
    a: int                      # OSM node ids until renumbering
    b: int
    length: float
    tt: float
    road_class: str
    car: bool
    bike: bool
    speed_kmh: float
    way: int
    geom: List[Point] = field(repr=False)
    maxspeed: bool = False      # speed came from a maxspeed tag

    def key(self):
        return (self.road_class, self.car, self.bike, self.speed_kmh)


@dataclass
class RoadGraphData:
    nodes: List[int]                         # OSM id of node i (index = new node id)
    lonlat: List[Point]
    edges: List[Edge]                        # a, b are new node ids
    stats: Dict[str, float] = field(default_factory=dict)


def parse_maxspeed(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(mph|km/h|kmh)?\s*$", text)
    if not m:
        return None
    v = float(m.group(1))
    return v * 1.609344 if m.group(2) == "mph" else v


def direction(tags: Dict[str, str]) -> Optional[int]:
    """+1 forward only, -1 backward only, 0 both ways, None = skip (reversible / alternating)."""
    ow = tags.get("oneway")
    if ow in YES:
        return 1
    if ow in REVERSE:
        return -1
    if ow in ("reversible", "alternating"):
        return None
    if ow in ("no", "false", "0"):
        return 0
    if tags.get("highway") in ("motorway", "motorway_link") or tags.get("junction") in ("roundabout", "circular"):
        return 1
    return 0


def build_graph(data: OsmData, area: Polygon, speeds_kmh: Dict[str, float]) -> RoadGraphData:
    ll = data.node_ll
    inside: Dict[int, bool] = {}

    def ins(n: int) -> bool:
        v = inside.get(n)
        if v is None:
            v = inside[n] = area.contains(ll[n])
        return v

    # 1. clip ---------------------------------------------------------------------------------------------
    runs: List[Tuple[int, Dict[str, str], List[int]]] = []
    for w in data.ways:
        cur: List[int] = []
        for n in w.refs:
            if ins(n):
                cur.append(n)
            else:
                if len(cur) >= 2:
                    runs.append((w.id, w.tags, cur))
                cur = []
        if len(cur) >= 2:
            runs.append((w.id, w.tags, cur))

    # 2. split at important nodes ------------------------------------------------------------------------
    uses: Dict[int, int] = {}
    ends: Set[int] = set()
    for _, _, refs in runs:
        for n in refs:
            uses[n] = uses.get(n, 0) + 1
        ends.add(refs[0])
        ends.add(refs[-1])
    important = {n for n, k in uses.items() if k >= 2} | ends

    edges: Dict[Tuple[int, int], Edge] = {}
    stats: Dict[str, float] = {"ways_clipped": len({r[0] for r in runs})}

    def add_piece(way: int, tags, refs: List[int], dirn: int, attrs) -> None:
        car, bike, speed, cls, has_max = attrs
        if refs[0] == refs[-1] or _collides(edges, refs, dirn):
            if len(refs) > 2:                  # loop / parallel edge: split at the middle inner node
                k = len(refs) // 2
                add_piece(way, tags, refs[:k + 1], dirn, attrs)
                add_piece(way, tags, refs[k:], dirn, attrs)
                return
            if refs[0] == refs[-1]:
                return
        geom = [ll[n] for n in refs]
        length = sum(haversine(p, q) for p, q in zip(geom[:-1], geom[1:]))
        if length <= 0:
            return
        tt = length / (speed / 3.6)
        for a, b, g in ((refs[0], refs[-1], geom), (refs[-1], refs[0], geom[::-1])):
            if (dirn == 1 and a != refs[0]) or (dirn == -1 and a == refs[0]):
                continue
            old = edges.get((a, b))
            if old is not None and old.tt <= tt:
                continue                          # keep the faster duplicate
            edges[(a, b)] = Edge(a, b, length, tt, cls, car, bike, speed, way, g, has_max)

    for way, tags, refs in runs:
        dirn = direction(tags)
        if dirn is None:
            continue
        hw = tags["highway"]
        default = float(speeds_kmh.get(hw, speeds_kmh.get(hw.replace("_link", ""), 20.0)))
        ms = parse_maxspeed(tags.get("maxspeed"))
        speed = min(ms, default) if ms else default          # maxspeed only lowers the free-flow speed
        car, bike = motor_access(tags)
        attrs = (car, bike, speed, hw, ms is not None)
        start = 0
        for i in range(1, len(refs)):
            if refs[i] in important:
                add_piece(way, tags, refs[start:i + 1], dirn, attrs)
                start = i
    stats["edges_raw"] = len(edges)
    stats["nodes_raw"] = len({n for e in edges for n in e})

    # 4. merge degree-2 chains ------------------------------------------------------------------------------
    _merge_chains(edges)
    stats["edges_simplified"] = len(edges)

    # 5. largest SCC of the union graph ------------------------------------------------------------------
    nodes_all = sorted({n for e in edges for n in e})
    comp = _largest_scc(nodes_all, edges)
    stats["nodes_simplified"] = len(nodes_all)
    stats["scc_share"] = round(len(comp) / max(1, len(nodes_all)), 4)
    kept = [e for (a, b), e in edges.items() if a in comp and b in comp]
    car_edges = {(e.a, e.b): e for e in kept if e.car}
    bike_edges = {(e.a, e.b): e for e in kept if e.bike}
    nodes = sorted(comp)
    stats["scc_car_share"] = round(len(_largest_scc(nodes, car_edges)) / max(1, len(nodes)), 4)
    stats["scc_bike_share"] = round(len(_largest_scc(nodes, bike_edges)) / max(1, len(nodes)), 4)

    # 6. renumber ------------------------------------------------------------------------------------------
    index = {n: i for i, n in enumerate(nodes)}
    for e in kept:
        e.a, e.b = index[e.a], index[e.b]
    kept.sort(key=lambda e: (e.a, e.b))
    stats.update(nodes=len(nodes), edges=len(kept),
                 edges_with_maxspeed=round(sum(e.maxspeed for e in kept) / max(1, len(kept)), 4),
                 edges_car_forbidden=sum(not e.car for e in kept),
                 edges_bike_forbidden=sum(not e.bike for e in kept),
                 length_km=round(sum(e.length for e in kept) / 1000, 1))
    return RoadGraphData(nodes, [ll[n] for n in nodes], kept, stats)


def _collides(edges, refs, dirn) -> bool:
    a, b = refs[0], refs[-1]
    if dirn in (0, 1) and (a, b) in edges:
        return True
    return dirn in (0, -1) and (b, a) in edges


def _merge_chains(edges: Dict[Tuple[int, int], Edge]) -> None:
    out: Dict[int, Dict[int, Edge]] = {}
    inn: Dict[int, Dict[int, Edge]] = {}
    for (a, b), e in edges.items():
        out.setdefault(a, {})[b] = e
        inn.setdefault(b, {})[a] = e

    def drop(e: Edge):
        del edges[(e.a, e.b)]
        del out[e.a][e.b]
        del inn[e.b][e.a]

    def add(e: Edge):
        edges[(e.a, e.b)] = e
        out.setdefault(e.a, {})[e.b] = e
        inn.setdefault(e.b, {})[e.a] = e

    def join(e1: Edge, e2: Edge) -> Edge:      # e1: u → n, e2: n → w
        return Edge(e1.a, e2.b, e1.length + e2.length, e1.tt + e2.tt, e1.road_class, e1.car, e1.bike,
                    e1.speed_kmh, e1.way, e1.geom + e2.geom[1:], e1.maxspeed)

    for n in sorted(set(out) | set(inn)):
        o, i = out.get(n, {}), inn.get(n, {})
        if set(o) == set(i) and len(o) == 2:                      # two-way through node
            u, w = sorted(o)
            es = [i[u], o[w], i[w], o[u]]
            if len({e.key() for e in es}) != 1 or (u, w) in edges or (w, u) in edges or u == w:
                continue
            f, b = join(i[u], o[w]), join(i[w], o[u])
            for e in es:
                drop(e)
            add(f)
            add(b)
        elif len(o) == 1 and len(i) == 1:                         # one-way through node
            (w, e2), = o.items()
            (u, e1), = i.items()
            if u == w or e1.key() != e2.key() or (u, w) in edges:
                continue
            drop(e1)
            drop(e2)
            add(join(e1, e2))


def _largest_scc(nodes: Sequence[int], edges) -> Set[int]:
    """Largest strongly connected component (iterative Tarjan); ties → the one with the smallest node id."""
    adj: Dict[int, List[int]] = {}
    for (a, b) in edges:
        adj.setdefault(a, []).append(b)
    for v in adj.values():
        v.sort()
    index: Dict[int, int] = {}
    low: Dict[int, int] = {}
    on: Set[int] = set()
    stack: List[int] = []
    best: Set[int] = set()
    counter = 0
    for root in nodes:
        if root in index:
            continue
        work = [(root, 0)]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on.add(root)
        while work:
            v, k = work[-1]
            nbrs = adj.get(v, ())
            if k < len(nbrs):
                work[-1] = (v, k + 1)
                w = nbrs[k]
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, 0))
                elif w in on:
                    low[v] = min(low[v], index[w])
                continue
            work.pop()
            if work:
                p = work[-1][0]
                low[p] = min(low[p], low[v])
            if low[v] == index[v]:
                comp = set()
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.add(w)
                    if w == v:
                        break
                if len(comp) > len(best) or (len(comp) == len(best) and min(comp) < min(best)):
                    best = comp
    return best
