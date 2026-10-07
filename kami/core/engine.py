"""kami simulation engine (design doc §4).

Hybrid time model: every agent action is an individual event; batch
matching runs on a periodic ``DISPATCH_TICK``. The core loop is tiny::

    while queue:
        ev = heappop(queue)            # (time, priority, seq) -> deterministic tie-break
        self.t = ev.time
        handler(ev.payload)            # "_on_<kind>"

Mandatory techniques implemented here:

* deterministic tie-break ``(time, priority, seq)``;
* lazy invalidation — scheduled events carry a version/token and handlers
  ignore them when the agent's state moved on;
* plan vs. reality — the platform promises ETAs with its own (possibly
  incident-blind) estimate, the drive itself uses the real traffic state.
"""
from __future__ import annotations

import heapq
import time as _time
from dataclasses import dataclass, field
from typing import Any, Dict, Hashable, Iterable, List, Optional, Sequence, Tuple

from kami.behavior.protocols import Context, TripOffer
from kami.behavior.registry import BehaviorSuite
from kami.core.agents import (Driver, DriverState, Job, Leg, PoolOffer, Quote, Rider, RiderState, Stop)
from kami.core.crn import CRN
from kami.core.events import DEFAULT_PRIORITY, EVENT_PRIORITY, Event, EventType as E
from kami.eventlog import EventLog
from kami.matching import MatchingParams, match
from kami.policy.base import Policy
from kami.pooling import Pooling, PoolingParams
from kami.pricing import FareModel
from kami.scenario import Scenario
from kami.traffic import Incident, TrafficLayer


@dataclass
class SimConfig:
    batch_window: float = 10.0        # DISPATCH_TICK interval (s)
    boarding_s: float = 30.0
    alighting_s: float = 20.0
    idle_decision_s: float = 120.0    # idle time before the IdleMoveModel is asked
    idle_recheck_s: float = 300.0     # after "stay", ask again later
    drain_s: float = 3600.0           # keep simulating after t_end so started trips finish
    cancel_step_s: float = 20.0       # integration step of the cancellation hazard
    cancel_lookahead_s: float = 1800.0
    default_quote_eta: float = 900.0  # ETA shown when no driver is visible
    traffic_update_s: float = 3600.0  # TRAFFIC_UPDATE period (time-dependent road networks)
    record_events: bool = True
    fare: FareModel = field(default_factory=FareModel)
    pooling: PoolingParams = field(default_factory=PoolingParams)


class BehaviorAPI:
    """``sim.behavior``: models of the suite bound to the agents' CRN numbers."""

    def __init__(self, sim: "Simulation", suite: BehaviorSuite):
        self.sim, self.suite = sim, suite

    def p_pool_accept(self, rider: Rider, offer) -> float:
        sim = self.sim
        if not isinstance(offer, PoolOffer):
            partner, detour = None, 0.0
            last = sim.pooling.last_eval.get(rider.id)
            if last:
                partner, ev = last
                detour = ev.detour.get(rider.id, 0.0)
            offer = PoolOffer(surcharge=float(offer), waited=sim.t - (rider.t_booked or sim.t), detour=detour,
                              partner_id=partner)
        return self.suite.pool_accept.p_accept(rider, offer, sim.context(rider.origin)), offer

    def pool_accept(self, rider: Rider, offer) -> bool:
        """Show a pooling offer (``PoolOffer`` or a surcharge amount) and return the rider's decision."""
        sim = self.sim
        p, offer = self.p_pool_accept(rider, offer)
        rider.pool_offers += 1
        u = sim.crn.u("pool_accept", rider.id, rider.pool_offers)
        ok = u < p
        if ok:
            rider.pool_accepts += 1
        sim.log.add(sim.t, "POOL_OFFER", rider.id, None, surcharge=offer.surcharge, detour=round(offer.detour, 1),
                    p=round(p, 4), accepted=ok, partner=offer.partner_id)
        return ok


