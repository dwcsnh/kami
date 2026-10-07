"""Metric catalogue (design doc §10.2).

``compute(sim)`` returns a flat ``{name: float}`` dict. Names are namespaced
``rider.* / driver.* / platform.* / ops.* / fair.*`` so decision rules and
reports can refer to them by string. Times are in **minutes**, money in VND,
distances in km, rates in [0, 1].

Riders are counted when they *requested* inside the measurement window
``[scenario.tags['measure_from'], scenario.t_end)`` (warm-up excluded).
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, Hashable, Iterable, List, Optional, Sequence

from kami.core.agents import RiderState

if TYPE_CHECKING:  # pragma: no cover
    from kami.core.engine import Simulation

NaN = float("nan")

#: direction of "better" for every metric (+1 higher is better, -1 lower is better, 0 diagnostic)
DIRECTION = {
    "rider.conversion": 1, "rider.completion_rate": 1, "rider.cancel_rate": -1, "rider.no_driver_rate": -1,
    "rider.wait_mean": -1, "rider.wait_p90": -1, "rider.wait_p95": -1, "rider.eta_error_abs": -1,
    "rider.travel_time_p90": -1, "rider.fare_mean": 0, "rider.pool_rate": 0, "rider.detour_ratio": -1,
    "driver.utilization": 1, "driver.earnings_per_hour": 1, "driver.idle_gap_mean": -1,
    "driver.empty_km_share": -1, "driver.rejection_rate": 0, "driver.earnings_gini": -1,
    "platform.trips": 1, "platform.gmv": 1, "platform.revenue": 1, "platform.contribution_margin": 1,
    "ops.trips_per_vehicle_hour": 1, "ops.pax_km_per_vehicle_km": 1, "ops.vehicle_km": -1,
    "fair.zone_wait_p90_max": -1, "fair.zone_completion_min": 1,
}


def percentile(xs: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile, q in [0, 100]; NaN for empty input."""
    if not xs:
        return NaN
    s = sorted(xs)
    k = (len(s) - 1) * q / 100.0
    f, c = math.floor(k), math.ceil(k)
    return s[f] if f == c else s[f] + (s[c] - s[f]) * (k - f)


def mean(xs: Iterable[float]) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else NaN


def ratio(a: float, b: float) -> float:
    return a / b if b else NaN


def gini(xs: Sequence[float]) -> float:
    xs = sorted(x for x in xs if x >= 0)
    n = len(xs)
    if n == 0 or sum(xs) == 0:
        return NaN
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return (2 * cum) / (n * sum(xs)) - (n + 1) / n


def measured_riders(sim: "Simulation"):
    t0 = sim.scenario.tags.get("measure_from", sim.scenario.t_start)
    return [r for r in sim.riders.values() if t0 <= r.t_request < sim.scenario.t_end]


