"""Pre-registered decision rules (design doc §10.4, §10.5).

Write the rule **before** running the experiment, then evaluate it on the
``Comparison``. Example — the pooling rule of §10.5::

    rule = DecisionRule("pool_after_wait → small A/B", [
        Condition("rider.cancel_rate", "delta_le", -0.01, significant=True,
                  label="cancel rate −≥1pp, CI excludes 0"),
        Condition("rider.pooled_travel_time_p90", "cross_delta_le", 8.0,
                  baseline_metric="rider.travel_time_p90", label="pooled p90 travel time +≤8 min"),
        Condition("platform.contribution_margin", "delta_ge", 0.0, label="margin not lower"),
        Condition("wait_p90", "zone_rel_le", 0.10, label="no zone p90 wait +>10%"),
    ])
    verdict = rule.evaluate(comparison)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from kami.evaluation.stats import Comparison


@dataclass
class Condition:
    """One check on a comparison.

    kinds:
      * ``delta_le`` / ``delta_ge``   – mean Δ (treatment − baseline) vs threshold
      * ``rel_le`` / ``rel_ge``       – relative Δ (Δ / baseline) vs threshold
      * ``ci_high_le`` / ``ci_low_ge``– the whole CI must be below/above the threshold (conservative)
      * ``cross_delta_le``            – treatment ``metric`` minus baseline ``baseline_metric`` ≤ threshold
      * ``zone_rel_le``               – every zone's relative change of ``metric`` (e.g. ``wait_p90``) ≤ threshold
    ``significant=True`` additionally requires the 95% CI to exclude 0.
    """

    metric: str
    kind: str
    threshold: float
    significant: bool = False
    baseline_metric: Optional[str] = None
    label: str = ""

    def check(self, cmp: Comparison):
        if self.kind == "zone_rel_le":
            rels = {z: v[f"{self.metric}_rel"] for z, v in cmp.zone_effects.items()
                    if not math.isnan(v.get(f"{self.metric}_rel", math.nan))}
            if not rels:
                return None, "no zone data", False
            worst = max(rels, key=rels.get)
            return rels[worst], f"worst zone {worst}: {rels[worst]:+.1%}", rels[worst] <= self.threshold
        if self.kind == "cross_delta_le":
            t = cmp.arm_means.get("treatment", {}).get(self.metric)
            b = cmp.arm_means.get("baseline", {}).get(self.baseline_metric or self.metric)
            if t is None or b is None:
                return None, "metric undefined in an arm (e.g. no pooled trips)", False
            value = t - b
            return value, f"treatment {t:.3f} − baseline {b:.3f} = {value:+.3f}", value <= self.threshold
        e = cmp.effects.get(self.metric)
        if e is None:
            return None, "metric missing", False
        value = {"delta_le": e.delta, "delta_ge": e.delta, "rel_le": e.rel, "rel_ge": e.rel,
                 "ci_high_le": e.ci_high, "ci_low_ge": e.ci_low}[self.kind]
        ok = value <= self.threshold if self.kind.endswith("_le") else value >= self.threshold
        if self.significant:
            ok = ok and e.significant
        detail = f"Δ={e.delta:+.4g} CI[{e.ci_low:+.4g}, {e.ci_high:+.4g}]"
        return value, detail, bool(ok)


@dataclass
class Verdict:
    rule: str
    results: List[dict]
    passed: bool

    def __str__(self):
        lines = [f"Decision rule: {self.rule} -> {'PASS' if self.passed else 'FAIL'}"]
        for r in self.results:
            lines.append(f"  [{'x' if r['passed'] else ' '}] {r['label']}: {r['detail']}")
        return "\n".join(lines)


@dataclass
class DecisionRule:
    name: str
    conditions: Sequence[Condition]

    def evaluate(self, cmp: Comparison) -> Verdict:
        results = []
        for c in self.conditions:
            value, detail, ok = c.check(cmp)
            results.append({"label": c.label or f"{c.metric} {c.kind} {c.threshold}", "value": value,
                            "detail": detail, "passed": ok})
        return Verdict(self.name, results, all(r["passed"] for r in results))


def pooling_rule_example() -> DecisionRule:
    """The sample rule of design doc §10.5 (thresholds are placeholders for the business to set)."""
    return DecisionRule("pool_after_wait -> propose small A/B", [
        Condition("rider.cancel_rate", "delta_le", -0.01, significant=True,
                  label="cancel rate drops ≥ 1 pp (CI excludes 0)"),
        Condition("rider.pooled_travel_time_p90", "cross_delta_le", 8.0, baseline_metric="rider.travel_time_p90",
                  label="pooled riders' p90 request→arrival time +≤ 8 min"),
        Condition("platform.contribution_margin", "delta_ge", 0.0, label="contribution margin not lower"),
        Condition("wait_p90", "zone_rel_le", 0.10, label="no zone with p90 wait +> 10%"),
    ])