class Simulation:
    def __init__(self, scenario: Scenario, policy: Optional[Policy] = None,
                 behavior: Optional[BehaviorSuite] = None, config: Optional[SimConfig] = None,
                 crn_seed: Optional[int] = None):
        self.scenario = scenario
        self.policy = policy or Policy()
        self.config = config or SimConfig()
        self.network = scenario.network
        self.zones = scenario.zones
        self.traffic = TrafficLayer(scenario.network, scenario.zones, **scenario.traffic)
        self.crn = CRN(scenario.seed if crn_seed is None else crn_seed)
        self.behavior = BehaviorAPI(self, behavior or BehaviorSuite())
        self.pooling = Pooling(self, self.config.pooling)
        self.fare_model = self.config.fare
        self.log = EventLog(self.config.record_events)

        self.t = scenario.t_start
        self.t_stop = scenario.t_end + self.config.drain_s
        self._q: List[Event] = []
        self._seq = 0
        self.riders: Dict[int, Rider] = {}
        self.drivers: Dict[int, Driver] = {}
        self.jobs: Dict[int, Job] = {}
        self.open_jobs: Dict[int, Job] = {}       # insertion-ordered: oldest first
        self._job_seq = 0
        self._req_specs = {r.id: r for r in scenario.requests}
        self._pending_requests = len(scenario.requests)
        self._recent_requests: List[Tuple[float, Hashable]] = []
        self.surge: Dict[Hashable, float] = {}
        self._incident_specs = {i.id: i for i in scenario.incidents}
        self.events_processed = 0
        self.wall_time = 0.0
        self._finished = False

    # ===================================================================== scheduling
    def _push(self, t: float, kind: E, **payload) -> None:
        self._seq += 1
        heapq.heappush(self._q, Event(t, EVENT_PRIORITY.get(kind, DEFAULT_PRIORITY), self._seq, kind, payload))

    def schedule(self, t: float, kind: str = "POLICY_TIMER", **payload) -> None:
        """Policy API: schedule a ``POLICY_TIMER`` (payload ``r=``/``rider=`` passes a rider to ``on_timer``)."""
        if E(kind) != E.POLICY_TIMER:
            raise ValueError("policies may only schedule POLICY_TIMER events")
        r = payload.pop("r", None) or payload.pop("rider", None)
        if r is not None:
            payload["rider_id"] = r.id if isinstance(r, Rider) else int(r)
        self._push(max(t, self.t), E.POLICY_TIMER, **payload)

    # ===================================================================== run
    def run(self) -> "Simulation":
        if self._finished:
            raise RuntimeError("a Simulation object can only run once; build a new one")
        wall = _time.perf_counter()
        sc = self.scenario
        for d in sc.drivers:
            drv = Driver(d.id, d.loc, d.shift_start, d.shift_end, dict(d.attrs), d.capacity)
            drv.home_zone = self.zones.zone_of(d.loc)
            drv._state_since = d.shift_start
            self.drivers[d.id] = drv
            self._push(max(d.shift_start, sc.t_start), E.DRIVER_ONLINE, driver_id=d.id)
            self._push(d.shift_end, E.DRIVER_OFFLINE, driver_id=d.id)
        for r in sc.requests:
            self._push(r.t, E.REQUEST_CREATED, request_id=r.id)
        for t, w in sc.weather:
            self._push(t, E.WEATHER_CHANGE, weather=w)
        for inc in sc.incidents:
            self._push(inc.t_start, E.INCIDENT_START, incident_id=inc.id)
            self._push(inc.t_end, E.INCIDENT_END, incident_id=inc.id)
        t = sc.t_start
        while t < sc.t_end:
            self._push(t, E.TRAFFIC_UPDATE)
            t += self.config.traffic_update_s
        self._push(sc.t_start, E.DISPATCH_TICK)
        for kind, every in self.policy.tick_intervals.items():
            self._push(sc.t_start, E(kind), every=every)
        self.policy.on_start(self)

        q = self._q
        while q:
            ev = heapq.heappop(q)
            if ev.time > self.t_stop:
                break
            self.t = ev.time
            self.events_processed += 1
            getattr(self, "_on_" + ev.kind.value.lower())(**ev.payload)

        self.t = min(max(self.t, sc.t_end), self.t_stop)
        self._finalise()
        self.policy.on_end(self)
        self._finished = True
        self.wall_time = _time.perf_counter() - wall
        return self

    def _finalise(self) -> None:
        for d in self.drivers.values():
            if d.state != DriverState.OFFLINE:
                if d.leg is not None:
                    self._close_leg(d, partial=True)
                self._set_driver_state(d, DriverState.OFFLINE)

    def metrics(self) -> Dict[str, float]:
        """Metric catalogue of design doc §10.2 for this (finished) run."""
        from kami.metrics import compute

        return compute(self)

    # ===================================================================== helpers (public, read-only)
    def context(self, node: int) -> Context:
        inc = self.traffic.incident_at(node)
        return Context(t=self.t, hour=int(self.t // 3600) % 24, weather=self.traffic.weather,
                       zone=self.zones.zone_of(node),
                       incident_cancel_multiplier=inc.cancel_multiplier if inc else 1.0)

    def current_loc(self, d: Driver) -> int:
        """Best estimate of a (possibly moving) driver's node right now."""
        leg = d.leg
        if leg is None or self.t >= leg.t_arrive:
            return leg.dest if leg is not None and self.t >= leg.t_arrive else d.loc
        return self._leg_position(leg)[0]

    def job_first_pickup(self, job: Job) -> int:
        if job.stops:
            return job.stops[0].loc
        return self.riders[job.rider_ids[0]].origin

    def job_size(self, job: Job) -> int:
        return len(job.rider_ids)

    def idle_drivers(self) -> List[Driver]:
        return [d for d in self.drivers.values() if d.available]

    def zone_stats(self, window_s: float = 900.0) -> Dict[Hashable, Dict[str, float]]:
        """Recent requests, open jobs and idle drivers per zone (for surge / repositioning policies)."""
        stats: Dict[Hashable, Dict[str, float]] = {}
        horizon = self.t - window_s
        self._recent_requests = [(t, z) for t, z in self._recent_requests if t >= horizon]
        for _, z in self._recent_requests:
            stats.setdefault(z, {"requests": 0, "open": 0, "idle": 0})["requests"] += 1
        for job in self.open_jobs.values():
            z = self.zones.zone_of(self.job_first_pickup(job))
            stats.setdefault(z, {"requests": 0, "open": 0, "idle": 0})["open"] += 1
        for d in self.idle_drivers():
            z = self.zones.zone_of(self.current_loc(d))
            stats.setdefault(z, {"requests": 0, "open": 0, "idle": 0})["idle"] += 1
        return stats

    # ===================================================================== policy API (actions)
    def default_dispatch(self, jobs: Sequence[Job], drivers: Sequence[Driver],
                         params: Optional[MatchingParams] = None) -> List[Tuple[Job, Driver]]:
        return match(self, list(jobs), list(drivers), params or MatchingParams())

    def offer_trip(self, driver: Driver, job: Job) -> bool:
        """Offer ``job`` to ``driver``; the driver-acceptance model decides. Returns True if assigned."""
        if not driver.available or job.id not in self.open_jobs or driver.id in job.tabu:
            return False
        loc = self.current_loc(driver)
        origin = self.job_first_pickup(job)
        eta, _ = self.traffic.estimate(loc, origin, self.t)
        fare = sum(self.riders[r].fare for r in job.rider_ids)
        trip_dist = sum(self.riders[r].direct_dist for r in job.rider_ids)
        dest_zone = self.zones.zone_of(self.riders[job.rider_ids[-1]].dest)
        offer = TripOffer(eta, self.fare_model.driver_payout(fare), trip_dist, dest_zone, job.pooled)
        driver.offers += 1
        p = self.behavior.suite.driver_accept.p_accept(driver, offer, self.context(loc))
        u = self.crn.u("driver_accept", driver.id, job.id, len(job.tabu))
        self.log.add(self.t, E.TRIP_OFFERED, job.rider_ids[0], driver.id, job=job.id, eta=round(eta, 1),
                     p=round(p, 4))
        if u >= p:
            driver.rejections += 1
            job.tabu.add(driver.id)
            self.log.add(self.t, E.TRIP_REJECTED, job.rider_ids[0], driver.id, job=job.id)
            return False
        self.assign(driver, job)
        return True

    def assign(self, driver: Driver, job: Job) -> None:
        """Bind ``job`` to ``driver`` (no acceptance step — use for employed drivers / forced dispatch)."""
        if job.id not in self.open_jobs:
            raise ValueError(f"job {job.id} is not open")
        if not driver.available:
            raise ValueError(f"driver {driver.id} is not available")
        self._interrupt_leg(driver)
        del self.open_jobs[job.id]
        job.driver_id = driver.id
        driver.job_ids.append(job.id)
        stops = list(job.stops) if job.stops else [Stop("pickup", job.rider_ids[0], self.riders[job.rider_ids[0]].origin),
                                                     Stop("dropoff", job.rider_ids[0], self.riders[job.rider_ids[0]].dest)]
        driver.plan = stops
        ev = self.pooling.evaluate(driver.loc, self.t, stops, check=False)
        for rid in job.rider_ids:
            r = self.riders[rid]
            r.state = RiderState.MATCHED
            r.version += 1
            r.driver_id = driver.id
            r.t_matched = self.t
            r.eta_promised = ev.pickup_t.get(rid, self.t)
            self._arm_cancel(r, "matched")
            self.log.add(self.t, E.TRIP_ACCEPTED, rid, driver.id, job=job.id,
                         eta=round(r.eta_promised - self.t, 1), pooled=job.pooled)
        self._set_driver_state(driver, DriverState.EN_ROUTE)
        self._start_next_leg(driver)

    def merge_jobs(self, r: Rider, partner: Rider, surcharge: float = 0.0,
                   partner_surcharge: Optional[float] = None) -> bool:
        """Serve ``r`` and ``partner`` with one vehicle. Both must be WAITING, or one WAITING and the
        other MATCHED (inserted into that driver's plan). Returns False if infeasible."""
        ps = surcharge if partner_surcharge is None else partner_surcharge
        a, b = (r, partner) if r.state == RiderState.WAITING else (partner, r)
        if a.pooled:
            return False
        if a.state != RiderState.WAITING or b.state not in (RiderState.WAITING, RiderState.MATCHED):
            return False
        if b.state == RiderState.WAITING:
            if a.pooled or b.pooled:
                return False
            ev = self.pooling.plan_pair(a, b)
            if ev is None:
                return False
            for x in (a, b):
                self.open_jobs.pop(x.job_id, None)
            job = self._new_job([a.id, b.id], pooled=True, stops=ev.stops)
            self.open_jobs[job.id] = job
            for x in (a, b):
                x.job_id, x.pooled = job.id, True
                x.version += 1
        else:
            drv = self.drivers[b.driver_id]
            ev = self.pooling.driver_plan_with(drv, a)
            if ev is None:
                return False
            self.open_jobs.pop(a.job_id, None)
            job = self.jobs[b.job_id]
            job.rider_ids.append(a.id)
            job.pooled = True
            a.job_id, a.pooled, b.pooled = job.id, True, True
            a.state = RiderState.MATCHED
            a.version += 1
            a.driver_id = drv.id
            a.t_matched = self.t
            a.eta_promised = ev.pickup_t.get(a.id, self.t)
            self._interrupt_leg(drv)
            drv.plan = list(ev.stops)
            self._arm_cancel(a, "matched")
            self._start_next_leg(drv)
        r.surcharge += surcharge
        partner.surcharge += ps
        self.log.add(self.t, "POOL_MERGE", r.id, None, partner=partner.id, job=job.id, surcharge=surcharge)
        return True

    def reposition(self, driver: Driver, node: int) -> bool:
        """Direct an available driver to ``node`` (platform repositioning)."""
        if not driver.available:
            return False
        self._interrupt_leg(driver)
        self._move_idle(driver, node, "reposition")
        return True

    def set_surge(self, zone: Hashable, multiplier: float) -> None:
        self.surge[zone] = multiplier

    # ===================================================================== event handlers: rider
    def _new_job(self, rider_ids: List[int], pooled: bool = False, stops: Optional[List[Stop]] = None) -> Job:
        self._job_seq += 1
        job = Job(self._job_seq, list(rider_ids), self.t, pooled=pooled, stops=list(stops or []))
        self.jobs[job.id] = job
        return job

    def _on_request_created(self, request_id: int) -> None:
        spec = self._req_specs[request_id]
        self._pending_requests -= 1
        r = Rider(spec.id, self.t, spec.origin, spec.dest, dict(spec.attrs))
        r.zone, r.dest_zone = self.zones.zone_of(r.origin), self.zones.zone_of(r.dest)
        r.direct_tt, r.direct_dist = self.traffic.travel(r.origin, r.dest, self.t)
        self.riders[r.id] = r
        self._recent_requests.append((self.t, r.zone))
        self.log.add(self.t, E.REQUEST_CREATED, r.id, None, origin=r.origin, dest=r.dest, zone=r.zone)

        eta = self._quote_eta(r.origin)
        surge = self.surge.get(r.zone, 1.0)
        quote = Quote(fare=self.fare_model.fare(r.direct_dist, r.direct_tt, surge), eta=eta, surge=surge)
        quote = self.policy.price(self, r, quote)
        r.quote = quote
        p = self.behavior.suite.booking.p_book(r, quote, self.context(r.origin))
        self.log.add(self.t, E.OFFER_SHOWN, r.id, None, fare=quote.fare, eta=round(quote.eta, 1),
                     surge=quote.surge, p=round(p, 4))
        if self.crn.u("book", r.id) >= p:
            r.state = RiderState.DECLINED
            r.version += 1
            self.log.add(self.t, E.OFFER_REJECTED, r.id, None)
            return
        r.state = RiderState.WAITING
        r.version += 1
        r.t_booked = self.t
        r.fare = quote.fare
        r.surcharge = quote.surcharge
        job = self._new_job([r.id])
        r.job_id = job.id
        self.open_jobs[job.id] = job
        self.log.add(self.t, E.OFFER_ACCEPTED, r.id, None, job=job.id)
        self._arm_cancel(r, "waiting")
        self.policy.on_request(self, r)

    def _quote_eta(self, origin: int) -> float:
        ox, oy = self.network.coords(origin)
        near = []
        for d in self.drivers.values():
            if d.available:
                x, y = self.network.coords(self.current_loc(d))
                near.append(((x - ox) ** 2 + (y - oy) ** 2, d.id, d))
        if not near:
            return self.config.default_quote_eta
        near.sort(key=lambda x: (x[0], x[1]))
        best = min(self.traffic.estimate(self.current_loc(d), origin, self.t)[0] for _, _, d in near[:3])
        return best

    # --- cancellation as a survival process -----------------------------------
    def _hazard_per_s(self, r: Rider, phase: str, tau: float, ctx: Context) -> float:
        waited_min = (tau - (r.t_booked or tau)) / 60.0
        if phase == "waiting":
            eta_shown = (r.quote.eta if r.quote else self.config.default_quote_eta) / 60.0
            model = self.behavior.suite.cancel_wait
        else:
            eta_shown = ((r.eta_promised or tau) - tau) / 60.0
            model = self.behavior.suite.cancel_matched
        return max(0.0, model.hazard(r, waited_min, eta_shown, ctx)) / 60.0

    def _accrue(self, r: Rider) -> None:
        """Integrate the hazard from the last checkpoint to now (before covariates change)."""
        if r.hazard_phase is None or r.hazard_t >= self.t:
            return
        ctx = self.context(r.origin)
        step = self.config.cancel_step_s
        tau, acc = r.hazard_t, 0.0
        while tau < self.t:
            dt = min(step, self.t - tau)
            acc += self._hazard_per_s(r, r.hazard_phase, tau + dt / 2, ctx) * dt
            tau += dt
        r.hazard_acc += acc
        r.hazard_t = self.t

    def _arm_cancel(self, r: Rider, phase: str) -> None:
        """Schedule the time at which the rider's cumulative hazard reaches its CRN budget.

        Budget ~ Exp(1) drawn from CRN key ("cancel_<phase>", rider). This is the
        inverse-transform method for a survival model with time-varying hazard.
        """
        if r.hazard_phase != phase:
            r.hazard_phase = phase
            r.hazard_acc = 0.0
            r.hazard_t = self.t
            r.hazard_budget = self.crn.exp("cancel_" + phase, r.id)
        else:
            self._accrue(r)
        r.cancel_token += 1
        token = r.cancel_token
        ctx = self.context(r.origin)
        step = self.config.cancel_step_s
        need = r.hazard_budget - r.hazard_acc
        tau, acc = self.t, 0.0
        end = min(self.t + self.config.cancel_lookahead_s, self.t_stop)
        while tau < end:
            h = self._hazard_per_s(r, phase, tau + step / 2, ctx) * step
            if acc + h >= need:
                frac = (need - acc) / h if h > 0 else 1.0
                self._push(tau + frac * step, E.RIDER_CANCEL, rider_id=r.id, token=token, recheck=False)
                return
            acc += h
            tau += step
        if end < self.t_stop:
            self._push(end, E.RIDER_CANCEL, rider_id=r.id, token=token, recheck=True)

    def _on_rider_cancel(self, rider_id: int, token: int, recheck: bool) -> None:
        r = self.riders[rider_id]
        if r.cancel_token != token or r.state not in (RiderState.WAITING, RiderState.MATCHED):
            return  # stale (lazy invalidation)
        if recheck:
            self._arm_cancel(r, r.hazard_phase)
            return
        phase = "waiting" if r.state == RiderState.WAITING else "matched"
        r.state = RiderState.CANCELLED
        r.version += 1
        r.t_cancel = self.t
        r.cancel_phase = phase
        job = self.jobs[r.job_id]
        if r.id in job.rider_ids:
            job.rider_ids.remove(r.id)
        job.stops = [s for s in job.stops if s.rider_id != r.id]
        if job.driver_id is None:
            if not job.rider_ids:
                self.open_jobs.pop(job.id, None)
        else:
            d = self.drivers[job.driver_id]
            heading_to_r = bool(d.plan) and d.plan[0].rider_id == r.id
            d.plan = [s for s in d.plan if s.rider_id != r.id]
            if heading_to_r:
                self._interrupt_leg(d)
                self._start_next_leg(d)
        self.log.add(self.t, E.RIDER_CANCEL, r.id, r.driver_id, phase=phase, waited=round(self.t - r.t_booked, 1))
        self.policy.on_rider_cancel(self, r)

    def _on_policy_timer(self, rider_id: Optional[int] = None, **payload) -> None:
        rider = self.riders.get(rider_id) if rider_id is not None else None
        if payload:
            self.policy.on_timer(self, rider, **payload)
        else:
            self.policy.on_timer(self, rider)

    # ===================================================================== event handlers: driver
    def _set_driver_state(self, d: Driver, new: DriverState) -> None:
        dt = self.t - d._state_since
        old = d.state
        if old != DriverState.OFFLINE:
            d.online_time += dt
        if old in (DriverState.EN_ROUTE, DriverState.ON_TRIP):
            d.busy_time += dt
        if old == DriverState.ON_TRIP:
            d.occupied_time += dt
        if old == DriverState.IDLE and new in (DriverState.EN_ROUTE, DriverState.ON_TRIP) and d.idle_since is not None:
            d.idle_gaps.append(self.t - d.idle_since)
        d.state = new
        d._state_since = self.t

    def _leg_position(self, leg: Leg) -> Tuple[int, float]:
        path = leg.path
        if path is None:
            path = leg.path = self.traffic.path(leg.origin, leg.dest)
        if self.t <= leg.t_depart:
            return leg.origin, 0.0
        frac = min(1.0, (self.t - leg.t_depart) / max(leg.t_arrive - leg.t_depart, 1e-9))
        total = path[-1][1] or 1.0
        node = leg.origin
        for n, cum in path:
            if cum / total <= frac:
                node = n
            else:
                break
        return node, frac

    def _close_leg(self, d: Driver, partial: bool = False) -> None:
        leg = d.leg
        if leg is None:
            return
        if partial and self.t < leg.t_arrive:
            node, frac = self._leg_position(leg)
        else:
            node, frac = leg.dest, 1.0
        dist = leg.dist * frac
        d.dist_total += dist
        if not leg.occupied:
            d.dist_empty += dist
        d.loc = node
        d.leg = None

    def _interrupt_leg(self, d: Driver) -> None:
        if d.leg is not None:
            self._close_leg(d, partial=True)
        d.plan_version += 1

    def _start_next_leg(self, d: Driver, depart_at: Optional[float] = None) -> None:
        if not d.plan:
            self._become_idle(d)
            return
        t0 = self.t if depart_at is None else depart_at
        stop = d.plan[0]
        tt, dist = self.traffic.travel(d.loc, stop.loc, t0)
        est, _ = self.traffic.estimate(d.loc, stop.loc, t0)
        d.leg = Leg(d.loc, stop.loc, t0, t0 + tt, dist, occupied=bool(d.onboard), purpose="stop",
                    promised_arrive=t0 + est)
        d.plan_version += 1
        self._set_driver_state(d, DriverState.ON_TRIP if d.onboard else DriverState.EN_ROUTE)
        self._push(t0 + tt, E.ARRIVE_STOP, driver_id=d.id, version=d.plan_version)

    def _on_arrive_stop(self, driver_id: int, version: int) -> None:
        d = self.drivers[driver_id]
        if version != d.plan_version or not d.plan:
            return
        self._close_leg(d)
        stop = d.plan.pop(0)
        r = self.riders[stop.rider_id]
        service = 0.0
        if stop.kind == "pickup":
            if r.state == RiderState.MATCHED:
                r.state = RiderState.ONBOARD
                r.version += 1
                r.t_pickup = self.t
                d.onboard.add(r.id)
                self._set_driver_state(d, DriverState.ON_TRIP)
                self.log.add(self.t, E.PICKUP, r.id, d.id, eta_error=round(self.t - (r.eta_promised or self.t), 1),
                             wait=round(self.t - r.t_booked, 1))
                service = self.config.boarding_s
        else:
            if r.state == RiderState.ONBOARD:
                r.state = RiderState.DONE
                r.version += 1
                r.t_dropoff = self.t
                d.onboard.discard(r.id)
                d.trips += 1
                d.earnings += self.fare_model.driver_payout(r.fare, r.surcharge)
                self.log.add(self.t, E.DROPOFF, r.id, d.id, fare=r.fare, surcharge=r.surcharge,
                             ivt=round(self.t - r.t_pickup, 1), pooled=r.pooled)
                self.policy.on_dropoff(self, r, d)
                service = self.config.alighting_s
        if d.plan:
            self._start_next_leg(d, depart_at=self.t + service)
        else:
            self._become_idle(d)

    def _become_idle(self, d: Driver) -> None:
        d.leg = None
        d.job_ids = [j for j in d.job_ids if any(self.riders[r].state in (RiderState.MATCHED, RiderState.ONBOARD)
                                                  for r in self.jobs[j].rider_ids)]
        if d.going_offline or self.t >= d.shift_end:
            self._go_offline(d)
            return
        ctx = self.context(d.loc)
        p_stop = self.behavior.suite.driver_shift.p_stop(d, ctx)
        if p_stop > 0 and self.crn.u("shift_stop", d.id, d.trips) < p_stop:
            self._go_offline(d)
            return
        if d.state != DriverState.IDLE:
            self._set_driver_state(d, DriverState.IDLE)
            d.idle_since = self.t
        d.plan_version += 1
        target = self.policy.on_driver_idle(self, d)
        if target is not None and target != d.loc:
            self._move_idle(d, target, "reposition")
        else:
            self._push(self.t + self.config.idle_decision_s, E.IDLE_MOVE, driver_id=d.id, version=d.plan_version)

    def _move_idle(self, d: Driver, node: int, purpose: str) -> None:
        tt, dist = self.traffic.travel(d.loc, node, self.t)
        d.leg = Leg(d.loc, node, self.t, self.t + tt, dist, occupied=False, purpose=purpose)
        d.plan_version += 1
        self.log.add(self.t, E.IDLE_MOVE, None, d.id, origin=d.loc, dest=node, purpose=purpose, tt=round(tt, 1))
        self._push(self.t + tt, E.IDLE_ARRIVE, driver_id=d.id, version=d.plan_version)

    def _on_idle_move(self, driver_id: int, version: int) -> None:
        d = self.drivers[driver_id]
        if version != d.plan_version or not d.available or d.leg is not None:
            return
        ctx = self.context(d.loc)
        dist = self.behavior.suite.idle_move.distribution(d, ctx, self.zones)
        d.idle_moves += 1
        k = self.crn.choice_index([w for _, w in dist], "idle_move", d.id, d.idle_moves)
        zone = dist[k][0] if dist else None
        if zone is None:
            d.plan_version += 1
            self._push(self.t + self.config.idle_recheck_s, E.IDLE_MOVE, driver_id=d.id, version=d.plan_version)
            return
        nodes = self.zones.location_nodes_in(zone)
        node = nodes[int(self.crn.u("idle_node", d.id, d.idle_moves) * len(nodes))] if nodes else d.loc
        self._move_idle(d, node, "idle")

    def _on_idle_arrive(self, driver_id: int, version: int) -> None:
        d = self.drivers[driver_id]
        if version != d.plan_version:
            return
        self._close_leg(d)
        if d.going_offline or self.t >= d.shift_end:
            self._go_offline(d)
            return
        d.plan_version += 1
        self._push(self.t + self.config.idle_decision_s, E.IDLE_MOVE, driver_id=d.id, version=d.plan_version)

    def _on_driver_online(self, driver_id: int) -> None:
        d = self.drivers[driver_id]
        d._state_since = self.t
        d.t_online = self.t
        self._set_driver_state(d, DriverState.IDLE)
        d.idle_since = self.t
        self.log.add(self.t, E.DRIVER_ONLINE, None, d.id, loc=d.loc)
        self._become_idle(d)

    def _on_driver_offline(self, driver_id: int) -> None:
        d = self.drivers[driver_id]
        if d.state == DriverState.OFFLINE:
            return
        if d.state == DriverState.IDLE:
            self._go_offline(d)
        else:
            d.going_offline = True

    def _go_offline(self, d: Driver) -> None:
        if d.leg is not None:
            self._close_leg(d, partial=True)
        d.plan_version += 1
        self._set_driver_state(d, DriverState.OFFLINE)
        self.log.add(self.t, E.DRIVER_OFFLINE, None, d.id, trips=d.trips, earnings=round(d.earnings))

    # ===================================================================== platform
    def _on_dispatch_tick(self) -> None:
        if self.open_jobs:
            idle = self.idle_drivers()
            if idle:
                pairs = self.policy.on_dispatch(self, list(self.open_jobs.values()), idle)
                for job, drv in pairs or ():
                    self.offer_trip(drv, job)
        window = self.policy.batch_window or self.config.batch_window
        busy = self.open_jobs or self._pending_requests > 0 or self.t < self.scenario.t_end
        if busy and self.t + window <= self.t_stop:
            self._push(self.t + window, E.DISPATCH_TICK)

    def _on_reposition_tick(self, every: float) -> None:
        self.policy.on_tick(self, E.REPOSITION_TICK.value)
        if self.t + every < self.scenario.t_end:
            self._push(self.t + every, E.REPOSITION_TICK, every=every)

    def _on_price_update(self, every: float) -> None:
        self.policy.on_tick(self, E.PRICE_UPDATE.value)
        if self.t + every < self.scenario.t_end:
            self._push(self.t + every, E.PRICE_UPDATE, every=every)

    # ===================================================================== environment
    def _riders_in_wait(self) -> List[Rider]:
        return [r for r in self.riders.values() if r.state in (RiderState.WAITING, RiderState.MATCHED)]

    def _environment_change(self, apply) -> None:
        """Accrue hazards with the old world, change it, then re-time trips and re-arm cancellations."""
        waiting = self._riders_in_wait()
        for r in waiting:
            self._accrue(r)
        apply()
        for d in self.drivers.values():
            leg = d.leg
            if leg is None or self.t >= leg.t_arrive:
                continue
            purpose, dest = leg.purpose, leg.dest
            self._interrupt_leg(d)
            if purpose == "stop":
                self._start_next_leg(d)
            else:
                self._move_idle(d, dest, purpose)
        for r in waiting:
            self._arm_cancel(r, r.hazard_phase)

    def _on_weather_change(self, weather: str) -> None:
        self._environment_change(lambda: self.traffic.set_weather(weather))
        self.log.add(self.t, E.WEATHER_CHANGE, weather=weather)

    def _on_incident_start(self, incident_id: str) -> None:
        spec = self._incident_specs[incident_id]
        zones = set(self.zones.zones_within(spec.center, spec.radius_m)) | {self.zones.zone_of(spec.center)}
        inc = Incident(spec.id, zones, spec.factor, spec.cancel_multiplier)
        self._environment_change(lambda: self.traffic.start_incident(inc))
        self.log.add(self.t, E.INCIDENT_START, incident=spec.id, zones=sorted(map(str, zones)), factor=spec.factor)

    def _on_incident_end(self, incident_id: str) -> None:
        self._environment_change(lambda: self.traffic.end_incident(incident_id))
        self.log.add(self.t, E.INCIDENT_END, incident=incident_id)

    def _on_traffic_update(self) -> None:
        update = getattr(self.network, "update_network", None)
        changed = bool(update(self.t)) if update else False
        self.log.add(self.t, E.TRAFFIC_UPDATE, multiplier=round(self.traffic.multiplier(self.t), 3),
                     network_changed=changed)
