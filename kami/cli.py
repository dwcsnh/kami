"""Command line: ``python -m kami {presets,run,compare,spec,db,bench}``.

``kami.store`` (SQLite) is imported only by ``run --db`` and ``db`` so the plain commands stay DB-free (NFR-5).
"""
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


def _run_args(p):
    _common(p)
    p.add_argument("--preset", default="weekday_am_peak")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--policy", default="baseline", choices=sorted(POLICIES))
    p.add_argument("--arg", action="append", default=[], help="policy argument k=v (repeatable)")


LEGACY_RUN_FLAGS = ("network", "zones", "zone_m", "grid_km", "demand", "drivers", "registry", "employed_drivers",
                    "preset", "seed", "policy", "arg")


def _print_run(sc, policy, sim, m) -> None:
    print(json.dumps({"scenario": sc.summary(), "policy": policy.describe(), "wall_s": round(sim.wall_time, 2),
                      "events": sim.events_processed}, default=str, indent=2))
    for k, v in m.items():
        print(f"  {k:34s} {v:,.4f}" if isinstance(v, float) else f"  {k:34s} {v}")


def _run_spec_cmd(args, parser) -> int:
    from kami.config import SpecError, build_run, load_run_spec

    changed = [f"--{k.replace('_', '-')}" for k in LEGACY_RUN_FLAGS if getattr(args, k) != parser.get_default(k)]
    if changed:
        print(f"error: --spec cannot be combined with {', '.join(changed)} (put them in the spec file)",
              file=sys.stderr)
        return 2
    try:
        spec = load_run_spec(args.spec)
    except SpecError as e:
        print(f"error: {args.spec}: {e}", file=sys.stderr)
        return 2
    run_id = None
    try:
        if args.db:
            from kami.store import Repository, execute

            repo = Repository.open(args.db)
            res = execute(spec, repo, args.artifacts)
            run_id = res.run_id
            if res.status != "succeeded":
                print(f"run {run_id} failed:\n{res.error}", file=sys.stderr)
                return 1
            sim, resolved = res.sim, repo.run_spec(run_id)
        else:
            resolved = spec
            sim = build_run(spec).simulation().run()
    except SpecError as e:
        print(f"error: {args.spec}: {e}", file=sys.stderr)
        return 2
    m = sim.metrics()
    _print_run(sim.scenario, sim.policy, sim, m)
    if run_id is not None:
        print(f"run_id {run_id} stored in {args.db}")
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "metrics.json").write_text(json.dumps(m, indent=2))
        (out / "run_spec.resolved.json").write_text(resolved.to_json())
        written = ["metrics.json", "run_spec.resolved.json"]
        if sim.timeseries is not None:
            sim.timeseries.to_json(out / "timeseries.json")
            written.append("timeseries.json")
        fmt = resolved.outputs.event_log
        if fmt != "none":
            name = "events.parquet" if fmt == "parquet" else "events.csv.gz"
            sim.log.save(out / name, fmt)
            written.append(name)
        print(f"wrote {out}/: {', '.join(written)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kami", description="kami ride-hailing policy simulator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("presets", help="list scenario presets and policies")

    r = sub.add_parser("run", help="run one simulation (flags as in kami 0.1, or --spec FILE)")
    _run_args(r)
    r.add_argument("--out", default=None, help="folder for metrics.json and events.csv")
    r.add_argument("--spec", default=None, help="RunSpec JSON file (replaces the scenario/policy flags)")
    r.add_argument("--db", default=None, help="with --spec: store the run in this SQLite database")
    r.add_argument("--artifacts", default="runs", help="with --db: folder for event log files (<dir>/<run_id>/)")

    s = sub.add_parser("spec", help="print the RunSpec JSON equivalent to `run` flags")
    _run_args(s)
    s.add_argument("--out", default=None, help="write to this file instead of stdout")

    d = sub.add_parser("db", help="database maintenance")
    dsub = d.add_subparsers(dest="db_cmd", required=True)
    di = dsub.add_parser("init", help="create the database or apply pending migrations")
    di.add_argument("--db", default="kami.db")

    b = sub.add_parser("bench", help="benchmark suite (wall-clock, events/s, peak RAM) -> JSON")
    from kami.bench import add_arguments as _bench_args

    _bench_args(b)

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

    if args.cmd == "run" and args.spec:
        return _run_spec_cmd(args, r)
    if args.cmd == "run" and (args.db or args.artifacts != "runs"):
        print("error: --db/--artifacts need --spec", file=sys.stderr)
        return 2
    if args.cmd == "spec":
        from kami.config import SpecError, spec_from_cli

        try:
            spec = spec_from_cli(args.preset, args.policy, _parse_kv(args.arg), seed=args.seed, demand=args.demand,
                                 drivers=args.drivers, network=args.network, zones=args.zones, zone_m=args.zone_m,
                                 grid_km=args.grid_km, registry=args.registry, employed_drivers=args.employed_drivers)
        except SpecError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(spec.to_json() + "\n")
            print(f"wrote {args.out}")
        else:
            print(spec.to_json())
        return 0
    if args.cmd == "db":
        from kami.store import connect, current_version, migrate

        conn = connect(args.db)
        applied = migrate(conn)
        print(f"{args.db}: schema version {current_version(conn)}"
              + (f" (applied {', '.join(map(str, applied))})" if applied else " (up to date)"))
        return 0
    if args.cmd == "bench":
        from kami.bench import run_cli

        return run_cli(args)

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
        _print_run(sc, pol, sim, m)
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