def compute(sim: "Simulation") -> Dict[str, float]:
    riders = measured_riders(sim)
    booked = [r for r in riders if r.t_booked is not None]
    done = [r for r in booked if r.state == RiderState.DONE]
    cancelled = [r for r in booked if r.state == RiderState.CANCELLED]
    picked = [r for r in booked if r.t_pickup is not None]
    waits = [(r.t_pickup - r.t_booked) / 60 for r in picked]
    eta_err = [(r.t_pickup - r.eta_promised) / 60 for r in picked if r.eta_promised is not None]
    pooled_done = [r for r in done if r.pooled]
    pooled_all = [r for r in booked if r.pooled]
    offers = sum(r.pool_offers for r in riders)
    accepts = sum(r.pool_accepts for r in riders)
    fm = sim.fare_model

    m: Dict[str, float] = {
        "rider.requests": len(riders),
        "rider.booked": len(booked),
        "rider.conversion": ratio(len(booked), len(riders)),
        "rider.completion_rate": ratio(len(done), len(booked)),
        "rider.cancel_rate": ratio(len(cancelled), len(booked)),
        "rider.cancel_rate_waiting": ratio(sum(r.cancel_phase == "waiting" for r in cancelled), len(booked)),
        "rider.cancel_rate_matched": ratio(sum(r.cancel_phase == "matched" for r in cancelled), len(booked)),
        "rider.no_driver_rate": ratio(sum(r.t_matched is None for r in cancelled), len(booked)),
        "rider.unfinished_rate": ratio(sum(not r.is_terminal for r in booked), len(booked)),
        "rider.wait_mean": mean(waits),
        "rider.wait_p50": percentile(waits, 50),
        "rider.wait_p90": percentile(waits, 90),
        "rider.wait_p95": percentile(waits, 95),
        "rider.eta_error_abs": mean(abs(e) for e in eta_err),
        "rider.eta_error_signed": mean(eta_err),
        "rider.travel_time_p90": percentile([(r.t_dropoff - r.t_booked) / 60 for r in done], 90),
        "rider.fare_mean": mean(r.fare + r.surcharge for r in done),
        "rider.pool_rate": ratio(len(pooled_done), len(done)),
        "rider.pool_offer_accept_rate": ratio(accepts, offers),
        "rider.pool_offers": offers,
        "rider.detour_ratio": mean((r.t_dropoff - r.t_pickup) / max(r.direct_tt, 1) for r in pooled_done),
        "rider.pooled_travel_time_p90": percentile([(r.t_dropoff - r.t_booked) / 60 for r in pooled_done], 90),
        "rider.pooled_cancel_rate": ratio(sum(r.state == RiderState.CANCELLED for r in pooled_all), len(pooled_all)),
    }

    drivers = [d for d in sim.drivers.values() if d.online_time > 0]
    online_h = sum(d.online_time for d in drivers) / 3600
    veh_km = sum(d.dist_total for d in drivers) / 1000
    empty_km = sum(d.dist_empty for d in drivers) / 1000
    gaps = [g / 60 for d in drivers for g in d.idle_gaps]
    all_done = [r for r in sim.riders.values() if r.state == RiderState.DONE]
    m.update({
        "driver.online_hours": online_h,
        "driver.utilization": ratio(sum(d.occupied_time for d in drivers), sum(d.online_time for d in drivers)),
        "driver.busy_share": ratio(sum(d.busy_time for d in drivers), sum(d.online_time for d in drivers)),
        "driver.earnings_per_hour": ratio(sum(d.earnings for d in drivers), online_h),
        "driver.idle_gap_mean": mean(gaps),
        "driver.empty_km_share": ratio(empty_km, veh_km),
        "driver.rejection_rate": ratio(sum(d.rejections for d in drivers), sum(d.offers for d in drivers)),
        "driver.earnings_gini": gini([d.earnings / max(d.online_time / 3600, 1e-9) for d in drivers]),
        "platform.trips": len(done),
        "platform.gmv": sum(r.fare + r.surcharge for r in done),
        "platform.revenue": sum(fm.platform_revenue(r.fare, r.surcharge) for r in done),
        "platform.surcharge_total": sum(r.surcharge for r in done),
        "platform.pooled_jobs": sum(1 for j in sim.jobs.values() if j.pooled),
        "ops.vehicle_km": veh_km,
        "ops.empty_km": empty_km,
        "ops.trips_per_vehicle_hour": ratio(len(all_done), online_h),
        "ops.pax_km_per_vehicle_km": ratio(sum(r.direct_dist for r in all_done) / 1000, veh_km),
    })
    # No incentive programmes are modelled yet, so margin == revenue minus discounts already in surcharges.
    m["platform.contribution_margin"] = m["platform.revenue"]

    zw = by_zone(sim, riders)
    p90s = [v["wait_p90"] for v in zw.values() if v["booked"] >= 10 and not math.isnan(v["wait_p90"])]
    comps = [v["completion_rate"] for v in zw.values() if v["booked"] >= 10]
    m["fair.zone_wait_p90_max"] = max(p90s) if p90s else NaN
    m["fair.zone_wait_p90_spread"] = (max(p90s) - min(p90s)) if p90s else NaN
    m["fair.zone_completion_min"] = min(comps) if comps else NaN
    return m


def by_zone(sim: "Simulation", riders=None) -> Dict[Hashable, Dict[str, float]]:
    """Per-origin-zone rider metrics (fairness & guardrails like "no zone p90 wait +10%")."""
    riders = riders if riders is not None else measured_riders(sim)
    groups: Dict[Hashable, List] = {}
    for r in riders:
        groups.setdefault(r.zone, []).append(r)
    out = {}
    for z, rs in groups.items():
        booked = [r for r in rs if r.t_booked is not None]
        picked = [(r.t_pickup - r.t_booked) / 60 for r in booked if r.t_pickup is not None]
        out[z] = {
            "requests": len(rs), "booked": len(booked),
            "completion_rate": ratio(sum(r.state == RiderState.DONE for r in booked), len(booked)),
            "cancel_rate": ratio(sum(r.state == RiderState.CANCELLED for r in booked), len(booked)),
            "wait_p90": percentile(picked, 90), "wait_mean": mean(picked),
        }
    return out


def by_hour(sim: "Simulation") -> Dict[int, Dict[str, float]]:
    """Per-hour rider metrics (baseline calibration against history, design doc §11)."""
    groups: Dict[int, List] = {}
    for r in measured_riders(sim):
        groups.setdefault(int(r.t_request // 3600) % 24, []).append(r)
    out = {}
    for h, rs in sorted(groups.items()):
        booked = [r for r in rs if r.t_booked is not None]
        picked = [(r.t_pickup - r.t_booked) / 60 for r in booked if r.t_pickup is not None]
        out[h] = {"requests": len(rs), "trips": sum(r.state == RiderState.DONE for r in booked),
                  "cancel_rate": ratio(sum(r.state == RiderState.CANCELLED for r in booked), len(booked)),
                  "wait_mean": mean(picked)}
    return out
