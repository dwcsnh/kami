"""Design doc end-to-end example: "after 5 minutes of waiting, offer pooling for +20,000 VND".

1. pre-register the decision rule (doc §10.5)
2. paired CRN experiment over a scenario library × N seeds (doc §10.1)
3. sensitivity of the conclusion to the pool-acceptance assumption ±50% (doc §10.4, §11)
4. Markdown report

    python examples/02_pool_after_wait.py [n_seeds] [n_jobs]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kami import (Baseline, BehaviorSuite, GridNetwork, PoolAfterWait, ScenarioBuilder,  # noqa: E402
                  SquareZoneSystem)
from kami.behavior import LogitPoolAccept, ProbabilityScaler  # noqa: E402
from kami.evaluation import (Experiment, behavior_sensitivity, pooling_rule_example, report,  # noqa: E402
                             sign_stable)

N_SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 30
N_JOBS = int(sys.argv[2]) if len(sys.argv) > 2 else -1     # -1 = all CPUs

net = GridNetwork(8000, 8000, 250)
zones = SquareZoneSystem(net, 1000)
builder = ScenarioBuilder(net, zones)


def scenario(name, seed):
    return builder.preset(name, seed=seed, demand_per_hour=200, n_drivers=120)


arms = {
    "baseline": Baseline,
    "pool_5min_+20k": lambda: PoolAfterWait(wait_threshold=300, surcharge=20_000, include_matched=True),
}
exp = Experiment(scenario, ["weekday_am_peak", "undersupply", "rain", "accident"], range(N_SEEDS), arms)

# 1. decision rule written BEFORE looking at results
rule = pooling_rule_example()

# 2. paired experiment
res = exp.run(n_jobs=N_JOBS)
cmp = res.compare("baseline", "pool_5min_+20k")
print(cmp.table(report.DEFAULT_METRICS))
verdict = rule.evaluate(cmp)
print("\n" + str(verdict))

# 3. sensitivity: what if riders accept pooling 50% less / more often than assumed?
variants = {
    "accept x0.5": lambda: BehaviorSuite(pool_accept=ProbabilityScaler(LogitPoolAccept(), 0.5)),
    "accept x1.0": BehaviorSuite,
    "accept x1.5": lambda: BehaviorSuite(pool_accept=ProbabilityScaler(LogitPoolAccept(), 1.5)),
}
sens = behavior_sensitivity(exp, variants, "baseline", "pool_5min_+20k", n_jobs=N_JOBS)
print("\nSensitivity of the effect to the pool-acceptance assumption:")
for metric in ["rider.cancel_rate", "rider.completion_rate", "rider.pool_rate", "platform.contribution_margin"]:
    s = sign_stable(sens, metric)
    print(f"  {metric:30s} stable={s['stable']}  " +
          "  ".join(f"{k}: Δ={v:+.4g}" for k, v in s["deltas"].items()))

# 4. report
notes = "Sensitivity (pool acceptance ×0.5/×1.0/×1.5): " + "; ".join(
    f"{k}: Δcancel={c['rider.cancel_rate'].delta:+.4f}, Δpool_rate={c['rider.pool_rate'].delta:+.4f}"
    for k, c in sens.items())
path = report.write(Path(__file__).resolve().parent / "output" / "pool_after_wait_report.md", cmp,
                    title="Pool after 5 min (+20,000 VND) vs baseline", verdict=verdict, notes=notes)
print(f"\nreport: {path}  ({len(res.records)} runs, {res.wall_s:.1f}s)")
