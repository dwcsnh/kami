import unittest

from kami.behavior import BehaviorSuite, LogitPoolAccept, ProbabilityScaler
from kami.core.agents import RiderState
from kami.core.engine import Simulation
from kami.policy import Baseline, Composite, HeatmapReposition, PoolAfterWait, SurgePricing
from tests.helpers import BUILDER, small_scenario


class AlwaysPool(ProbabilityScaler):
    def __init__(self):
        super().__init__(LogitPoolAccept(), 100.0)


class TestPoolAfterWait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # under-supply so riders actually wait; everybody accepts pooling
        cls.sc = small_scenario(seed=3, preset="undersupply", demand=220, drivers=40)
        suite = BehaviorSuite(pool_accept=AlwaysPool())
        cls.pol = PoolAfterWait(wait_threshold=120, surcharge=20_000, include_matched=True, retry_every=60)
        cls.sim = Simulation(cls.sc, cls.pol, suite).run()

    def test_pools_happen(self):
        pooled = [r for r in self.sim.riders.values() if r.pooled]
        self.assertGreater(len(pooled), 4)

    def test_pooled_riders_share_vehicle_and_respect_detour(self):
        p = self.sim.pooling.p
        for job in self.sim.jobs.values():
            if not job.pooled:
                continue
            done = [self.sim.riders[r] for r in job.rider_ids if self.sim.riders[r].state == RiderState.DONE]
            self.assertLessEqual(len({r.driver_id for r in done}), 1)
            for r in done:
                ivt = r.t_dropoff - r.t_pickup
                # planned limit + slack for traffic changes and boarding at intermediate stops
                self.assertLessEqual(ivt, r.direct_tt * (1 + p.max_detour_ratio) + p.max_detour_abs + 120)

    def test_surcharge_charged(self):
        for r in self.sim.riders.values():
            if r.pooled and r.state == RiderState.DONE:
                self.assertEqual(r.surcharge, 20_000)

    def test_pool_offers_logged(self):
        self.assertGreater(self.sim.log.counts().get("POOL_OFFER", 0), 0)
        self.assertGreater(self.sim.log.counts().get("POOL_MERGE", 0), 0)


class TestOtherPolicies(unittest.TestCase):
    def test_surge_prices_out_demand(self):
        sc = small_scenario(seed=5, preset="undersupply", demand=200, drivers=40)
        pol = Composite(SurgePricing(every=120, threshold=1.0), HeatmapReposition(every=300))
        sim = Simulation(sc, pol).run()
        surged = [r for r in sim.riders.values() if r.quote and r.quote.surge > 1.0]
        self.assertTrue(surged)
        base = Simulation(sc, Baseline()).run().metrics()
        self.assertLess(sim.metrics()["rider.conversion"], base["rider.conversion"])

    def test_reposition_moves_surplus_drivers(self):
        sc = BUILDER.preset("oversupply", seed=5, demand_per_hour=120, n_drivers=60, t_end=14.5 * 3600)
        sim = Simulation(sc, HeatmapReposition(every=300)).run()
        moves = [info for _, ev, _, _, info in sim.log.rows if ev == "IDLE_MOVE" and info.get("purpose") == "reposition"]
        self.assertTrue(moves)


if __name__ == "__main__":
    unittest.main()
