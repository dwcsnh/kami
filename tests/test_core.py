import heapq
import math
import unittest

from kami.core.agents import DriverState, RiderState
from kami.core.crn import CRN
from kami.core.engine import SimConfig, Simulation
from kami.core.events import EVENT_PRIORITY, Event, EventType as E
from kami.policy import Baseline, Policy, PoolAfterWait
from tests.helpers import small_scenario


class TestCRN(unittest.TestCase):
    def test_deterministic_and_order_independent(self):
        a, b = CRN(7), CRN(7)
        xs = [a.u("cancel", i) for i in range(50)]
        ys = [b.u("cancel", i) for i in reversed(range(50))][::-1]
        self.assertEqual(xs, ys)
        self.assertTrue(all(0 < x < 1 for x in xs))

    def test_streams_and_seeds_differ(self):
        c = CRN(7)
        self.assertNotEqual(c.u("a", 1), c.u("b", 1))
        self.assertNotEqual(CRN(7).u("a", 1), CRN(8).u("a", 1))

    def test_uniform_moments(self):
        c = CRN(3)
        xs = [c.u("x", i) for i in range(20000)]
        self.assertAlmostEqual(sum(xs) / len(xs), 0.5, delta=0.01)
        es = [c.exp("e", i) for i in range(20000)]
        self.assertAlmostEqual(sum(es) / len(es), 1.0, delta=0.03)


class TestEvents(unittest.TestCase):
    def test_tie_break(self):
        q = []
        heapq.heappush(q, Event(10, EVENT_PRIORITY[E.DISPATCH_TICK], 1, E.DISPATCH_TICK))
        heapq.heappush(q, Event(10, EVENT_PRIORITY[E.ARRIVE_STOP], 2, E.ARRIVE_STOP))
        heapq.heappush(q, Event(10, EVENT_PRIORITY[E.ARRIVE_STOP], 3, E.ARRIVE_STOP))
        heapq.heappush(q, Event(5, EVENT_PRIORITY[E.POLICY_TIMER], 4, E.POLICY_TIMER))
        order = [heapq.heappop(q).seq for _ in range(4)]
        self.assertEqual(order, [4, 2, 3, 1])


class TestEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sc = small_scenario()
        cls.sim = Simulation(cls.sc, Baseline()).run()

    def test_reproducible(self):
        again = Simulation(self.sc, Baseline()).run()
        m1, m2 = self.sim.metrics(), again.metrics()
        for k in m1:
            self.assertTrue(m1[k] == m2[k] or (math.isnan(m1[k]) and math.isnan(m2[k])), k)
        self.assertEqual(self.sim.log.rows, again.log.rows)

    def test_every_booked_rider_terminal_after_drain(self):
        for r in self.sim.riders.values():
            self.assertIn(r.state, (RiderState.DONE, RiderState.CANCELLED, RiderState.DECLINED), r.id)

    def test_rider_timeline_consistent(self):
        for r in self.sim.riders.values():
            if r.state == RiderState.DONE:
                self.assertLessEqual(r.t_request, r.t_booked)
                self.assertLessEqual(r.t_booked, r.t_matched)
                self.assertLessEqual(r.t_matched, r.t_pickup)
                self.assertLess(r.t_pickup, r.t_dropoff)
                self.assertGreaterEqual(r.t_dropoff - r.t_pickup, r.direct_tt * 0.99 - 1)

    def test_driver_accounting(self):
        for d in self.sim.drivers.values():
            self.assertEqual(d.state, DriverState.OFFLINE)
            self.assertLessEqual(d.occupied_time, d.busy_time + 1e-6)
            self.assertLessEqual(d.busy_time, d.online_time + 1e-6)
            self.assertLessEqual(d.dist_empty, d.dist_total + 1e-6)
        trips = sum(d.trips for d in self.sim.drivers.values())
        done = sum(r.state == RiderState.DONE for r in self.sim.riders.values())
        self.assertEqual(trips, done)

    def test_metrics_sane(self):
        m = self.sim.metrics()
        self.assertGreater(m["rider.completion_rate"], 0.5)
        self.assertAlmostEqual(m["rider.completion_rate"] + m["rider.cancel_rate"] + m["rider.unfinished_rate"], 1, 6)
        self.assertGreater(m["rider.wait_p90"], m["rider.wait_p50"])
        self.assertGreater(m["platform.gmv"], m["platform.revenue"])

    def test_policy_may_only_schedule_timers(self):
        sim = Simulation(self.sc, Baseline())
        with self.assertRaises(ValueError):
            sim.schedule(sim.t + 1, "DISPATCH_TICK")

    def test_run_once(self):
        with self.assertRaises(RuntimeError):
            self.sim.run()


class TestCRNPairing(unittest.TestCase):
    def test_noop_policy_is_identical_to_baseline(self):
        """A treatment that never acts must give *exactly* the baseline (no noise) — the essence of CRN."""
        sc = small_scenario(seed=4)

        class Noop(Policy):
            name = "noop"

            def on_request(self, sim, r):
                sim.schedule(sim.t + 60, "POLICY_TIMER", r=r)

            def on_timer(self, sim, r, **kw):
                pass

        a = Simulation(sc, Baseline()).run().metrics()
        b = Simulation(sc, Noop()).run().metrics()
        for k in a:
            self.assertTrue(a[k] == b[k] or (math.isnan(a[k]) and math.isnan(b[k])), k)

    def test_independent_seed_differs(self):
        sc = small_scenario(seed=4)
        a = Simulation(sc, Baseline(), crn_seed=1).run().metrics()
        b = Simulation(sc, Baseline(), crn_seed=2).run().metrics()
        self.assertNotEqual(a["rider.booked"], b["rider.booked"])


class TestLazyInvalidation(unittest.TestCase):
    def test_stale_cancel_ignored_after_pickup(self):
        sim = Simulation(small_scenario(seed=2), Baseline()).run()
        cancels = {r for _, ev, r, _, _ in sim.log.rows if ev == "RIDER_CANCEL"}
        picked = {r for _, ev, r, _, _ in sim.log.rows if ev == "PICKUP"}
        self.assertFalse(cancels & picked)


if __name__ == "__main__":
    unittest.main()
