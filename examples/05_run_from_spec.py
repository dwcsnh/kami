"""Run simulations from declarative RunSpec files and store them in a database (kami 0.2, sprint 01).

    python examples/05_run_from_spec.py

Same as the command line::

    python -m kami run --spec examples/specs/fleets_policy_group.json --out out/spec_run
    python -m kami run --spec examples/specs/fleets_policy_group.json --db out/kami.db --artifacts out/runs
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kami.config import PolicySpec, RunSpec, load_run_spec, run_spec  # noqa: E402

here = Path(__file__).resolve().parent
out = here / "output"

# (a) library mode: no database involved (NFR-5)
spec = load_run_spec(here / "specs" / "fleets_policy_group.json")
sim = run_spec(spec)
m = sim.metrics()
print(f"{spec.name}: {sim.events_processed} events in {sim.wall_time:.2f}s, trips={m['platform.trips']:.0f}, "
      f"wait={m['rider.wait_mean']:.2f} min, policy={sim.policy.name}")
print(f"time series: {len(sim.timeseries.rows)} rows, e.g. {sim.timeseries.rows[3]}")

# (b) database mode: store entities, reference them from a RunSpec, record the run
from kami.store import Repository, execute  # noqa: E402

db = out / "kami_example.db"
db.unlink(missing_ok=True)
repo = Repository.open(db)
for vt in spec.vehicle_types:
    repo.save_vehicle_type(vt)
for fl in spec.fleets:
    repo.save_fleet(fl)
repo.save_scenario(spec.scenario)
repo.save_policy(PolicySpec("surge", {"every": 60, "max_surge": 1.8}), name="surge_fast")
by_ref = RunSpec.from_dict({
    "name": "from_db", "scenario": {"ref": spec.scenario.name},
    "fleets": [{"ref": "taxi"}, {"ref": "bike"}],
    "policy_group": {"name": "surge_only", "members": [{"policy": {"ref": "surge_fast"}}]},
})
res = execute(by_ref, repo, artifacts_dir=out / "runs")
run = repo.get_run(res.run_id)
print(f"run {res.run_id}: {run['status']}, provenance={run['provenance']}")
print(f"  metrics stored: {len(repo.run_metrics(res.run_id))}, time-series rows: "
      f"{len(repo.run_timeseries(res.run_id))}, event log: {repo.run_artifacts(res.run_id)[0]['path']}")
