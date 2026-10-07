"""Robustness checks (design doc §10.4 criteria 3–4, §11, §13 phase 4).

* ``behavior_sensitivity`` — rerun the same experiment under alternative
  behaviour assumptions (e.g. pool acceptance ×0.5 / ×1.5) and check the
  sign of the effect does not flip.
* ``policy_grid`` — grid-search policy parameters (wait threshold 3/5/7 min,
  surcharge 0–30k) against the same baseline runs.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import replace
from typing import Callable, Dict, Iterable, List, Mapping, Sequence

from kami.behavior.registry import BehaviorSuite
from kami.evaluation.experiment import Experiment
from kami.evaluation.stats import Comparison
from kami.policy.base import Policy


def behavior_sensitivity(exp: Experiment, variants: Mapping[str, Callable[[], BehaviorSuite]],
                         baseline: str, treatment: str, n_jobs: int = 1) -> Dict[str, Comparison]:
    """Same scenarios/seeds/arms, different behaviour suites."""
    out = {}
    for name, fn in variants.items():
        res = replace(exp, behavior_fn=fn).run(n_jobs=n_jobs)
        out[name] = res.compare(baseline, treatment)
    return out


def sign_stable(comparisons: Mapping[str, Comparison], metric: str) -> Dict[str, object]:
    """Does the direction of ``metric``'s effect hold across all variants?"""
    deltas = {k: c[metric].delta for k, c in comparisons.items() if metric in c.effects}
    signs = {k: (0 if (c[metric].significant is False) else (1 if c[metric].delta > 0 else -1))
             for k, c in comparisons.items() if metric in c.effects}
    nonzero = {s for s in signs.values() if s != 0}
    return {"metric": metric, "deltas": deltas, "signs": signs, "stable": len(nonzero) <= 1}


def policy_grid(exp: Experiment, make_policy: Callable[..., Policy], grid: Mapping[str, Sequence],
                baseline_arm: str = "baseline", n_jobs: int = 1) -> List[Dict[str, object]]:
    """Run baseline + one arm per parameter combination; return one row per combination."""
    keys = list(grid)
    combos = list(itertools.product(*(grid[k] for k in keys)))
    arms = {baseline_arm: exp.arms[baseline_arm]}
    labels = []
    for combo in combos:
        params = dict(zip(keys, combo))
        label = ",".join(f"{k}={v}" for k, v in params.items())
        arms[label] = (lambda p=params: make_policy(**p))
        labels.append((label, params))
    res = replace(exp, arms=arms).run(n_jobs=n_jobs)
    rows = []
    for label, params in labels:
        cmp = res.compare(baseline_arm, label)
        rows.append({"params": params, "comparison": cmp})
    return rows
