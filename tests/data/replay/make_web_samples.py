"""Write the small replay + reference samples used by the web tests (Vitest, web/src/data/*.test.ts).

    python tests/data/replay/make_web_samples.py

Output: ``web/src/data/__fixtures__/grid_small/`` — a gzip-compressed replay of a 30-minute grid run (12 vehicles) and
``samples.json``: state and position of vehicles at fixed times computed by ``kami.replay.query`` (the reference the
TypeScript look-ups must reproduce), plus ``metricsAt`` rows.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "web" / "src" / "data" / "__fixtures__" / "grid_small"


def write(out: Path = OUT) -> Path:
    from kami.core.engine import SimConfig, Simulation
    from kami.network import GridNetwork, SquareZoneSystem
    from kami.replay import export, load
    from kami.replay.query import ReplayIndex
    from kami.scenario import ScenarioBuilder

    net = GridNetwork(3000, 3000, 250)
    sc = ScenarioBuilder(net, SquareZoneSystem(net, 1000)).preset(
        "weekday_am_peak", seed=4, demand_per_hour=80, n_drivers=12, t_end=7.5 * 3600)
    sim = Simulation(sc, config=SimConfig(record_trajectories=True, timeseries_interval_s=60, drain_s=600)).run()
    export(sim, out)
    rp = load(out)
    idx = ReplayIndex(rp["trips"])
    t0, t1 = rp["manifest"]["time"]["start"], rp["manifest"]["time"]["end"]
    samples = []
    for k in range(200):
        v = rp["vehicles"][k % len(rp["vehicles"])]["id"]
        t = round(t0 + (t1 - t0) * ((k * 0.6180339887) % 1.0), 1)
        pos = idx.position_at(v, t)
        samples.append({"vehicle": v, "t": t, "state": idx.state_at(v, t),
                        "pos": None if pos is None else [round(pos[0], 6), round(pos[1], 6)]})
    m = rp["metrics"]
    metric_samples = []
    for k in range(20):
        t = round(t0 - 30 + (t1 - t0 + 60) * k / 19, 1)
        rows = [i for i, tt in enumerate(m["t"]) if tt <= t]
        metric_samples.append({"t": t, "row": rows[-1] if rows else None})
    (out / "samples.json").write_text(json.dumps({"positions": samples, "metrics": metric_samples},
                                                 sort_keys=True, indent=1) + "\n")
    return out


if __name__ == "__main__":
    print(write())
