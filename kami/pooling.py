"""Ride-pooling primitives: stop-sequence evaluation, insertion, partner search.

The algorithm follows FleetPy's immediate *insertion heuristic*
(``src/fleetctrl/pooling/immediate/insertion.py``): try every (pickup,
dropoff) insertion position in the current stop list, keep the cheapest
feasible one. FleetPy's implementation is bound to its ``VehiclePlan`` /
``FleetControlBase`` classes, so kami re-implements the same idea on its own
light ``Stop`` list. Feasibility = every rider's in-vehicle time stays within
``direct_tt * (1 + max_detour_ratio) + max_detour_abs``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

from kami.core.agents import RiderState, Stop

if TYPE_CHECKING:  # pragma: no cover
    from kami.core.agents import Driver, Rider
    from kami.core.engine import Simulation


@dataclass
class PoolingParams:
    max_detour_ratio: float = 0.5     # in-vehicle time ≤ direct * (1 + ratio) + abs
    max_detour_abs: float = 300.0     # seconds
    max_candidates: int = 6           # partners evaluated on the network per search


@dataclass
class PlanEval:
    stops: List[Stop]
    total_time: float
    pickup_t: Dict[int, float]
    dropoff_t: Dict[int, float]
    detour: Dict[int, float]          # extra in-vehicle seconds vs. direct trip, per rider


class Pooling:
    def __init__(self, sim: "Simulation", params: Optional[PoolingParams] = None):
        self.sim = sim
        self.p = params or PoolingParams()
        self.last_eval: Dict[int, Tuple[int, PlanEval]] = {}   # rider -> (partner, plan)

    # ------------------------------------------------------------------ evaluation
    def evaluate(self, start_loc: int, start_t: float, stops: Sequence[Stop],
                 onboard_since: Optional[Dict[int, float]] = None, check: bool = True) -> Optional[PlanEval]:
        """Simulate a stop sequence with platform-side travel times.

        Returns None if ``check`` and a rider's detour limit is violated.
        """
        sim = self.sim
        t, loc = start_t, start_loc
        pick: Dict[int, float] = dict(onboard_since or {})
        drop: Dict[int, float] = {}
        for s in stops:
            tt, _ = sim.traffic.estimate(loc, s.loc, t)
            t += tt
            loc = s.loc
            if s.kind == "pickup":
                pick[s.rider_id] = t
                t += sim.config.boarding_s
            else:
                drop[s.rider_id] = t
                t += sim.config.alighting_s
        detour = {}
        for rid, td in drop.items():
            r = sim.riders[rid]
            ivt = td - pick.get(rid, start_t)
            limit = r.direct_tt * (1 + self.p.max_detour_ratio) + self.p.max_detour_abs
            if check and ivt > limit + 1e-6:
                return None
            detour[rid] = max(0.0, ivt - r.direct_tt)
        return PlanEval(list(stops), t - start_t, {k: v for k, v in pick.items() if k not in (onboard_since or {})},
                        drop, detour)

    def best_insertion(self, start_loc: int, start_t: float, stops: Sequence[Stop], rider: "Rider",
                       onboard_since: Optional[Dict[int, float]] = None) -> Optional[PlanEval]:
        base = self.evaluate(start_loc, start_t, stops, onboard_since)
        base_time = base.total_time if base else 0.0
        best = None
        pu, do = Stop("pickup", rider.id, rider.origin), Stop("dropoff", rider.id, rider.dest)
        n = len(stops)
        for i in range(n + 1):
            for j in range(i, n + 1):
                cand = list(stops[:i]) + [pu] + list(stops[i:j]) + [do] + list(stops[j:])
                ev = self.evaluate(start_loc, start_t, cand, onboard_since)
                if ev is None:
                    continue
                if best is None or ev.total_time - base_time < best[0]:
                    best = (ev.total_time - base_time, ev)
        return best[1] if best else None

    def plan_pair(self, a: "Rider", b: "Rider") -> Optional[PlanEval]:
        """Best stop order to serve two unassigned riders together (starting at a's origin)."""
        first = self.best_insertion(a.origin, self.sim.t, [], a)
        if first is None:
            return None
        return self.best_insertion(a.origin, self.sim.t, first.stops, b) or None

    def driver_plan_with(self, driver: "Driver", rider: "Rider") -> Optional[PlanEval]:
        """Insert ``rider`` into an assigned driver's remaining plan (from its current position)."""
        sim = self.sim
        if len(driver.onboard) + len({s.rider_id for s in driver.plan if s.kind == "pickup"}) + 1 > driver.capacity:
            return None
        onboard_since = {rid: sim.riders[rid].t_pickup for rid in driver.onboard}
        return self.best_insertion(sim.current_loc(driver), sim.t, driver.plan, rider, onboard_since)

    # ------------------------------------------------------------------ partner search
    def find_partner(self, r: "Rider", max_o_km: float = 1.5, max_d_km: float = 2.0,
                     include_matched: bool = False) -> Optional["Rider"]:
        """Closest compatible rider (crow-fly pre-filter, then a feasible shared plan)."""
        sim = self.sim
        net = sim.network
        cands = []
        for job in sim.open_jobs.values():
            if job.pooled or len(job.rider_ids) != 1 or job.rider_ids[0] == r.id:
                continue
            c = sim.riders[job.rider_ids[0]]
            if c.state == RiderState.WAITING:
                cands.append(c)
        if include_matched:
            for c in sim.riders.values():
                if c.state == RiderState.MATCHED and c.id != r.id and not c.pooled:
                    cands.append(c)
        scored = []
        for c in cands:
            do, dd = net.crow_dist(r.origin, c.origin), net.crow_dist(r.dest, c.dest)
            if do <= max_o_km * 1000 and dd <= max_d_km * 1000:
                scored.append((do + dd, c.id, c))
        scored.sort(key=lambda x: (x[0], x[1]))
        for _, _, c in scored[: self.p.max_candidates]:
            if c.state == RiderState.WAITING:
                ev = self.plan_pair(r, c)
            else:
                ev = self.driver_plan_with(sim.drivers[c.driver_id], r)
            if ev is not None:
                self.last_eval[r.id] = (c.id, ev)
                self.last_eval[c.id] = (r.id, ev)
                return c
        return None
