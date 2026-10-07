"""Run one baseline simulation on the synthetic grid city and print key metrics.

    python examples/01_quickstart.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kami import Baseline, GridNetwork, ScenarioBuilder, Simulation, SquareZoneSystem  # noqa: E402

net = GridNetwork(width_m=8000, height_m=8000, spacing_m=250, speed_kmh=25)
zones = SquareZoneSystem(net, cell_m=1000)
scenario = ScenarioBuilder(net, zones).preset("weekday_am_peak", seed=1)
print(scenario.summary())

sim = Simulation(scenario, Baseline()).run()
m = sim.metrics()
print(f"\n{sim.events_processed} events in {sim.wall_time:.2f}s")
for key in ["rider.conversion", "rider.completion_rate", "rider.cancel_rate", "rider.wait_mean", "rider.wait_p90",
            "driver.utilization", "driver.earnings_per_hour", "platform.trips", "platform.gmv"]:
    print(f"  {key:28s} {m[key]:>14,.3f}")

out = Path(__file__).resolve().parent / "output"
sim.log.to_csv(out / "quickstart_events.csv")
print(f"\nevent log: {out / 'quickstart_events.csv'}  ({len(sim.log)} rows)")
