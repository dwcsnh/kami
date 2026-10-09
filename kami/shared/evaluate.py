"""Evaluator thuần: từ xe thật, dwell, deadline và extra ride từng khách."""
from dataclasses import dataclass
import math

from kami.core.agents import Stop


@dataclass
class SharedPlanEval:
    stops: list
    pickup_t: dict
    dropoff_t: dict
    direct_baseline_s: dict
    extra_ride_s: dict
    total_dist_m: float
    total_dropoff_s: float
    overlap_s: float

    @property
    def order(self):
        return tuple((s.kind, s.rider_id) for s in self.stops)


class Evaluator:
    """Cache/query counters chỉ có hiệu lực trong một dispatch tick."""
    def __init__(self, sim):
        self.sim = sim
        self.cache = {}
        self.reachable_cache = {}

    def reachable(self, o, d, group):
        """Reject legacy crow-fly fallback on disconnected/group-forbidden roads."""
        net = self.sim.network
        if not hasattr(net, 'graph') or o == d:
            return True
        # RoadNetwork's common SCC excludes transit through stop-only nodes.
        common = getattr(net, '_scc', set())
        if o in common and d in common:
            return True
        group = self.sim.traffic.group(group)
        key = (o, group)
        if key not in self.reachable_cache:
            g = net.graph
            allowed = g.allow.get(group)
            seen, stack = {o}, [o]
            while stack:
                n = stack.pop()
                for other in g.out_edges[n]:
                    if other in seen or (allowed is not None and not allowed[g.edge_index[(n, other)]]):
                        continue
                    seen.add(other)
                    if not g.stop_only[other]:
                        stack.append(other)
            self.reachable_cache[key] = seen
        return d in self.reachable_cache[key]

    def route(self, o, d, t, group):
        key = (o, d, t, group)
        if key not in self.cache:
            self.sim.shared_stats["route_queries"] += 1
            try:
                self.cache[key] = (self.sim.traffic.estimate(o, d, t, group=group)
                                   if self.reachable(o, d, group) else (math.inf, math.inf))
            except (ValueError, KeyError):
                self.cache[key] = (math.inf, math.inf)
        return self.cache[key]

    def evaluate(self, driver, riders, stops):
        sim = self.sim
        if not driver.available or driver.capacity < len(riders):
            return None
        loc, t, dist = sim.current_loc(driver), sim.t, 0.0
        pickup, dropoff, baseline = {}, {}, {}
        for s in stops:
            tt, dd = self.route(loc, s.loc, t, driver.group)
            if not math.isfinite(tt) or not math.isfinite(dd):
                return None
            t, loc, dist = t + tt, s.loc, dist + dd
            if s.kind == "pickup":
                pickup[s.rider_id] = t
                r = sim.riders[s.rider_id]
                deadline = min(r.pickup_deadline, r.attrs.get("latest_pickup", math.inf))
                if t > deadline + 1e-9:
                    return None
                direct, _ = self.route(r.origin, r.dest, t, driver.group)
                if not math.isfinite(direct):
                    return None
                baseline[r.id] = sim.config.boarding_s + direct
                t += sim.config.boarding_s
            else:
                dropoff[s.rider_id] = t
                if t > sim.riders[s.rider_id].attrs.get("latest_dropoff", math.inf) + 1e-9:
                    return None
                t += sim.config.alighting_s
        extra = {r.id: max(0.0, dropoff[r.id] - pickup[r.id] - baseline[r.id]) for r in riders}
        overlap = max(0.0, min(dropoff.values()) - max(pickup.values())) if len(riders) == 2 else 0.0
        if len(riders) == 2 and (overlap <= 0 or any(x > sim.config.shared_ride.max_shared_extra_ride_s + 1e-9 for x in extra.values())):
            return None
        return SharedPlanEval(list(stops), pickup, dropoff, baseline, extra, dist,
                              sum(x - sim.t for x in dropoff.values()), overlap)

    def plans(self, driver, riders):
        if len(riders) == 1:
            r = riders[0]
            orders = [[Stop("pickup", r.id, r.origin), Stop("dropoff", r.id, r.dest)]]
        else:
            a, b = riders
            orders = [[Stop("pickup", x.id, x.origin), Stop("pickup", y.id, y.origin),
                       Stop("dropoff", u.id, u.dest), Stop("dropoff", v.id, v.dest)]
                      for x, y in ((a, b), (b, a)) for u, v in ((a, b), (b, a))]
        return [ev for stops in orders if (ev := self.evaluate(driver, riders, stops)) is not None]
