"""Reuse FleetPy: real OSM road network, FleetPy zones and FleetPy demand files.

Requires the FleetPy checkout next to kami (or KAMI_FLEETPY_ROOT) and its
dependencies (numpy, pandas, pyproj) — e.g. ``conda activate fleetpy``.

    python examples/03_fleetpy_network.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kami import (Baseline, FleetPyNetwork, FleetPyZoneSystem, PoolAfterWait, ScenarioBuilder,  # noqa: E402
                  Simulation)

t = time.time()
net = FleetPyNetwork("example_network")            # FleetPy/data/networks/example_network
zones = FleetPyZoneSystem(net, "example_zones")     # FleetPy/data/zones/example_zones
print(f"network: {net.num_nodes()} nodes, backend={net.backend}, zones={len(zones.zones())}, "
      f"loaded in {time.time() - t:.1f}s")
builder = ScenarioBuilder(net, zones)

# (a) replay a FleetPy demand file
demand = net.fleetpy_root / "data/demand/example_demand/matched/example_network/example_400.csv"
sc = builder.from_fleetpy_demand(demand, n_drivers=25)
print(sc.summary())
for pol in [Baseline(), PoolAfterWait(wait_threshold=180, surcharge=0, include_matched=True)]:
    sim = Simulation(sc, pol).run()
    m = sim.metrics()
    print(f"  {pol.name:16s} trips={m['platform.trips']:.0f} completion={m['rider.completion_rate']:.3f} "
          f"wait={m['rider.wait_mean']:.2f}min pool_rate={m['rider.pool_rate']:.3f} ({sim.wall_time:.1f}s)")

# (b) synthetic accident on the real network: incident routing goes through FleetPy's router
sc = builder.preset("accident", seed=1, demand_per_hour=150, n_drivers=60)
sim = Simulation(sc, Baseline()).run()
m = sim.metrics()
print(f"accident: trips={m['platform.trips']:.0f} eta_error={m['rider.eta_error_abs']:.2f}min "
      f"({sim.wall_time:.1f}s)")
print("first request at lon/lat", net.lonlat(sc.requests[0].origin))
