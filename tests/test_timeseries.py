"""Sprint 01 — time-series sampler (S01-6) and event-log listeners / files."""
import math
import tempfile
import unittest
from pathlib import Path

from kami.core.engine import SimConfig, Simulation
from kami.eventlog import EventLog, load
from kami.policy import Baseline, SurgePricing
from kami.timeseries import COLUMNS
from tests.helpers import assert_metrics_equal, small_scenario


def run(interval=None, record=True, policy=None, sc=None):
    sc = sc or small_scenario(seed=2)
    return Simulation(sc, policy or SurgePricing(every=60),
                      config=SimConfig(timeseries_interval_s=interval, record_events=record)).run()


class TestMetricSampler(unittest.TestCase):
    def test_sampler_does_not_change_results(self):
        a, b = run(None), run(300)
        assert_metrics_equal(self, a.metrics(), b.metrics())
        self.assertEqual(a.events_processed, b.events_processed)
        self.assertEqual(a.log.rows, b.log.rows)
        self.assertIsNone(a.timeseries)

    def test_marks_and_totals(self):
        sim = run(300)
        rows = sim.timeseries.rows
        sc = sim.scenario
        marks = [r["t"] for r in rows]
        self.assertEqual(marks[0], sc.t_start)
        self.assertTrue(all(b - a == 300 for a, b in zip(marks[:-2], marks[1:-1])))
        self.assertEqual(marks[-1], sim.t)
        self.assertEqual(list(rows[0]), COLUMNS)
        m = sim.metrics()
        # no warm-up: every rider is measured, so window sums equal the final metrics
        self.assertEqual(sum(sim.timeseries.series("rider.completed")), m["platform.trips"])
        self.assertEqual(sum(sim.timeseries.series("rider.requests")), m["rider.requests"])
        self.assertEqual(rows[-1]["rider.booked_cum"], m["rider.booked"])
        self.assertAlmostEqual(rows[-1]["platform.gmv_cum"], m["platform.gmv"], places=3)
        cancelled = sum(1 for r in sim.riders.values() if r.state.value == "CANCELLED")
        self.assertEqual(rows[-1]["rider.cancelled_cum"], cancelled)

    def test_state_gauges(self):
        sim = run(600)
        for r in sim.timeseries.rows:
            self.assertEqual(r["driver.online"], r["driver.idle"] + r["driver.repositioning"] + r["driver.en_route"]
                             + r["driver.on_trip"])
            if r["driver.online"]:
                self.assertAlmostEqual(r["driver.utilization_now"], r["driver.on_trip"] / r["driver.online"])
        busy = [r for r in sim.timeseries.rows[1:-1]]
        self.assertTrue(any(r["driver.on_trip"] > 0 for r in busy))
        waits = [r["rider.wait_mean"] for r in busy if not math.isnan(r["rider.wait_mean"])]
        self.assertTrue(waits and all(w >= 0 for w in waits))

    def test_works_without_recording_events(self):
        a, b = run(300, record=True), run(300, record=False)
        self.assertEqual(len(b.log), 0)
        self.assertEqual(len(a.timeseries.rows), len(b.timeseries.rows))
        for ra, rb in zip(a.timeseries.rows, b.timeseries.rows):
            assert_metrics_equal(self, ra, rb)

    def test_export(self):
        sim = run(900)
        with tempfile.TemporaryDirectory() as d:
            sim.timeseries.to_json(Path(d) / "ts.json")
            sim.timeseries.to_csv(Path(d) / "ts.csv")
            self.assertIn("null", (Path(d) / "ts.json").read_text())   # NaN of empty windows

    def test_invalid_interval(self):
        with self.assertRaises(ValueError):
            Simulation(small_scenario(), Baseline(), config=SimConfig(timeseries_interval_s=-5)).run()


class TestEventLogFiles(unittest.TestCase):
    def test_listener_sees_rows_when_disabled(self):
        log = EventLog(enabled=False)
        seen = []
        log.subscribe(lambda *row: seen.append(row))
        log.add(1.23456, "PICKUP", 3, 4, wait=12.0)
        self.assertEqual(len(log), 0)
        self.assertEqual(seen, [(1.23456, "PICKUP", 3, 4, {"wait": 12.0})])

    def test_save_load_round_trip(self):
        sim = run(None, policy=Baseline())
        with tempfile.TemporaryDirectory() as d:
            formats = ["csv.gz"]
            try:
                import pyarrow  # noqa: F401
                formats.append("parquet")
            except ImportError:
                pass
            for fmt in formats:
                path = sim.log.save(Path(d) / f"events.{fmt}", fmt)
                rows = load(path)
                self.assertEqual(len(rows), len(sim.log))
                self.assertEqual([r[:4] for r in rows], [r[:4] for r in sim.log.rows])
                self.assertEqual(rows[100][4], {k: v for k, v in sim.log.rows[100][4].items()})
            with self.assertRaises(ValueError):
                sim.log.save(Path(d) / "x", "xml")

    def test_csv_compress_by_suffix(self):
        log = EventLog()
        log.add(1.0, "X", None, 2, a=1)
        with tempfile.TemporaryDirectory() as d:
            p = log.to_csv(Path(d) / "e.csv.gz")
            self.assertEqual(p.read_bytes()[:2], b"\x1f\x8b")
            self.assertEqual(load(p), [(1.0, "X", None, 2, {"a": 1})])


if __name__ == "__main__":
    unittest.main()
