import math
import random
import tempfile
import unittest

from kami.behavior import (BehaviorSuite, LogitPoolAccept, ModelRegistry, ProbabilityScaler, TransitionMatrixIdleMove,
                           WeibullCancel)
from kami.behavior.protocols import Context
from kami.core.agents import PoolOffer, Rider
from kami.core.engine import Simulation
from kami.network import GridNetwork, SquareZoneSystem
from kami.policy import Baseline
from kami.training import fit_logit, fit_transition_matrix, fit_weibull_cancel
from kami.traffic import Incident, TrafficLayer
from tests.helpers import small_scenario


class TestTraffic(unittest.TestCase):
    def setUp(self):
        self.net = GridNetwork(4000, 4000, 250)
        self.zones = SquareZoneSystem(self.net, 1000)
        self.tl = TrafficLayer(self.net, self.zones, hour_profile=[1.0] * 24)

    def test_weather_and_hour(self):
        o, d = self.net.node_at(0, 0), self.net.node_at(8, 0)
        base, dist = self.tl.travel(o, d, 0)
        self.assertAlmostEqual(dist, 2000)
        self.tl.set_weather("rain")
        self.assertAlmostEqual(self.tl.travel(o, d, 0)[0], base * 1.25)

    def test_incident_slows_and_reroutes(self):
        o, d = self.net.node_at(0, 0), self.net.node_at(8, 8)
        base, _ = self.tl.travel(o, d, 0)
        zone = self.zones.zone_of(self.net.node_at(4, 0))
        self.tl.start_incident(Incident("x", {zone}, factor=5.0))
        aware, _ = self.tl.travel(o, d, 0)
        blind, _ = self.tl.estimate(o, d, 0)
        self.assertGreaterEqual(aware, base)
        self.assertLess(aware, base * 5)      # an L-route avoiding the zone exists
        self.assertEqual(blind, base)         # platform does not see incidents by default
        self.tl.end_incident("x")
        self.assertEqual(self.tl.travel(o, d, 0)[0], base)

    def test_accident_scenario_creates_eta_error(self):
        m = Simulation(small_scenario(seed=1, preset="accident", demand=150, drivers=50), Baseline()).run().metrics()
        self.assertGreater(m["rider.eta_error_abs"], 0)


class TestBehavior(unittest.TestCase):
    def test_pool_accept_monotone_in_surcharge(self):
        r = Rider(1, 0, 0, 1, {"price_sens": 1.0})
        ctx = Context(t=0, hour=8)
        m = LogitPoolAccept()
        ps = [m.p_accept(r, PoolOffer(s, 300), ctx) for s in (-20_000, 0, 20_000)]
        self.assertGreater(ps[0], ps[1])
        self.assertGreater(ps[1], ps[2])
        self.assertAlmostEqual(ProbabilityScaler(m, 0.5).p_accept(r, PoolOffer(0, 300), ctx), ps[1] * 0.5)

    def test_registry_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            reg = ModelRegistry(d)
            reg.save("pool_accept", LogitPoolAccept(asc=-2.0), "v1")
            reg.save("pool_accept", LogitPoolAccept(asc=-0.5), "v2")
            reg.save("idle_move", TransitionMatrixIdleMove({"8": {"0_0": {"stay": 1.0}}}), "v1")
            self.assertEqual(reg.versions("pool_accept"), ["v1", "v2"])
            self.assertEqual(reg.load("pool_accept").params.asc, -0.5)
            self.assertEqual(reg.load("pool_accept", "v1").params.asc, -2.0)
            suite = reg.suite({"pool_accept": "v1", "idle_move": "latest"})
            self.assertEqual(suite.pool_accept.params.asc, -2.0)
            self.assertIsInstance(suite.idle_move, TransitionMatrixIdleMove)
            self.assertIn("booking", suite.describe())


class TestTraining(unittest.TestCase):
    def test_weibull_recovers_parameters(self):
        rng = random.Random(0)
        k, lam = 1.4, 8.0
        recs = []
        for _ in range(4000):
            t = lam * (-math.log(rng.random())) ** (1 / k)
            c = rng.uniform(2, 20)                     # censoring time (rider got matched)
            recs.append((min(t, c), t <= c))
        fit = fit_weibull_cancel(recs)
        self.assertAlmostEqual(fit["shape"], k, delta=0.1)
        self.assertAlmostEqual(fit["scale_min"], lam, delta=0.6)

    def test_logit_recovers_parameters(self):
        rng = random.Random(1)
        X, y = [], []
        for _ in range(3000):
            w, s = rng.uniform(0, 10), rng.uniform(-2, 2)
            p = 1 / (1 + math.exp(-(-1 + 0.2 * w - 0.6 * s)))
            X.append([w, s])
            y.append(1 if rng.random() < p else 0)
        b = fit_logit(X, y, ["wait", "surcharge"])
        self.assertAlmostEqual(b["asc"], -1, delta=0.25)
        self.assertAlmostEqual(b["wait"], 0.2, delta=0.05)
        self.assertAlmostEqual(b["surcharge"], -0.6, delta=0.1)

    def test_transition_matrix(self):
        moves = [(8, "a", "a")] * 6 + [(8, "a", "b")] * 4
        m = fit_transition_matrix(moves, smoothing=0)
        self.assertAlmostEqual(m["8"]["a"]["stay"], 0.6)
        self.assertAlmostEqual(m["8"]["a"]["b"], 0.4)


if __name__ == "__main__":
    unittest.main()
