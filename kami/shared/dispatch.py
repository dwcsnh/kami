"""Index points đón/đến; greedy shared-first, matching Exclusive trên xe còn lại."""
from collections import defaultdict
from itertools import product
import math

from kami.core.agents import RiderState
from kami.matching import solve
from kami.shared.evaluate import Evaluator


def candidate_pairs(sim, riders):
    radius = sim.config.shared_ride.candidate_radius_m
    cells = defaultdict(list)
    for a in sorted(riders, key=lambda r: r.id):
        xy = sim.network.coords(a.origin) + sim.network.coords(a.dest)
        cell = tuple(math.floor(x / radius) for x in xy)
        for delta in product((-1, 0, 1), repeat=4):
            for b in cells[tuple(c + d for c, d in zip(cell, delta))]:
                if sim.network.crow_dist(a.origin, b.origin) <= radius and sim.network.crow_dist(a.dest, b.dest) <= radius:
                    yield b, a
        cells[cell].append(a)


def nearby(sim, drivers, riders, params):
    eligible = [d for d in drivers if d.available and d.capacity >= len(riders)]
    ranked = sorted(eligible, key=lambda d: (min(sim.network.crow_dist(sim.current_loc(d), r.origin) for r in riders), d.id))
    k = params.candidates_per_job
    sim.shared_stats["drivers_truncated"] += max(0, len(ranked) - k)
    return ranked[:k]


def dispatch(sim, params):
    evaluator = Evaluator(sim)
    waiting = [sim.riders[j.rider_ids[0]] for j in sim.open_jobs.values() if len(j.rider_ids) == 1]
    shared = [r for r in waiting if r.service_preference == "shared_only" and r.state == RiderState.WAITING]
    options = []
    idle = sim.idle_drivers()
    for a, b in candidate_pairs(sim, shared):
        sim.shared_stats["candidate_pairs"] += 1
        for d in nearby(sim, idle, (a, b), params):
            for ev in evaluator.plans(d, (a, b)):
                sim.shared_stats["candidate_plans"] += 1
                deadlines = sorted((a.pickup_deadline, b.pickup_deadline))
                key = (*deadlines, ev.total_dropoff_s, ev.total_dist_m, a.id, b.id, d.id, ev.order)
                options.append((key, d, (a, b), ev))
    offered = set()
    for _, d, riders, ev in sorted(options, key=lambda x: x[0]):
        key = (d.id, *(r.id for r in riders))
        if key in offered:
            continue
        if d.available and all(r.state == RiderState.WAITING for r in riders):
            offered.add(key)
            sim._offer_shared_plan(d, riders, ev)
    pairs, plans = [], {}
    for r in waiting:
        if r.service_preference != "exclusive_only" or r.state != RiderState.WAITING:
            continue
        job = sim.open_jobs.get(r.job_id)
        if job is None:
            continue
        for d in nearby(sim, sim.idle_drivers(), (r,), params):
            if d.id in job.tabu:
                continue
            for ev in evaluator.plans(d, (r,)):
                eta = ev.pickup_t[r.id] - sim.t
                if eta <= params.max_pickup_eta:
                    pairs.append((eta - params.wait_weight * (sim.t - r.t_booked), job, d, eta))
                    plans[(job.id, d.id)] = ev
    for job, d in solve(pairs, params.solver):
        sim._offer_shared_plan(d, (sim.riders[job.rider_ids[0]],), plans[(job.id, d.id)])
