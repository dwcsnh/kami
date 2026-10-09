import unittest
from tests.shared_helpers import world
from tests.helpers import assert_metrics_equal


class Metrics(unittest.TestCase):
    def test_overlap_uses_sample_time_between_events(self):
        sim = world(timeseries_interval_s=10).run()
        row = next(r for r in sim.timeseries.rows if r['t'] == 100)
        self.assertEqual(row['shared.overlap_min'],1)

    def test_cohorts_quantiles_predictions_actual_and_no_data(self):
        sim=world().run();m=sim.metrics()
        self.assertEqual(m['shared.shared_only.served'],2)
        self.assertEqual(m['shared.actual_pairs'],1)
        self.assertEqual(m['shared.overlap_min'],2)
        self.assertAlmostEqual(m['shared.shared_only.wait_p50'],1/3)
        self.assertAlmostEqual(m['shared.shared_only.wait_p95'],38/60)
        import math
        self.assertTrue(math.isnan(m['shared.exclusive_only.wait_p50']))
        assert_metrics_equal(self,m,world(record_events=False).run().metrics())

    def test_traffic_violation_is_actual_separate_from_prediction(self):
        sim=world();sim.traffic.platform_sees_incidents=True;sim.t_stop=1500
        sim.scenario.weather=[(60,'heavy_rain')];sim.traffic.weather_factor['heavy_rain']=10
        sim.run();m=sim.metrics()
        self.assertEqual(m['shared.shared_only.extra_ride_violations'],2)
        self.assertLess(m['shared.shared_only.predicted_extra_ride_mean'],7.5)
        self.assertGreater(m['shared.shared_only.extra_ride_mean'],7.5)
