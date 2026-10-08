"""Real road network: OSM-derived network, zone file and demand file shipped in ``data/``.

Runs with the standard library only (pure-Python router). For the ~20× faster C++ router build it once:
``pip install cython && python -m kami.network.road.cpp.build``. ``pyproj`` is needed for lon/lat output.

    python examples/03_road_network.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kami import (Baseline, FileZoneSystem, PoolAfterWait, RoadNetwork, ScenarioBuilder,  # noqa: E402
                  Simulation)

t = time.time()
net = RoadNetwork("example_network")            # data/networks/example_network
zones = FileZoneSystem(net, "example_zones")    # data/zones/example_zones
print(f"network: {net.num_nodes()} nodes, backend={net.backend}, zones={len(zones.zones())}, "
      f"loaded in {time.time() - t:.1f}s")
builder = ScenarioBuilder(net, zones)

# (a) replay a demand file (columns rq_time,start,end,request_id)
demand = net.data_root / "demand/example_demand/matched/example_network/example_400.csv"
sc = builder.from_fleetpy_demand(demand, n_drivers=25)
print(sc.summary())
for pol in [Baseline(), PoolAfterWait(wait_threshold=180, surcharge=0, include_matched=True)]:
    sim = Simulation(sc, pol).run()
    m = sim.metrics()
    print(f"  {pol.name:16s} trips={m['platform.trips']:.0f} completion={m['rider.completion_rate']:.3f} "
          f"wait={m['rider.wait_mean']:.2f}min pool_rate={m['rider.pool_rate']:.3f} ({sim.wall_time:.1f}s)")

# (b) synthetic accident on the real network: routing avoids the incident area
sc = builder.preset("accident", seed=1, demand_per_hour=150, n_drivers=60)
sim = Simulation(sc, Baseline()).run()
m = sim.metrics()
print(f"accident: trips={m['platform.trips']:.0f} eta_error={m['rider.eta_error_abs']:.2f}min "
      f"({sim.wall_time:.1f}s)")
try:
    print("first request at lon/lat", net.lonlat(sc.requests[0].origin))
except ImportError:
    print("install pyproj for lon/lat output")
