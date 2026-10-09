from kami import Simulation, SimConfig
from kami.behavior.registry import BehaviorSuite
from kami.network import GridNetwork, SquareZoneSystem
from kami.scenario import Scenario, RequestSpec, DriverSpec
from kami.shared import SharedRideConfig


class Book:
    def p_book(self, *args): return 1.0


class NeverCancel:
    def hazard(self, *args): return 0.0


class Accept:
    def p_accept(self, *args): return 1.0


def world(requests=None, drivers=None, **config):
    net = GridNetwork(3000, 1000, 100, speed_kmh=36)
    reqs = requests if requests is not None else [RequestSpec(1,0,0,net.node_at(10,0)), RequestSpec(2,0,net.node_at(1,0),net.node_at(11,0))]
    sc = Scenario("shared-test", 7, 0, 1000, net, SquareZoneSystem(net,500), reqs,
                  drivers if drivers is not None else [DriverSpec(1,0,0,3000)], traffic=dict(hour_profile=[1.0]*24))
    cfg = SimConfig(shared_ride=SharedRideConfig(enabled=True, preference_weights=dict(shared_only=1)),
                    idle_decision_s=10000, drain_s=0, **config)
    suite = BehaviorSuite.employed_drivers().replace(booking=Book(),cancel_wait=NeverCancel(),cancel_matched=NeverCancel(),driver_accept=Accept())
    return Simulation(sc,behavior=suite,config=cfg)
