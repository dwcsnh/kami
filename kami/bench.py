"""Benchmark harness (sprint 01, S01-8, PERF-3).

Every case is a RunSpec JSON file (default suite: ``benchmarks/specs/``). Each repetition
runs in its own Python process so the peak RSS is that of one case::

    python -m kami bench --repeat 3 --out benchmarks/results/2026-10-07.json
    python -m kami bench --compare benchmarks/results/2026-10-07.json   # exit 1 on > 10% regression

Per case: ``wall_s`` of ``Simulation.run`` (median / min / max), ``build_s`` (network,
scenario), ``events``, ``events_per_s``, ``peak_rss_mb`` and a few metrics to detect a
change of results.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SUITE = REPO / "benchmarks" / "specs"
KEY_METRICS = ("platform.trips", "rider.completion_rate", "rider.wait_mean", "driver.utilization", "platform.gmv")
MARK = "KAMI_BENCH_RESULT "


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--suite", default=str(DEFAULT_SUITE), help="folder of RunSpec JSON files (one case per file)")
    p.add_argument("--cases", default=None, help="comma-separated case names (file stems); default: all")
    p.add_argument("--repeat", type=int, default=3, help="repetitions per case (median is reported)")
    p.add_argument("--out", default=None, help="write the results JSON here")
    p.add_argument("--compare", default=None, help="baseline results JSON; exit 1 if a case regresses")
    p.add_argument("--threshold", type=float, default=0.10, help="regression threshold (fraction, default 0.10)")


# ---------------------------------------------------------------------------- worker (child process)
def _peak_rss_mb() -> Optional[float]:
    try:
        import resource
    except ImportError:  # pragma: no cover - Windows
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess
        process.restype = wintypes.HANDLE
        get_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_info.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
        if get_info(process(), ctypes.byref(counters), counters.cb):
            return counters.PeakWorkingSetSize / (1024 * 1024)
        return None
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024   # macOS bytes, Linux KiB


def _worker(spec_path: str) -> Dict[str, Any]:
    from kami.config import build_run, load_run_spec

    t0 = time.perf_counter()
    spec = load_run_spec(spec_path)
    built = build_run(spec)
    build_s = time.perf_counter() - t0
    sim = built.simulation().run()
    m = sim.metrics()
    return {"wall_s": sim.wall_time, "build_s": build_s, "events": sim.events_processed,
            "events_per_s": sim.events_processed / sim.wall_time if sim.wall_time else None,
            "peak_rss_mb": _peak_rss_mb(), "network_backend": getattr(sim.network, "backend", "grid"),
            "requests": len(sim.scenario.requests), "drivers": len(sim.scenario.drivers),
            "solver": sim.policy.matching.solver,
            "cohorts": _cohorts(sim, spec),
            "metrics": {k: (None if isinstance(v, float) and not math.isfinite(v) else v)
                        for k, v in m.items() if k in KEY_METRICS or k.startswith("shared.") or k in ("ops.vehicle_km", "ops.empty_km")}}


def _cohorts(sim, spec):
    """Label both experiment arms by the same demand preference, outside the engine."""
    cfg = spec.sim_config.to_dict().get('shared_ride')
    if not cfg:
        return None
    from kami.shared import SharedRideConfig
    from kami.core.crn import CRN
    from kami.core.agents import RiderState
    from kami.metrics import measured_riders, mean, percentile, ratio
    weights = SharedRideConfig(preference_weights=cfg.get('preference_weights', {'exclusive_only': 1}))
    crn = CRN(sim.scenario.seed)
    cohorts = {}
    for pref in ('shared_only', 'exclusive_only'):
        rs = [r for r in measured_riders(sim) if weights.preference(r.attrs, r.id, crn) == pref]
        booked = [r for r in rs if r.t_booked is not None]
        done = [r for r in rs if r.state == RiderState.DONE]
        picked = [r for r in rs if r.t_pickup is not None]
        waits = [(r.t_pickup-r.t_booked)/60 for r in picked]
        gmv = sum(r.fare_paid for r in done)
        payout = sum(sim.fare_model.driver_payout(r.fare, r.surcharge) for r in done)
        vals = dict(requests=len(rs), booked=len(booked), served=len(done),
                    cancelled=sum(r.state == RiderState.CANCELLED for r in rs),
                    unfinished=sum(not r.is_terminal for r in booked),
                    completion_rate=ratio(len(done),len(booked)), wait_mean=mean(waits),
                    wait_p50=percentile(waits,50),wait_p90=percentile(waits,90),wait_p95=percentile(waits,95),
                    gmv=gmv,payout=payout,platform_fee=gmv-payout)
        cohorts[pref] = {k: None if isinstance(v,float) and not math.isfinite(v) else v for k,v in vals.items()}
    return cohorts


def _run_case(path: Path) -> Dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(REPO)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    proc = subprocess.run([sys.executable, "-m", "kami.bench", "--worker", str(path)], capture_output=True,
                          text=True, env=env)
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(MARK):
            return json.loads(line[len(MARK):])
    raise RuntimeError(f"benchmark case {path.name} failed (exit {proc.returncode}):\n{proc.stderr[-3000:]}")


# ---------------------------------------------------------------------------- environment
def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def _git(*args: str) -> Optional[str]:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def environment() -> Dict[str, Any]:
    import kami
    from kami.network.road.network import _cpp_router

    dirty = _git("status", "--porcelain")
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "executable": sys.executable, "os": platform.platform(), "cpu": _cpu_model(), "cpu_count": os.cpu_count(),
            "git_commit": _git("rev-parse", "--short", "HEAD"), "git_dirty": bool(dirty),
            "kami_version": kami.__version__, "cpp_router_built": _cpp_router() is not None}


# ---------------------------------------------------------------------------- suite
def missing_data(spec_path: Path) -> Optional[str]:
    """Reason to skip a case whose road network has not been built (e.g. Hà Nội: ``python -m kami.osm build``)."""
    from kami.config import load_run_spec
    from kami.config.specs import RoadNetworkSpec
    from kami.network.road import network_path

    spec = load_run_spec(spec_path)
    net = getattr(spec.scenario, "network", None)
    if isinstance(net, RoadNetworkSpec):
        try:
            network_path(net.name, net.data_root)
        except FileNotFoundError:
            return f"road network {net.name!r} not built"
    return None


def run_suite(suite: Path, cases: Optional[List[str]] = None, repeat: int = 3, progress: bool = True) -> Dict:
    files = sorted(Path(suite).glob("*.json"))
    if cases:
        files = [f for f in files if f.stem in cases]
        missing = set(cases) - {f.stem for f in files}
        if missing:
            raise FileNotFoundError(f"benchmark cases not found in {suite}: {sorted(missing)}")
    out: Dict[str, Any] = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                           "suite": str(suite), "repeat": repeat, "env": environment(), "cases": {}}
    for f in files:
        reason = missing_data(f)
        if reason:
            if progress:
                print(f"  {f.stem} skipped: {reason}", file=sys.stderr)
            out.setdefault("skipped", {})[f.stem] = reason
            continue
        runs = []
        for k in range(repeat):
            if progress:
                print(f"  {f.stem} [{k + 1}/{repeat}] …", end="", flush=True, file=sys.stderr)
            runs.append(_run_case(f))
            if progress:
                print(f" {runs[-1]['wall_s']:.2f}s", file=sys.stderr)
        walls = [r["wall_s"] for r in runs]
        med = statistics.median(walls)
        first = runs[0]
        out["cases"][f.stem] = {
            "wall_s": {"median": med, "min": min(walls), "max": max(walls)},
            "build_s": statistics.median(r["build_s"] for r in runs),
            "events": first["events"], "events_per_s": first["events"] / med if med else None,
            "peak_rss_mb": max((r["peak_rss_mb"] or 0) for r in runs) or None,
            "network_backend": first["network_backend"], "requests": first["requests"],
            "drivers": first["drivers"], "metrics": first["metrics"],
            "solver": first.get("solver"),
            "cohorts": first.get("cohorts"),
            "deterministic": all(r["events"] == first["events"] and r["metrics"] == first["metrics"]
                                 and r.get("cohorts") == first.get("cohorts") for r in runs),
        }
    return out


def table(res: Dict) -> str:
    lines = [f"{'case':26s} {'wall_s':>8s} {'min':>8s} {'max':>8s} {'events':>9s} {'ev/s':>9s} {'RSS MB':>7s} "
             f"{'backend':>7s}"]
    for name, c in res["cases"].items():
        w = c["wall_s"]
        lines.append(f"{name:26s} {w['median']:8.2f} {w['min']:8.2f} {w['max']:8.2f} {c['events']:9d} "
                     f"{c['events_per_s'] or 0:9.0f} {c['peak_rss_mb'] or 0:7.0f} {c['network_backend']:>7s}")
    for name, reason in res.get("skipped", {}).items():
        lines.append(f"{name:26s} skipped: {reason}")
    return "\n".join(lines)


def compare(new: Dict, old: Dict, threshold: float = 0.10) -> Tuple[str, List[str]]:
    """Change table vs. a baseline result; returns ``(text, regressed case names)``."""
    lines = [f"{'case':26s} {'wall old':>9s} {'wall new':>9s} {'Δ%':>7s} {'RSS old':>8s} {'RSS new':>8s} {'Δ%':>7s}  "
             f"note"]
    bad = []
    for name, c in new["cases"].items():
        o = old.get("cases", {}).get(name)
        if o is None:
            lines.append(f"{name:26s} {'—':>9s} {c['wall_s']['median']:9.2f}  (new case)")
            continue
        dw = c["wall_s"]["median"] / o["wall_s"]["median"] - 1
        rn, ro = c.get("peak_rss_mb") or 0, o.get("peak_rss_mb") or 0
        dr = rn / ro - 1 if ro else 0.0
        notes = []
        if dw > threshold:
            notes.append(f"SLOWER > {threshold:.0%}")
        if dr > threshold:
            notes.append(f"RAM > {threshold:.0%}")
        if notes:
            bad.append(name)
        if c["events"] != o["events"] or c["metrics"] != o["metrics"]:
            notes.append("results changed")
        lines.append(f"{name:26s} {o['wall_s']['median']:9.2f} {c['wall_s']['median']:9.2f} {dw:+7.1%} "
                     f"{ro:8.0f} {rn:8.0f} {dr:+7.1%}  {', '.join(notes)}")
    if new.get("env", {}).get("python") != old.get("env", {}).get("python") or \
            new.get("env", {}).get("cpu") != old.get("env", {}).get("cpu"):
        lines.append("warning: different Python/CPU than the baseline; numbers are not comparable")
    return "\n".join(lines), bad


def run_cli(args) -> int:
    cases = [c.strip() for c in args.cases.split(",")] if args.cases else None
    res = run_suite(Path(args.suite), cases, args.repeat)
    print(table(res))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(res, indent=2) + "\n")
        print(f"wrote {args.out}")
    if args.compare:
        text, bad = compare(res, json.loads(Path(args.compare).read_text()), args.threshold)
        print(text)
        if bad:
            print(f"regression in: {', '.join(bad)}", file=sys.stderr)
            return 1
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="kami.bench", description=__doc__.splitlines()[0])
    p.add_argument("--worker", default=None, help=argparse.SUPPRESS)
    add_arguments(p)
    args = p.parse_args(argv)
    if args.worker:
        print(MARK + json.dumps(_worker(args.worker)))
        return 0
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
