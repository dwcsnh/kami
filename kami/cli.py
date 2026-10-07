"""Command line: ``python -m kami {presets,run,compare}``."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

from kami.behavior import BehaviorSuite, ModelRegistry
from kami.core.engine import SimConfig, Simulation
from kami.evaluation import Experiment, pooling_rule_example, report
from kami.network import FileZoneSystem, GridNetwork, RoadNetwork, SquareZoneSystem
from kami.policy import POLICIES
from kami.scenario import PRESETS, ScenarioBuilder


def _parse_kv(items: List[str]) -> Dict:
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        for cast in (int, float):
            try:
                v = cast(v)
                break
            except ValueError:
                continue
        if v in ("true", "True"):
            v = True
        elif v in ("false", "False"):
            v = False
        out[k] = v
    return out


def _world(args):
    if args.network.startswith(("road", "fleetpy")):   # "fleetpy:" is the kami 0.1 spelling
        name = args.network.partition(":")[2] or "example_network"
        net = RoadNetwork(name)
        zones = FileZoneSystem(net, args.zones) if args.zones else SquareZoneSystem(net, args.zone_m)
    else:
        net = GridNetwork(args.grid_km * 1000, args.grid_km * 1000)
        zones = SquareZoneSystem(net, args.zone_m)
    return net, zones


def _common(p):
    p.add_argument("--network", default="grid", help="grid | road[:<network name or folder>] (alias fleetpy:)")
    p.add_argument("--zones", default=None, help="zone system name under data/zones (default: square zones)")
    p.add_argument("--zone-m", type=float, default=1000.0)
    p.add_argument("--grid-km", type=float, default=8.0)
    p.add_argument("--demand", type=float, default=200.0, help="requests/hour at demand-profile 1.0")
    p.add_argument("--drivers", type=int, default=150)
    p.add_argument("--registry", default=None, help="model registry folder (latest checkpoint of every slot)")
    p.add_argument("--employed-drivers", action="store_true", help="drivers cannot reject trips")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kami", description="kami ride-hailing policy simulator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("presets", help="list scenario presets and policies")

    r = sub.add_parser("run", help="run one simulation")
    _common(r)
    r.add_argument("--preset", default="weekday_am_peak")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--policy", default="baseline", choices=sorted(POLICIES))
    r.add_argument("--arg", action="append", default=[], help="policy argument k=v (repeatable)")
    r.add_argument("--out", default=None, help="folder for metrics.json and events.csv")

    c = sub.add_parser("compare", help="paired baseline vs treatment experiment (CRN)")
    _common(c)
    c.add_argument("--presets", default="weekday_am_peak,undersupply,rain,accident")
    c.add_argument("--seeds", type=int, default=10)
    c.add_argument("--baseline", default="baseline", choices=sorted(POLICIES))
    c.add_argument("--treatment", default="pool_after_wait", choices=sorted(POLICIES))
    c.add_argument("--arg", action="append", default=[], help="treatment argument k=v (repeatable)")
    c.add_argument("--jobs", type=int, default=1)
    c.add_argument("--no-crn", action="store_true")
    c.add_argument("--report", default=None, help="write a Markdown report here")
    c.add_argument("--pooling-rule", action="store_true", help="evaluate the sample decision rule (doc §10.5)")
    args = ap.parse_args(argv)

    if args.cmd == "presets":
        print("Scenario presets:")
        for k, v in PRESETS.items():
            print(f"  {k:18s} {v}")
        print("Policies:", ", ".join(sorted(POLICIES)))
        return 0

    net, zones = _world(args)
    builder = ScenarioBuilder(net, zones)
    behavior = (lambda: BehaviorSuite.employed_drivers()) if args.employed_drivers else BehaviorSuite
    if args.registry:
        reg = ModelRegistry(args.registry)
        slots = {p.name: "latest" for p in Path(args.registry).iterdir() if p.is_dir()}
        behavior = lambda: reg.suite(slots)

    if args.cmd == "run":
        sc = builder.preset(args.preset, seed=args.seed, demand_per_hour=args.demand, n_drivers=args.drivers)
        pol = POLICIES[args.policy](**_parse_kv(args.arg))
        sim = Simulation(sc, pol, behavior()).run()
        m = sim.metrics()
        print(json.dumps({"scenario": sc.summary(), "policy": pol.describe(), "wall_s": round(sim.wall_time, 2),
                          "events": sim.events_processed}, default=str, indent=2))
        for k, v in m.items():
            print(f"  {k:34s} {v:,.4f}" if isinstance(v, float) else f"  {k:34s} {v}")
        if args.out:
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            (out / "metrics.json").write_text(json.dumps(m, indent=2))
            sim.log.to_csv(out / "events.csv")
            print(f"wrote {out}/metrics.json and events.csv")
        return 0

    if args.cmd == "compare":
        kw = _parse_kv(args.arg)
        arms = {"baseline": POLICIES[args.baseline], "treatment": lambda: POLICIES[args.treatment](**kw)}
        names = [p.strip() for p in args.presets.split(",") if p.strip()]
        demand, drivers = args.demand, args.drivers
        exp = Experiment(lambda n, s: builder.preset(n, seed=s, demand_per_hour=demand, n_drivers=drivers),
                         names, list(range(args.seeds)), arms, behavior, SimConfig(), crn=not args.no_crn)
        res = exp.run(n_jobs=args.jobs, progress=True)
        cmp = res.compare("baseline", "treatment")
        b, t = args.baseline, args.treatment
        print(cmp.table(report.DEFAULT_METRICS))
        verdict = pooling_rule_example().evaluate(cmp) if args.pooling_rule else None
        if verdict:
            print(verdict)
        if args.report:
            report.write(args.report, cmp, title=f"{t} vs {b}", verdict=verdict)
            print(f"report: {args.report}")
        print(f"{len(res.records)} runs in {res.wall_s:.1f}s")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
