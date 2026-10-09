"""Hai booking WAITING, một xe, Shared 70% — dữ liệu minh họa trên lưới."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kami import BehaviorSuite, GridNetwork, Scenario, SharedRideConfig, SimConfig, Simulation, SquareZoneSystem
from kami.scenario import DriverSpec, RequestSpec

net = GridNetwork(3000, 1000, 100)
scenario = Scenario("shared-v1-example", 7, 0, 1800, net, SquareZoneSystem(net, 500),
                    [RequestSpec(1, 0, 0, net.node_at(10, 0), {"service_preference": "shared_only"}),
                     RequestSpec(2, 0, net.node_at(1, 0), net.node_at(11, 0), {"service_preference": "shared_only"})],
                    [DriverSpec(1, 0, 0, 1800)])
sim = Simulation(scenario, behavior=BehaviorSuite.employed_drivers(),
                 config=SimConfig(shared_ride=SharedRideConfig(enabled=True))).run()
for r in sim.riders.values():
    print(r.id, r.state.value, "pair", r.pair_id, "fare", r.fare, "reference", r.exclusive_reference_fare)
print({k: v for k, v in sim.metrics().items() if k.startswith("shared.") and (k.endswith("served") or k.endswith("pairs"))})
