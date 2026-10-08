"""Routing check of a built network (S02-2): size, reachability, query times, C++ vs Python routes.

``python -m kami.osm check hanoi``. Origin/destination pairs are drawn from ``location_nodes`` with
``random.Random(f"osm-check|{seed}")`` (build-time tool, not part of a simulation).
"""
from __future__ import annotations

import random
import statistics
import time
from typing import Any, Dict, Optional


def check(network: str, n_pairs: int = 1000, seed: int = 0, python_pairs: int = 200,
          data_root: Optional[str] = None) -> Dict[str, Any]:
    from kami.network.road import RoadNetwork
    from kami.network.road.cpp import PyNetwork

    t0 = time.perf_counter()
    py = RoadNetwork(network, data_root=data_root, backend="python")
    load_py = time.perf_counter() - t0
    g = py.graph
    locs = py.location_nodes()
    out: Dict[str, Any] = {
        "network": py.name, "nodes": py.num_nodes(), "edges": len(g.edges),
        "location_nodes": len(locs), "location_share": round(len(locs) / py.num_nodes(), 4),
        "groups_restricted": {k: sum(not a for a in v) for k, v in g.allow.items()},
        "load_s": {"python": round(load_py, 2)},
    }
    for group, allowed in g.allow.items():
        out[f"scc_share_{group}"] = round(len(py._main_scc(allowed)) / py.num_nodes(), 4)
    rng = random.Random(f"osm-check|{seed}")
    pairs = [(rng.choice(locs), rng.choice(locs)) for _ in range(n_pairs)]
    if PyNetwork is None:
        out["cpp"] = "not built (python -m kami.network.road.cpp.build)"
        return out
    t0 = time.perf_counter()
    cpp = RoadNetwork(network, data_root=data_root, backend="cpp")
    out["load_s"]["cpp"] = round(time.perf_counter() - t0, 2)
    # 1 → 1
    t1 = []
    reach = 0
    for o, d in pairs:
        s = time.perf_counter()
        tt, _ = cpp._travel_1to1(cpp, o, d, None)
        t1.append(time.perf_counter() - s)
        reach += tt < float("inf")
    # X → 1 (12 origins, 900 s radius: the matching query)
    tx = []
    for k in range(min(n_pairs, 300)):
        d = pairs[k][1]
        origins = [rng.choice(locs) for _ in range(12)]
        s = time.perf_counter()
        cpp.many_to_one(origins, d, max_tt=900.0)
        tx.append(time.perf_counter() - s)
        cpp._cache.clear()
    # route comparison with the pure-Python router
    same = 0
    tpy = []
    for o, d in pairs[:python_pairs]:
        s = time.perf_counter()
        a = py.path(o, d)
        tpy.append(time.perf_counter() - s)
        b = cpp.path(o, d)
        same += [n for n, _ in a] == [n for n, _ in b] or abs(a[-1][1] - b[-1][1]) < 1e-6
    tts = [cpp.base_travel(o, d)[0] for o, d in pairs]
    out.update({
        "pairs": n_pairs, "reachable_share": round(reach / n_pairs, 4),
        "cpp_1to1_ms": {"mean": round(statistics.mean(t1) * 1e3, 3), "p95": round(sorted(t1)[int(0.95 * len(t1))] * 1e3, 3)},
        "cpp_xto1_900s_ms": {"mean": round(statistics.mean(tx) * 1e3, 3)},
        "python_1to1_ms": {"mean": round(statistics.mean(tpy) * 1e3, 2)},
        "python_vs_cpp_same_route_or_cost": f"{same}/{min(python_pairs, n_pairs)}",
        "free_flow_tt_min": {"median": round(statistics.median(tts) / 60, 1), "max": round(max(tts) / 60, 1)},
    })
    return out
