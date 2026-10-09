"""``python -m kami replay {demo,export,validate}`` (sprint 03, S03-2, S03-3).

* ``demo``: run ``scenarios/hanoi/demo_center.json`` and write the replay the web app ships
  (``web/public/fixtures/hanoi_center_demo/``); same seed → same bytes.
* ``export --spec FILE --out DIR``: run a RunSpec and write its replay; ``export RUN_FOLDER --out DIR``: replay of a
  folder written by ``run --spec --out`` with ``outputs.trajectories = "parquet"`` (needs ``pyarrow``).
* ``validate DIR``: check a replay folder (exit 1 on problems).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from kami.replay.export import ReplayInput, SimplifyParams, export, spec_sha256
from kami.replay.schema import validate

REPO = Path(__file__).resolve().parents[2]
DEMO_SPEC = REPO / "scenarios" / "hanoi" / "demo_center.json"
DEMO_OUT = REPO / "web" / "public" / "fixtures" / "hanoi_center_demo"


def add_arguments(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="replay_cmd", required=True)
    d = sub.add_parser("demo", help="run the demo scenario and write the web fixture")
    d.add_argument("--spec", default=str(DEMO_SPEC))
    d.add_argument("--out", default=str(DEMO_OUT))
    _simplify_args(d)
    e = sub.add_parser("export", help="replay of a RunSpec (--spec) or of a run folder")
    e.add_argument("run_folder", nargs="?", default=None, help="folder written by `run --spec --out`")
    e.add_argument("--spec", default=None, help="RunSpec JSON file to run")
    e.add_argument("--out", required=True)
    _simplify_args(e)
    v = sub.add_parser("validate", help="check a replay folder")
    v.add_argument("folder")


def _simplify_args(p) -> None:
    p.add_argument("--dist-m", type=float, default=1.0, help="simplification: max distance to the road (m)")
    p.add_argument("--dt-s", type=float, default=0.5, help="simplification: max timing error (s)")
    p.add_argument("--no-gzip", action="store_true", help="write plain .json files")


# ---------------------------------------------------------------------------- shared helpers
def run_meta(spec) -> Dict[str, Any]:
    """Run block of the manifest for a resolved RunSpec."""
    sc = spec.scenario
    return {"name": spec.name, "scenario": sc.name, "seed": spec.seed if spec.seed is not None else sc.seed,
            "crn_seed": spec.crn_seed, "policy": spec.policy_group.name,
            "network": getattr(sc.network, "name", None) or sc.network.kind, "spec_sha256": spec_sha256(spec)}


def area_of_spec(spec) -> Optional[Dict[str, Any]]:
    area = getattr(spec.scenario.source, "area", None)
    if not area:
        return None
    return {"name": area.get("name") or spec.scenario.name, "bbox": list(area["bbox"])}


def export_run(spec, sim, out_dir, params: SimplifyParams = SimplifyParams(), compress: bool = True) -> Path:
    """Replay of a finished run of ``spec`` (used by ``run --spec --out`` and the run store)."""
    return export(sim, out_dir, area=area_of_spec(spec), simplify_params=params, compress=compress,
                  run=run_meta(spec))


def _run(spec):
    from kami.config import build_run

    built = build_run(spec)
    built.config.record_trajectories = True
    built.config.record_events = True
    return built.simulation().run()


def from_run_folder(folder: Path) -> tuple:
    """(spec, ReplayInput) of a folder written by ``run --spec --out``."""
    from kami.config import build_scenario, load_run_spec
    from kami.eventlog import load as load_events
    from kami.trajectory import load as load_traj

    spec = load_run_spec(folder / "run_spec.resolved.json")
    traj = folder / "trajectories.parquet"
    if not traj.exists():
        raise FileNotFoundError(f"{traj} missing: run with outputs.trajectories = \"parquet\"")
    ev = next((folder / n for n in ("events.parquet", "events.csv.gz") if (folder / n).exists()), None)
    if ev is None:
        raise FileNotFoundError(f"{folder}: no event log (events.parquet / events.csv.gz)")
    legs, meta = load_traj(traj)
    events = load_events(ev)
    ts_path = folder / "timeseries.json"
    rows = json.loads(ts_path.read_text()) if ts_path.exists() else []
    rows = [{k: (float("nan") if v is None else v) for k, v in r.items()} for r in rows]
    sc = build_scenario(spec.scenario, seed=spec.seed, fleets=spec.fleets, vehicle_types=spec.vehicle_types)
    from kami.replay.export import _positions

    coords = meta.get("coords", "lonlat")
    nodes = sorted({d.loc for d in sc.drivers} | {r.origin for r in sc.requests} | {r.dest for r in sc.requests})
    pos = dict(zip(nodes, _positions(sc.network, nodes, coords)))
    vehicles = [{"id": d.id, "fleet": d.attrs.get("fleet_id"), "vehicle_type": d.attrs.get("vehicle_type"),
                 "group": d.attrs.get("vehicle_group"), "seats": d.capacity, "home": pos[d.loc]}
                for d in sorted(sc.drivers, key=lambda d: d.id)]
    riders = {r.id: pos[r.origin] + pos[r.dest] for r in sc.requests}
    interval = rows[1]["t"] - rows[0]["t"] if len(rows) > 1 else None
    # the last time-series row is written at the end of the run (sim.t)
    t_end = rows[-1]["t"] if rows else max([sc.t_end] + [r[0] for r in events[-1:]])
    shared_path = folder / "shared.json"
    shared = json.loads(shared_path.read_text(encoding="utf-8")) if shared_path.exists() else None
    return spec, ReplayInput(legs, coords, list(events), rows, interval, vehicles, riders, sc.t_start, t_end,
                             run_meta(spec), shared)


# ---------------------------------------------------------------------------- commands
def run_cli(args) -> int:
    if args.replay_cmd == "validate":
        errs = validate(args.folder)
        for e in errs:
            print(f"  {e}")
        print(f"{args.folder}: {'OK' if not errs else f'{len(errs)} lỗi'}")
        return 1 if errs else 0

    from kami.config import SpecError, load_run_spec

    params = SimplifyParams(args.dist_m, args.dt_s)
    compress = not args.no_gzip
    t0 = time.perf_counter()
    try:
        if args.replay_cmd == "export" and args.run_folder:
            spec, inp = from_run_folder(Path(args.run_folder))
            out = export(inp, args.out, area=area_of_spec(spec), simplify_params=params, compress=compress)
        else:
            spec_file = args.spec
            if args.replay_cmd == "export" and not spec_file:
                print("error: give a run folder or --spec FILE", file=sys.stderr)
                return 2
            spec = load_run_spec(spec_file)
            sim = _run(spec)
            print(f"simulated {len(sim.scenario.requests)} requests, {len(sim.scenario.drivers)} vehicles, "
                  f"{sim.events_processed} events in {sim.wall_time:.1f}s")
            out = export_run(spec, sim, args.out, params, compress)
    except (SpecError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    errs = validate(out)
    man = json.loads((Path(out) / "manifest.json").read_text())
    size = sum(f["bytes"] for f in man["files"].values())
    print(f"wrote {out}/ ({size / 1e6:.2f} MB, {man['counts']['vehicles']} vehicles, "
          f"{man['counts']['segments']} segments, {man['counts']['points']} points, "
          f"{man['counts']['events']} events) in {time.perf_counter() - t0:.1f}s")
    for name, f in sorted(man["files"].items()):
        print(f"  {f['path']:22s} {f['bytes'] / 1e6:7.2f} MB (raw {f['raw_bytes'] / 1e6:.2f} MB)")
    if errs:
        print("validation failed:\n  " + "\n  ".join(errs), file=sys.stderr)
        return 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kami replay", description="replay files for the web visualizer")
    add_arguments(ap)
    return run_cli(ap.parse_args(argv))
