"""Separate training pipeline → model registry → simulator (design doc §2 principle 7).

Here the "historical data" are themselves simulated so the example is
self-contained: we fit a Weibull cancellation model and an idle-movement
transition matrix from a baseline run's event log, save them as registry
checkpoints, and load them back into a BehaviorSuite.

    python examples/04_train_and_register.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kami import Baseline, GridNetwork, ModelRegistry, ScenarioBuilder, Simulation, SquareZoneSystem  # noqa: E402
from kami.behavior import TransitionMatrixIdleMove, WeibullCancel  # noqa: E402
from kami.core.agents import RiderState  # noqa: E402
from kami.training import fit_transition_matrix, fit_weibull_cancel  # noqa: E402

net = GridNetwork()
zones = SquareZoneSystem(net, 1000)
sim = Simulation(ScenarioBuilder(net, zones).preset("undersupply", seed=7), Baseline()).run()

# --- "historical" cancellation log: waited minutes until cancel (event) or until matched (censored)
recs = []
for r in sim.riders.values():
    if r.t_booked is None:
        continue
    if r.state == RiderState.CANCELLED and r.cancel_phase == "waiting":
        recs.append(((r.t_cancel - r.t_booked) / 60, True))
    elif r.t_matched is not None:
        recs.append(((r.t_matched - r.t_booked) / 60, False))
fit = fit_weibull_cancel(recs)
print("Weibull cancel fit:", {k: round(v, 3) for k, v in fit.items()})

# --- idle GPS segments -> zone transition matrix
moves = []
for t, ev, _, d, info in sim.log.rows:
    if ev == "IDLE_MOVE" and info.get("purpose") == "idle":
        moves.append((int(t // 3600) % 24, zones.zone_of(info["origin"]), zones.zone_of(info["dest"])))
matrix = fit_transition_matrix(moves, min_count=3)
print(f"transition matrix: {sum(len(v) for v in matrix.values())} (hour, zone) rows")

reg = ModelRegistry(Path(__file__).resolve().parent / "output" / "registry")
reg.save("cancel_wait", WeibullCancel(shape=round(fit["shape"], 3)), "v_fit",
         meta={"source": "example 04", "scale_min": fit["scale_min"], "n": len(recs)})
reg.save("idle_move", TransitionMatrixIdleMove(matrix), "v_fit", meta={"n_moves": len(moves)})
suite = reg.suite({"cancel_wait": "latest", "idle_move": "latest"})
print("loaded suite:", {k: v["class"] for k, v in suite.describe().items()})
print("registry at", reg.root)
