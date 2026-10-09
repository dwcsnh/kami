"""S08-5/6: actual HTTP SSE, client disconnect, bounded fan-out and supervisor crash."""
import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests.service_helpers import HAS_SERVICE, document


@unittest.skipUnless(HAS_SERVICE, "cần kami[service-test]")
class TestLiveStream(unittest.TestCase):
    def test_bounded_broker_reports_history_loss(self):
        from kami.service.stream import Broker, frame
        broker = Broker(capacity=2)
        for i in range(10):
            broker.publish(1, "metric", {"value": i})
        lost, items, cursor = broker.read(1, 0)
        self.assertTrue(lost)
        self.assertEqual(len(items), 2)
        self.assertEqual(cursor, 10)
        self.assertIn('"value": null', frame("metric", {"value": float("nan")}))

    def test_supervisor_kill_recovery_and_new_worker(self):
        from kami.config import RunSpec
        from kami.service.supervisor import Supervisor
        from kami.service.locks import FileLock
        with tempfile.TemporaryDirectory() as d:
            db, artifacts, ready = Path(d) / "k.db", Path(d) / "runs", Path(d) / "ready.json"
            process = subprocess.Popen([sys.executable, "-m", "tests.service_host", str(db), str(artifacts), str(ready)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 30
                while not ready.exists() and time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail(process.stderr.read().decode(errors="replace"))
                    time.sleep(0.02)
                self.assertTrue(ready.exists())
                old = json.loads(ready.read_text())
                # The worker really owns the execution lock before the crash.
                with self.assertRaises(RuntimeError):
                    FileLock(str(db) + ".execution.lock").acquire()
                process.kill()
                process.wait(timeout=5)
                supervisor = Supervisor(db, artifacts, interval_s=0.01).open()
                try:
                    state = supervisor.detail(old["run_id"])
                    self.assertEqual((state["status"], state["error_code"]), ("failed", "interrupted"))
                    with FileLock(str(db) + ".execution.lock"):
                        pass  # the orphan is no longer executing
                    with supervisor.repository() as repo:
                        new = repo.queue_run(RunSpec.from_dict(document()))
                    supervisor.start(new)
                    deadline = time.monotonic() + 30
                    while supervisor.detail(new)["status"] == "running" and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertEqual(supervisor.detail(new)["status"], "succeeded")
                finally:
                    supervisor.close()
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                process.stderr.close()

    def test_http_metrics_before_completion_disconnect_and_determinism(self):
        import httpx
        from kami.service.metrics import visible
        with tempfile.TemporaryDirectory() as d:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            stop_file = Path(d) / "stop-http"
            command = [sys.executable, "web/scripts/manager-test-host.py", "--db", str(Path(d) / "k.db"),
                       "--artifacts", str(Path(d) / "runs"), "--port", str(port), "--stop-file", str(stop_file)]
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            url = f"http://127.0.0.1:{port}/api/v1"
            try:
                with httpx.Client(timeout=30) as client:
                    deadline = time.monotonic() + 30
                    while True:
                        try:
                            if client.get(url + "/health").status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        if process.poll() is not None or time.monotonic() >= deadline:
                            self.fail("service did not start")
                        time.sleep(0.05)
                    # Enough work for live observation, yet bounded for routine integration testing.
                    doc = document(True)
                    doc["scenario"]["n_drivers"] = 80
                    doc["scenario"]["source"]["demand_per_hour"] = 1500
                    run_id = client.post(url + "/runs", json={"spec": doc}).json()["id"]
                    client.post(f"{url}/runs/{run_id}/start").raise_for_status()
                    metric = None
                    with client.stream("GET", f"{url}/runs/{run_id}/stream") as response:
                        kind = None
                        for line in response.iter_lines():
                            if line.startswith("event: "):
                                kind = line[7:]
                            if line.startswith("data: ") and kind == "metric":
                                metric = json.loads(line[6:])["row"]
                                self.assertEqual(client.get(f"{url}/runs/{run_id}").json()["status"], "running")
                                break
                    self.assertIsNotNone(metric)
                    # Closing the stream does not cancel/block the worker.
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        state = client.get(f"{url}/runs/{run_id}").json()
                        if state["status"] != "running":
                            break
                        time.sleep(0.02)
                    self.assertEqual(state["status"], "succeeded", state.get("error"))
                    rows = client.get(f"{url}/runs/{run_id}/timeseries").json()["rows"]
                    self.assertIn(metric, rows)
                    first = client.get(f"{url}/runs/{run_id}/metrics").json()["summary"]
                    replay = client.post(url + "/runs", json={"spec": doc}).json()["id"]
                    client.post(f"{url}/runs/{replay}/start").raise_for_status()
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        again = client.get(f"{url}/runs/{replay}").json()
                        if again["status"] != "running":
                            break
                        time.sleep(0.02)
                    self.assertEqual(again["status"], "succeeded", again.get("error"))
                    self.assertEqual(first, client.get(f"{url}/runs/{replay}/metrics").json()["summary"])
                    self.assertEqual(state["events"], again["events"])
                    # Save measured engine wall times for QA, independent of pass/fail thresholds.
                    self.assertGreater(state["wall_s"], 0)
            finally:
                stop_file.write_text("stop")
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
