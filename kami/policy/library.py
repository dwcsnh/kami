"""Ready-made policies (design doc §7.2, §7.3)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Hashable, List, Optional, Sequence

from kami.core.agents import Quote, RiderState
from kami.matching import MatchingParams
from kami.policy.base import Policy

if TYPE_CHECKING:  # pragma: no cover
    from kami.core.engine import Simulation


class Baseline(Policy):
    """Status quo: batch matching, metered fares, drivers decide where to go when idle."""

    name = "baseline"


class PoolAfterWait(Policy):
    """Design doc §7.2 — after ``wait_threshold`` seconds without a driver, propose pooling.

    Both riders must accept (``sim.behavior.pool_accept``); the merged job then
    goes back to the dispatch queue and is served by one vehicle.

    :param surcharge: VND added to each pooled rider's fare (negative = discount)
    :param include_matched: also look for partners among riders whose driver is already en route
    :param retry_every: re-try every N seconds while the rider is still waiting (None = once)
    """

    name = "pool_after_wait"

    def __init__(self, wait_threshold: float = 300.0, surcharge: float = 20_000, max_o_km: float = 1.5,
                 max_d_km: float = 2.0, include_matched: bool = False, retry_every: Optional[float] = None,
                 **kw):
        super().__init__(**kw)
        self.wait_threshold = wait_threshold
        self.surcharge = surcharge
        self.max_o_km, self.max_d_km = max_o_km, max_d_km
        self.include_matched = include_matched
        self.retry_every = retry_every

    def on_request(self, sim: "Simulation", r):
        sim.schedule(sim.t + self.wait_threshold, "POLICY_TIMER", r=r)

    def on_timer(self, sim: "Simulation", r, **payload):
        if r is None or r.state != RiderState.WAITING or r.pooled:
            return
        partner = sim.pooling.find_partner(r, max_o_km=self.max_o_km, max_d_km=self.max_d_km,
                                           include_matched=self.include_matched)
        if partner is not None and sim.behavior.pool_accept(r, self.surcharge) \
                and sim.behavior.pool_accept(partner, self.surcharge):
            sim.merge_jobs(r, partner, surcharge=self.surcharge)
        elif self.retry_every:
            sim.schedule(sim.t + self.retry_every, "POLICY_TIMER", r=r)

    def describe(self):
        return dict(super().describe(), wait_threshold=self.wait_threshold, surcharge=self.surcharge,
                    max_o_km=self.max_o_km, max_d_km=self.max_d_km, include_matched=self.include_matched)


class SurgePricing(Policy):
    """Zone surge from the recent demand/supply ratio, recomputed on ``PRICE_UPDATE``.

    surge = clip(1 + sensitivity * (ratio - threshold), 1, max_surge),
    ratio = (recent requests + open jobs) / max(idle drivers, 1).
    """

    name = "surge"

    def __init__(self, every: float = 120.0, window_s: float = 600.0, threshold: float = 1.5,
                 sensitivity: float = 0.25, max_surge: float = 2.0, **kw):
        super().__init__(**kw)
        self.tick_intervals = {"PRICE_UPDATE": every}
        self.window_s, self.threshold = window_s, threshold
        self.sensitivity, self.max_surge = sensitivity, max_surge

    def on_tick(self, sim: "Simulation", kind: str):
        if kind != "PRICE_UPDATE":
            return
        for z, s in sim.zone_stats(self.window_s).items():
            ratio = (s["requests"] + s["open"]) / max(s["idle"], 1)
            surge = min(self.max_surge, max(1.0, 1 + self.sensitivity * (ratio - self.threshold)))
            sim.set_surge(z, round(surge, 2))


class HeatmapReposition(Policy):
    """Every ``every`` seconds send up to ``max_moves`` idle drivers from surplus to deficit zones."""

    name = "heatmap_reposition"

    def __init__(self, every: float = 300.0, window_s: float = 900.0, max_moves: int = 20,
                 max_distance_m: float = 3000.0, **kw):
        super().__init__(**kw)
        self.tick_intervals = {"REPOSITION_TICK": every}
        self.window_s, self.max_moves, self.max_distance_m = window_s, max_moves, max_distance_m

    def on_tick(self, sim: "Simulation", kind: str):
        if kind != "REPOSITION_TICK":
            return
        stats = sim.zone_stats(self.window_s)
        deficit = sorted(((s["requests"] + s["open"] - s["idle"], z) for z, s in stats.items()
                          if s["requests"] + s["open"] > s["idle"]), key=lambda x: (-x[0], str(x[1])))
        if not deficit:
            return
        idle_by_zone: Dict[Hashable, List] = {}
        for d in sim.idle_drivers():
            if d.leg is None:   # only parked drivers are redirected
                idle_by_zone.setdefault(sim.zones.zone_of(d.loc), []).append(d)
        surplus = [d for z, ds in idle_by_zone.items()
                   if stats.get(z, {}).get("requests", 0) + stats.get(z, {}).get("open", 0) < len(ds)
                   for d in sorted(ds, key=lambda d: d.id)[1:]]
        moves = 0
        for need, z in deficit:
            target = sim.zones.centroid_node(z)
            surplus.sort(key=lambda d: (sim.network.crow_dist(d.loc, target), d.id))
            for _ in range(int(need)):
                if not surplus or moves >= self.max_moves:
                    return
                d = surplus[0]
                if sim.network.crow_dist(d.loc, target) > self.max_distance_m:
                    break
                surplus.pop(0)
                sim.reposition(d, target)
                moves += 1


class Composite(Policy):
    """Combine policies: each hook is forwarded to every member that overrides it.

    ``price`` is chained, ``on_dispatch`` uses the first member that overrides it
    (otherwise default matching), ``on_driver_idle`` returns the first non-None target.
    """

    def __init__(self, *policies: Policy, name: Optional[str] = None, matching: Optional[MatchingParams] = None):
        super().__init__(matching=matching)
        self.policies = list(policies)
        self.name = name or "+".join(p.name for p in policies)
        self.tick_intervals = {}
        for p in policies:
            self.tick_intervals.update(p.tick_intervals)
        windows = [p.batch_window for p in policies if p.batch_window]
        self.batch_window = windows[0] if windows else None

    def _members(self, hook: str):
        return [p for p in self.policies if getattr(type(p), hook) is not getattr(Policy, hook)]

    def on_start(self, sim):
        for p in self.policies:
            p.on_start(sim)

    def on_end(self, sim):
        for p in self.policies:
            p.on_end(sim)

    def price(self, sim, rider, quote: Quote) -> Quote:
        for p in self.policies:
            quote = p.price(sim, rider, quote)
        return quote

    def on_request(self, sim, rider):
        for p in self._members("on_request"):
            p.on_request(sim, rider)

    def on_timer(self, sim, rider, **payload):
        for p in self._members("on_timer"):
            p.on_timer(sim, rider, **payload)

    def on_rider_cancel(self, sim, rider):
        for p in self._members("on_rider_cancel"):
            p.on_rider_cancel(sim, rider)

    def on_dropoff(self, sim, rider, driver):
        for p in self._members("on_dropoff"):
            p.on_dropoff(sim, rider, driver)

    def on_dispatch(self, sim, open_jobs, idle_drivers):
        members = self._members("on_dispatch")
        if members:
            return members[0].on_dispatch(sim, open_jobs, idle_drivers)
        return sim.default_dispatch(open_jobs, idle_drivers, self.matching)

    def on_driver_idle(self, sim, driver):
        for p in self._members("on_driver_idle"):
            target = p.on_driver_idle(sim, driver)
            if target is not None:
                return target
        return None

    def on_tick(self, sim, kind):
        for p in self.policies:
            p.on_tick(sim, kind)

    def describe(self):
        return {"name": self.name, "members": [p.describe() for p in self.policies]}


# Registry of named policies for the CLI and configs.
POLICIES = {
    "baseline": Baseline,
    "pool_after_wait": PoolAfterWait,
    "surge": SurgePricing,
    "heatmap_reposition": HeatmapReposition,
}
