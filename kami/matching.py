"""Batch matching: candidate generation + assignment (greedy or Hungarian).

Used by ``Simulation.default_dispatch`` and available to policies that only
want to change *parameters* (pickup radius, wait weight, solver).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Sequence, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from kami.core.agents import Driver, Job
    from kami.core.engine import Simulation

INF = 1e9


@dataclass
class MatchingParams:
    max_pickup_eta: float = 900.0   # seconds; pairs beyond are not considered ("bán kính đón tối đa")
    candidates_per_job: int = 12    # k nearest drivers (crow-fly) evaluated on the network
    max_speed_mps: float = 16.0     # crow-fly pre-filter: radius = max_pickup_eta * max_speed
    solver: str = "hungarian"       # "hungarian" | "greedy"
    wait_weight: float = 0.0        # cost = eta - wait_weight * waited (prioritise long waits)


def candidate_pairs(sim: "Simulation", jobs: Sequence["Job"], drivers: Sequence["Driver"],
                    p: MatchingParams) -> List[Tuple[float, "Job", "Driver", float]]:
    """(cost, job, driver, eta) for every feasible job/driver pair."""
    if not jobs or not drivers:
        return []
    locs = {d.id: sim.current_loc(d) for d in drivers}
    xy = {d.id: sim.network.coords(locs[d.id]) for d in drivers}
    radius2 = (p.max_pickup_eta * p.max_speed_mps) ** 2
    grouped = len({d.group for d in drivers}) > 1     # vehicle groups route separately (sprint 02)
    out = []
    for job in jobs:
        origin = sim.job_first_pickup(job)
        ox, oy = sim.network.coords(origin)
        need = sim.job_size(job)
        near = []
        for d in drivers:
            if d.id in job.tabu or d.capacity < need:
                continue
            dx, dy = xy[d.id]
            dd = (dx - ox) ** 2 + (dy - oy) ** 2
            if dd <= radius2:
                near.append((dd, d))
        near.sort(key=lambda x: (x[0], x[1].id))
        near = [d for _, d in near[: p.candidates_per_job]]
        if not near:
            continue
        aware = sim.traffic.platform_sees_incidents
        if grouped:
            by_group = {g: sim.traffic.many_to_one([locs[d.id] for d in near if d.group == g], origin, sim.t,
                                                   max_tt=p.max_pickup_eta, aware=aware, group=g)
                        for g in sorted({d.group for d in near})}
        else:
            etas = sim.traffic.many_to_one([locs[d.id] for d in near], origin, sim.t, max_tt=p.max_pickup_eta,
                                           aware=aware)
        waited = sim.t - min(sim.riders[r].t_booked or sim.t for r in job.rider_ids)
        for d in near:
            hit = (by_group[d.group] if grouped else etas).get(locs[d.id])
            if hit is None:
                continue
            eta = hit[0]
            out.append((eta - p.wait_weight * waited, job, d, eta))
    return out


def solve(pairs, solver: str = "hungarian") -> List[Tuple["Job", "Driver"]]:
    if not pairs:
        return []
    if solver == "hungarian":
        try:
            return _hungarian(pairs)
        except ImportError:
            pass
    return _greedy(pairs)


def _greedy(pairs):
    used_j, used_d, out = set(), set(), []
    for cost, job, drv, _ in sorted(pairs, key=lambda x: (x[0], x[1].id, x[2].id)):
        if job.id in used_j or drv.id in used_d:
            continue
        used_j.add(job.id)
        used_d.add(drv.id)
        out.append((job, drv))
    return out


def _hungarian(pairs):
    from scipy.optimize import linear_sum_assignment  # optional dependency
    import numpy as np

    jobs = sorted({j.id: j for _, j, _, _ in pairs}.values(), key=lambda j: j.id)
    drvs = sorted({d.id: d for _, _, d, _ in pairs}.values(), key=lambda d: d.id)
    ji = {j.id: i for i, j in enumerate(jobs)}
    di = {d.id: i for i, d in enumerate(drvs)}
    cost = np.full((len(jobs), len(drvs)), INF)
    for c, j, d, _ in pairs:
        cost[ji[j.id], di[d.id]] = min(cost[ji[j.id], di[d.id]], c)
    rows, cols = linear_sum_assignment(cost)
    return [(jobs[r], drvs[c]) for r, c in zip(rows, cols) if cost[r, c] < INF]


def match(sim: "Simulation", jobs, drivers, p: MatchingParams) -> List[Tuple["Job", "Driver"]]:
    return solve(candidate_pairs(sim, jobs, drivers, p), p.solver)
