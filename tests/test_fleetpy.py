"""Integration with FleetPy (skipped when FleetPy or its dependencies are unavailable)."""
import unittest

try:
    from kami.network import FleetPyNetwork, FleetPyZoneSystem
    from kami.network.fleetpy_network import default_fleetpy_root

    NET = FleetPyNetwork("example_network")
    HAVE_FLEETPY = True
except Exception as exc:  # noqa: BLE001 - any import/data problem means "skip"
    HAVE_FLEETPY = False
    REASON = str(exc)

from kami.core.engine import Simulation
from kami.policy import Baseline
from kami.scenario import ScenarioBuilder


@unittest.skipUnless(HAVE_FLEETPY, "FleetPy not available")
class TestFleetPy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zones = FleetPyZoneSystem(NET, "example_zones")
        cls.builder = ScenarioBuilder(NET, cls.zones)

    def test_routing_matches_fleetpy(self):
        locs = NET.location_nodes()
        o, d = locs[10], locs[500]
        tt, dist = NET.base_travel(o, d)
        cost, tt2, dist2 = NET.nw.return_travel_costs_1to1((o, None, None), (d, None, None))
        self.assertAlmostEqual(tt, tt2, places=3)
        self.assertAlmostEqual(dist, dist2, places=1)
        path = NET.path(o, d)
        self.assertEqual(path[0][0], o)
        self.assertEqual(path[-1][0], d)
        self.assertAlmostEqual(path[-1][1], tt, delta=1.0)

    def test_replay_fleetpy_demand(self):
        f = default_fleetpy_root() / "data/demand/example_demand/matched/example_network/example_100.csv"
        sc = self.builder.from_fleetpy_demand(f, n_drivers=20)
        self.assertEqual(len(sc.requests), 100)
        m = Simulation(sc, Baseline()).run().metrics()
        self.assertGreater(m["platform.trips"], 50)

    def test_incident_on_real_network(self):
        sc = self.builder.preset("accident", seed=1, demand_per_hour=80, n_drivers=30, t_end=8.5 * 3600)
        sim = Simulation(sc, Baseline()).run()
        self.assertIn("INCIDENT_START", sim.log.counts())
        if NET.backend == "cpp":
            self.assertFalse(NET._live_factor)   # live state restored after the incident


if __name__ == "__main__":
    unittest.main()
