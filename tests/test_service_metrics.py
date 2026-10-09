"""S08-8: JSON null, metric direction, comparisons and API error contracts."""
from tests.service_helpers import ServiceCase, document
from kami.config import RunSpec
from kami.store.service import ServiceRepository


class TestMetrics(ServiceCase):
    def test_comparison_direction_missing_zero_and_seed_warning(self):
        repo = ServiceRepository.open(self.db)
        try:
            ids = []
            for seed, metrics in ((1, {"rider.wait_mean": 10, "platform.trips": 0, "rider.fare_mean": 100,
                                       "rider.wait_p90": float("nan"), "rider.pool_rate": 0}),
                                  (2, {"rider.wait_mean": 8, "platform.trips": 5, "rider.fare_mean": 110})):
                run_id = repo.queue_run(RunSpec.from_dict(document(seed=seed)))
                repo.claim(run_id, "token")
                repo.save_run_metrics(run_id, metrics)
                repo.finish(run_id, "token", "succeeded")
                ids.append(run_id)
        finally:
            repo.close()
        response = self.client.get(self.api + "/runs/compare?ids=" + ",".join(map(str, ids)))
        self.assertEqual(response.status_code, 200, response.text)
        comp = response.json()["comparisons"][0]
        self.assertIn("unpaired_seed", comp["warnings"])
        metrics = {r["metric"]: r for r in comp["metrics"]}
        self.assertEqual(metrics["rider.wait_mean"]["verdict"], "better")
        self.assertEqual(metrics["platform.trips"]["verdict"], "better")
        self.assertIsNone(metrics["platform.trips"]["delta_percent"])
        self.assertIsNone(metrics["rider.fare_mean"]["verdict"])
        self.assertIsNone(metrics["rider.wait_p90"]["delta"])
        self.assertNotIn("rider.pool_rate", metrics)
        summary = self.client.get(f"{self.api}/runs/{ids[0]}/metrics").json()["summary"]
        self.assertIsNone(summary["rider.wait_p90"])
        for bad in ("1", "a,2", "1,1", "-1,2"):
            self.assertEqual(self.client.get(self.api + "/runs/compare?ids=" + bad).status_code, 422)
        self.assertEqual(self.client.get(self.api + "/runs/compare?ids=999,998").status_code, 404)
        self.assertEqual(self.client.get(self.api + "/runs?status=bogus").status_code, 422)
        self.assertEqual(self.client.get(self.api + "/runs/999/metrics").status_code, 404)
        queued = self.queue()
        self.assertEqual(self.client.get(f"{self.api}/runs/{queued}/timeseries").status_code, 409)
        self.assertEqual(self.client.get(f"{self.api}/runs/{queued}/stream", headers={"Last-Event-ID": "invalid"}).status_code, 422)

    def test_sse_terminal_reconnect_and_health(self):
        self.assertFalse(self.client.get(self.api + "/health").json()["capabilities"]["live_vehicle_snapshots"])
        run_id = self.queue()
        self.client.post(f"{self.api}/runs/{run_id}/cancel")
        response = self.client.get(f"{self.api}/runs/{run_id}/stream")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertIn("event: terminal", response.text)
        self.assertIn('"cancelled"', response.text)
