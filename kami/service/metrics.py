"""Read-only comparison of persisted metrics; no new simulation or significance test."""
from __future__ import annotations

import math
from kami.metrics import DIRECTION
from kami.service.stream import clean
from kami.store.service import Conflict


def visible(name):
    return not (name.startswith(("rider.pool_", "rider.pooled_")) or
                name in {"rider.detour_ratio", "platform.pooled_jobs", "platform.surcharge_total"})


def summary(repo, run_id):
    require_results(repo, run_id)
    return clean({k: v for k, v in repo.run_metrics(run_id).items() if visible(k)})


def require_results(repo, run_id):
    if repo.get_run(run_id)["status"] != "succeeded":
        raise Conflict("kết quả hoàn chỉnh chỉ có ở run succeeded")


def compare(repo, ids):
    runs = [repo.get_run(i) for i in ids]
    metrics = [summary(repo, i) for i in ids]
    baseline = runs[0]
    comparisons = []
    for candidate, values in zip(runs[1:], metrics[1:]):
        warnings = []
        a, b = baseline["run_spec"], candidate["run_spec"]
        if a["scenario"] != b["scenario"]:
            warnings.append("different_scenario")
        crn_a = baseline["seed"] if a.get("crn_seed") is None else a["crn_seed"]
        crn_b = candidate["seed"] if b.get("crn_seed") is None else b["crn_seed"]
        if (baseline["seed"], crn_a) != (candidate["seed"], crn_b):
            warnings.append("unpaired_seed")
        if a.get("fleets") != b.get("fleets") or a.get("vehicle_types") != b.get("vehicle_types"):
            warnings.append("different_fleet")
        if baseline["kami_version"] != candidate["kami_version"] or baseline["provenance"].get("environment") != candidate["provenance"].get("environment"):
            warnings.append("different_environment")
        rows = []
        for name in sorted(set(metrics[0]) | set(values)):
            before, after = metrics[0].get(name), values.get(name)
            delta = after - before if before is not None and after is not None else None
            if delta is not None and not math.isfinite(delta):
                delta = None
            direction = DIRECTION.get(name, 0)
            verdict = None
            if delta is not None and direction:
                verdict = "equal" if delta == 0 else ("better" if delta * direction > 0 else "worse")
            rows.append({"metric": name, "baseline": before, "candidate": after, "delta": delta,
                         "delta_percent": delta / abs(before) * 100 if delta is not None and before else None,
                         "direction": direction, "verdict": verdict})
        comparisons.append({"run_id": candidate["id"], "warnings": warnings, "metrics": rows})
    return clean({"baseline_id": baseline["id"], "comparisons": comparisons})
