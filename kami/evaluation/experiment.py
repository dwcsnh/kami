"""Paired experiments with Common Random Numbers (design doc §10.1).

For every scenario ``s`` and seed ``k`` each arm runs on the *same* scenario
object and the *same* CRN seed, so the per-pair difference
``Δ = metric(treatment) − metric(baseline)`` contains the policy effect and
very little noise. ``crn=False`` gives the treatment arm a different CRN
seed — useful to measure how much variance CRN removes.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Hashable, List, Optional, Sequence, Tuple

from kami.behavior.registry import BehaviorSuite
from kami.core.engine import SimConfig, Simulation
from kami.metrics import by_zone, compute
from kami.policy.base import Policy
from kami.scenario import Scenario

ScenarioFn = Callable[[str, int], Scenario]     # (scenario name, seed) -> Scenario
PolicyFn = Callable[[], Policy]
BehaviorFn = Callable[[], BehaviorSuite]


@dataclass
class RunRecord:
    scenario: str
    seed: int
    arm: str
    metrics: Dict[str, float]
    zones: Dict[Hashable, Dict[str, float]]
    wall_s: float
    events: int


@dataclass
class Experiment:
    """Grid of (scenario × seed × arm) simulation runs.

    :param scenario_fn: builds the exogenous world for ``(name, seed)``; must be deterministic
    :param arms: arm name -> policy factory (first arm is the reference unless stated otherwise)
    :param behavior_fn: behaviour suite factory (one fresh suite per run)
    """

    scenario_fn: ScenarioFn
    scenarios: Sequence[str]
    seeds: Sequence[int]
    arms: Dict[str, PolicyFn]
    behavior_fn: BehaviorFn = BehaviorSuite
    config: SimConfig = field(default_factory=SimConfig)
    crn: bool = True
    keep_sims: bool = False

    def tasks(self) -> List[Tuple[str, int, str]]:
        return [(s, k, a) for s in self.scenarios for k in self.seeds for a in self.arms]

    def run_one(self, scenario: str, seed: int, arm: str, sc: Optional[Scenario] = None) -> RunRecord:
        sc = sc or self.scenario_fn(scenario, seed)
        arm_index = list(self.arms).index(arm)
        crn_seed = seed if (self.crn or arm_index == 0) else seed * 7919 + 104729 * arm_index
        sim = Simulation(sc, self.arms[arm](), self.behavior_fn(), self.config, crn_seed=crn_seed).run()
        rec = RunRecord(scenario, seed, arm, compute(sim), by_zone(sim), sim.wall_time, sim.events_processed)
        if self.keep_sims:
            rec.sim = sim  # type: ignore[attr-defined]
        return rec

    def run(self, n_jobs: int = 1, progress: bool = False) -> "ExperimentResult":
        t0 = time.perf_counter()
        records: List[RunRecord] = []
        if n_jobs == 1:
            for s in self.scenarios:
                for k in self.seeds:
                    sc = self.scenario_fn(s, k)   # build once, reuse for every arm
                    for a in self.arms:
                        records.append(self.run_one(s, k, a, sc))
                        if progress:
                            print(f"  {s} seed={k} {a}: {records[-1].wall_s:.2f}s", flush=True)
        else:
            global _EXPERIMENT
            _EXPERIMENT = self
            ctx = mp.get_context("fork")   # workers inherit the network instead of pickling it
            n = n_jobs if n_jobs > 0 else os.cpu_count() or 1
            pairs = [(s, k) for s in self.scenarios for k in self.seeds]
            with ctx.Pool(n) as pool:
                for recs in pool.imap(_run_pair, pairs):
                    records.extend(recs)
                    if progress:
                        print(f"  {recs[0].scenario} seed={recs[0].seed}: done", flush=True)
        return ExperimentResult(records, list(self.arms), time.perf_counter() - t0, self.crn)


_EXPERIMENT: Optional[Experiment] = None


def _run_pair(task):
    s, k = task
    exp = _EXPERIMENT
    sc = exp.scenario_fn(s, k)
    return [exp.run_one(s, k, a, sc) for a in exp.arms]


@dataclass
class ExperimentResult:
    records: List[RunRecord]
    arms: List[str]
    wall_s: float
    crn: bool

    def metrics(self, arm: str, scenario: Optional[str] = None) -> List[Dict[str, float]]:
        return [r.metrics for r in self.records if r.arm == arm and (scenario is None or r.scenario == scenario)]

    def pairs(self, baseline: str, treatment: str, scenario: Optional[str] = None):
        idx = {(r.scenario, r.seed, r.arm): r for r in self.records}
        out = []
        for (s, k, a), r in sorted(idx.items(), key=lambda x: (x[0][0], x[0][1])):
            if a == baseline and (scenario is None or s == scenario) and (s, k, treatment) in idx:
                out.append((r, idx[(s, k, treatment)]))
        return out

    def compare(self, baseline: Optional[str] = None, treatment: Optional[str] = None, **kw):
        from kami.evaluation.stats import compare

        baseline = baseline or self.arms[0]
        treatment = treatment or self.arms[1]
        return compare(self, baseline, treatment, **kw)

    def to_rows(self) -> List[Dict[str, Any]]:
        return [{"scenario": r.scenario, "seed": r.seed, "arm": r.arm, **r.metrics} for r in self.records]

    def to_csv(self, path) -> None:
        import csv

        rows = self.to_rows()
        keys = list(rows[0]) if rows else []
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
