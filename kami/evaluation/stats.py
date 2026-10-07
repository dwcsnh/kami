"""Paired effect estimation: mean Δ, t-interval and stratified bootstrap CI (design doc §10.1)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, Hashable, List, Optional, Sequence

from kami.metrics import DIRECTION


def t_quantile(p: float, df: int) -> float:
    """Student-t quantile (scipy if available, else Cornish–Fisher expansion; error < 1e-3 for df ≥ 3)."""
    try:
        from scipy.stats import t

        return float(t.ppf(p, df))
    except ImportError:
        from statistics import NormalDist

        z = NormalDist().inv_cdf(p)
        return (z + (z ** 3 + z) / (4 * df) + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * df ** 2)
                + (3 * z ** 7 + 19 * z ** 5 + 17 * z ** 3 - 15 * z) / (384 * df ** 3))


@dataclass
class Effect:
    metric: str
    n: int
    baseline: float
    treatment: float
    delta: float
    ci_low: float
    ci_high: float
    t_low: float
    t_high: float
    sd_delta: float
    by_scenario: Dict[str, float] = field(default_factory=dict)

    @property
    def rel(self) -> float:
        return self.delta / self.baseline if self.baseline not in (0, 0.0) and not math.isnan(self.baseline) else math.nan

    @property
    def significant(self) -> bool:
        return not (self.ci_low <= 0.0 <= self.ci_high)

    @property
    def half_width(self) -> float:
        return (self.ci_high - self.ci_low) / 2

    @property
    def verdict(self) -> str:
        if not self.significant:
            return "≈"
        d = DIRECTION.get(self.metric, 0)
        if d == 0:
            return "↑" if self.delta > 0 else "↓"
        return "better" if d * self.delta > 0 else "worse"


@dataclass
class Comparison:
    baseline: str
    treatment: str
    effects: Dict[str, Effect]
    scenarios: List[str]
    n_pairs: int
    crn: bool
    zone_effects: Dict[Hashable, Dict[str, float]] = field(default_factory=dict)
    #: per-arm means over runs where the metric is defined, e.g. arm_means["treatment"]["rider.pooled_travel_time_p90"]
    arm_means: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def __getitem__(self, metric: str) -> Effect:
        return self.effects[metric]

    def table(self, metrics: Optional[Sequence[str]] = None) -> str:
        names = metrics or list(self.effects)
        lines = [f"{'metric':34s} {'baseline':>12s} {'treatment':>12s} {'Δ':>11s} {'95% CI':>25s} {'rel':>8s}  verdict"]
        for name in names:
            e = self.effects.get(name)
            if e is None:
                continue
            lines.append(f"{name:34s} {_fmt(e.baseline):>12s} {_fmt(e.treatment):>12s} {_fmt(e.delta):>11s} "
                         f"[{_fmt(e.ci_low):>10s}, {_fmt(e.ci_high):>10s}] {_pct(e.rel):>8s}  {e.verdict}")
        return "\n".join(lines)


def _fmt(x: float) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "nan"
    if abs(x) >= 1e5:
        return f"{x:,.0f}"
    if abs(x) >= 100:
        return f"{x:.1f}"
    return f"{x:.4f}"


def _pct(x: float) -> str:
    return "nan" if x is None or math.isnan(x) else f"{100 * x:+.1f}%"


def _finite(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def compare(result, baseline: str, treatment: str, metrics: Optional[Sequence[str]] = None,
            n_boot: int = 2000, alpha: float = 0.05, seed: int = 12345, scenario: Optional[str] = None) -> Comparison:
    """Paired comparison; ``scenario`` restricts it to one scenario (robustness across scenarios)."""
    pairs = result.pairs(baseline, treatment, scenario)
    if not pairs:
        raise ValueError(f"no paired runs for {baseline} vs {treatment}")
    names = metrics or [k for k in pairs[0][0].metrics]
    scenarios = sorted({b.scenario for b, _ in pairs})
    rng = random.Random(seed)
    effects = {}
    for name in names:
        rows = [(b.scenario, b.metrics.get(name), t.metrics.get(name)) for b, t in pairs]
        rows = [(s, x, y) for s, x, y in rows if _finite(x) and _finite(y)]
        if not rows:
            continue
        deltas = [y - x for _, x, y in rows]
        n = len(deltas)
        md = sum(deltas) / n
        sd = math.sqrt(sum((d - md) ** 2 for d in deltas) / (n - 1)) if n > 1 else 0.0
        tq = t_quantile(1 - alpha / 2, max(n - 1, 1)) if n > 1 else math.inf
        # stratified bootstrap: resample replications within each scenario
        strata: Dict[str, List[float]] = {}
        for s, x, y in rows:
            strata.setdefault(s, []).append(y - x)
        boots = []
        for _ in range(n_boot):
            tot, cnt = 0.0, 0
            for ds in strata.values():
                tot += sum(rng.choices(ds, k=len(ds)))
                cnt += len(ds)
            boots.append(tot / cnt)
        boots.sort()
        lo = boots[int(alpha / 2 * n_boot)]
        hi = boots[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
        effects[name] = Effect(
            name, n, sum(x for _, x, _ in rows) / n, sum(y for _, _, y in rows) / n, md, lo, hi,
            md - tq * sd / math.sqrt(n) if n > 1 else math.nan, md + tq * sd / math.sqrt(n) if n > 1 else math.nan,
            sd, {s: sum(ds) / len(ds) for s, ds in strata.items()})
    arm_means = {}
    for arm, idx in (("baseline", 0), ("treatment", 1)):
        sums: Dict[str, List[float]] = {}
        for pair in pairs:
            for k, v in pair[idx].metrics.items():
                if _finite(v):
                    sums.setdefault(k, []).append(v)
        arm_means[arm] = {k: sum(v) / len(v) for k, v in sums.items()}
    return Comparison(baseline, treatment, effects, scenarios, len(pairs), result.crn,
                      zone_effects=_zone_effects(pairs), arm_means=arm_means)


def _zone_effects(pairs) -> Dict[Hashable, Dict[str, float]]:
    """Mean per-zone baseline/treatment wait p90 and its relative change (guardrail input)."""
    acc: Dict[Hashable, Dict[str, List[float]]] = {}
    for b, t in pairs:
        for z, bz in b.zones.items():
            tz = t.zones.get(z)
            if not tz or bz["booked"] < 10:
                continue
            if _finite(bz["wait_p90"]) and _finite(tz["wait_p90"]):
                a = acc.setdefault(z, {"b": [], "t": []})
                a["b"].append(bz["wait_p90"])
                a["t"].append(tz["wait_p90"])
    out = {}
    for z, a in acc.items():
        mb, mt = sum(a["b"]) / len(a["b"]), sum(a["t"]) / len(a["t"])
        out[z] = {"wait_p90_baseline": mb, "wait_p90_treatment": mt,
                  "wait_p90_rel": (mt - mb) / mb if mb else math.nan, "n": len(a["b"])}
    return out
