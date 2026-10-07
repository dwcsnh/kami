import math
import unittest

from kami.evaluation import Condition, DecisionRule, Experiment
from kami.evaluation.experiment import ExperimentResult, RunRecord
from kami.evaluation.stats import compare, t_quantile
from kami.policy import Baseline, PoolAfterWait
from tests.helpers import BUILDER


def fake_result(deltas, base=10.0):
    recs = []
    for i, d in enumerate(deltas):
        recs.append(RunRecord("s", i, "baseline", {"m": base + i}, {}, 0, 0))
        recs.append(RunRecord("s", i, "treatment", {"m": base + i + d}, {}, 0, 0))
    return ExperimentResult(recs, ["baseline", "treatment"], 0, True)


class TestStats(unittest.TestCase):
    def test_t_quantile(self):
        self.assertAlmostEqual(t_quantile(0.975, 29), 2.045, places=2)

    def test_paired_ci(self):
        cmp = compare(fake_result([1.0 + 0.1 * ((-1) ** i) for i in range(30)]), "baseline", "treatment")
        e = cmp["m"]
        self.assertAlmostEqual(e.delta, 1.0, delta=0.01)
        self.assertTrue(e.significant)
        self.assertLess(e.ci_low, 1.0)
        self.assertGreater(e.ci_high, 1.0)

    def test_null_effect_not_significant(self):
        cmp = compare(fake_result([0.5 * ((-1) ** i) for i in range(30)]), "baseline", "treatment")
        self.assertFalse(cmp["m"].significant)

    def test_decision_rule(self):
        cmp = compare(fake_result([-2.0] * 10), "baseline", "treatment")
        rule = DecisionRule("r", [Condition("m", "delta_le", -1.0, significant=True),
                                  Condition("m", "rel_ge", 0.0)])
        v = rule.evaluate(cmp)
        self.assertFalse(v.passed)
        self.assertTrue(v.results[0]["passed"])
        self.assertFalse(v.results[1]["passed"])


class TestExperiment(unittest.TestCase):
    def test_crn_narrows_ci(self):
        def scen(name, seed):
            return BUILDER.preset(name, seed=seed, demand_per_hour=150, n_drivers=40, t_end=8.5 * 3600)

        arms = {"baseline": Baseline, "treatment": lambda: PoolAfterWait(wait_threshold=120, surcharge=0)}
        crn = Experiment(scen, ["undersupply"], range(12), arms, crn=True).run().compare()
        ind = Experiment(scen, ["undersupply"], range(12), arms, crn=False).run().compare()
        # paired differences are much less noisy when both arms share the agents' random numbers
        self.assertLess(crn["rider.booked"].sd_delta * 2, ind["rider.booked"].sd_delta)
        self.assertLess(crn["rider.completion_rate"].sd_delta, ind["rider.completion_rate"].sd_delta)


if __name__ == "__main__":
    unittest.main()
