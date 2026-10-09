"""Small public service inputs and a real-worker HTTP fixture."""
import copy
import tempfile
import time
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    from kami.service import create_app
    HAS_SERVICE = True
except ImportError:
    HAS_SERVICE = False


def document(long=False, seed=2):
    return {"name": "test-run", "scenario": {"name": "service-test", "seed": seed, "n_drivers": 300 if long else 20,
            "source": {"kind": "synthetic", "t_start": 25200, "t_end": 28800 if long else 25800,
                       "demand_per_hour": 10000 if long else 200, "warmup_s": 0}},
            "outputs": {"event_log": "csv.gz"}, "sim_config": {"timeseries_interval_s": 60}}


@unittest.skipUnless(HAS_SERVICE, "cần kami[service-test]")
class ServiceCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.artifacts = Path(self.tmp.name) / "runs"
        self.app = create_app(self.db, self.artifacts, interval_s=0.01)
        self.client = TestClient(self.app).__enter__()
        self.api = "/api/v1"

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.tmp.cleanup()

    def queue(self, doc=None):
        response = self.client.post(self.api + "/runs", json={"spec": doc or document()})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def start(self, run_id):
        response = self.client.post(f"{self.api}/runs/{run_id}/start")
        self.assertEqual(response.status_code, 202, response.text)

    def wait(self, run_id, terminal=True, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.client.get(f"{self.api}/runs/{run_id}").json()
            if terminal and state["status"] in {"succeeded", "failed", "cancelled"}:
                return state
            if not terminal and state["progress"].get("simulation_time") is not None:
                return state
            time.sleep(0.02)
        self.fail(f"run {run_id} không cập nhật: {state}")
