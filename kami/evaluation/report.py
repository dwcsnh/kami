"""Markdown report for a comparison (baseline vs treatment)."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional, Sequence

from kami.evaluation.decision import Verdict
from kami.evaluation.stats import Comparison, _fmt, _pct

DEFAULT_METRICS = [
    "rider.conversion", "rider.completion_rate", "rider.cancel_rate", "rider.no_driver_rate",
    "rider.wait_mean", "rider.wait_p90", "rider.wait_p95", "rider.eta_error_abs", "rider.travel_time_p90",
    "rider.fare_mean", "rider.pool_rate", "rider.pool_offer_accept_rate", "rider.detour_ratio",
    "rider.pooled_travel_time_p90", "rider.pooled_cancel_rate",
    "driver.utilization", "driver.earnings_per_hour", "driver.idle_gap_mean", "driver.empty_km_share",
    "driver.rejection_rate", "platform.trips", "platform.gmv", "platform.revenue",
    "platform.contribution_margin", "platform.pooled_jobs", "ops.trips_per_vehicle_hour",
    "ops.pax_km_per_vehicle_km", "ops.vehicle_km", "fair.zone_wait_p90_max", "fair.zone_completion_min",
]


def markdown(cmp: Comparison, title: str = "kami policy evaluation", verdict: Optional[Verdict] = None,
             metrics: Optional[Sequence[str]] = None, notes: str = "") -> str:
    names = [m for m in (metrics or DEFAULT_METRICS) if m in cmp.effects]
    out = [f"# {title}", "",
           f"- Baseline: `{cmp.baseline}` · Treatment: `{cmp.treatment}`",
           f"- Scenarios: {', '.join(cmp.scenarios)} · paired replications: {cmp.n_pairs} · "
           f"CRN: {'on' if cmp.crn else 'off'}",
           "- Δ = treatment − baseline; CI = stratified bootstrap 95%. Units: minutes, VND, km, rates in [0,1].",
           ""]
    if notes:
        out += [notes, ""]
    if verdict is not None:
        out += ["## Decision rule", "", f"**{verdict.rule}: {'PASS' if verdict.passed else 'FAIL'}**", ""]
        out += [f"- {'✅' if r['passed'] else '❌'} {r['label']} — {r['detail']}" for r in verdict.results]
        out.append("")
    out += ["## Effects", "", "| metric | baseline | treatment | Δ | 95% CI | rel | verdict |",
            "|---|---:|---:|---:|---:|---:|---|"]
    for n in names:
        e = cmp.effects[n]
        out.append(f"| `{n}` | {_fmt(e.baseline)} | {_fmt(e.treatment)} | {_fmt(e.delta)} | "
                   f"[{_fmt(e.ci_low)}, {_fmt(e.ci_high)}] | {_pct(e.rel)} | {e.verdict} |")
    if len(cmp.scenarios) > 1:
        out += ["", "## Δ by scenario", "", "| metric | " + " | ".join(cmp.scenarios) + " |",
                "|---|" + "---:|" * len(cmp.scenarios)]
        for n in names[:12]:
            e = cmp.effects[n]
            out.append(f"| `{n}` | " + " | ".join(_fmt(e.by_scenario.get(s, math.nan)) for s in cmp.scenarios) + " |")
    if cmp.zone_effects:
        worst = sorted(cmp.zone_effects.items(), key=lambda kv: -(kv[1]["wait_p90_rel"]
                                                                   if not math.isnan(kv[1]["wait_p90_rel"]) else -9))[:5]
        out += ["", "## Zones with the largest p90 wait increase", "", "| zone | baseline | treatment | rel |",
                "|---|---:|---:|---:|"]
        out += [f"| {z} | {_fmt(v['wait_p90_baseline'])} | {_fmt(v['wait_p90_treatment'])} | {_pct(v['wait_p90_rel'])} |"
                for z, v in worst]
    out += ["", "> Simulators tend to exaggerate magnitudes: trust direction and ranking first (design doc §2.8)."]
    return "\n".join(out) + "\n"


def write(path, *args, **kw) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown(*args, **kw))
    return path
