"""S08-3/4/5/7: true spawned workers, simultaneous starts, cancellation and failures."""
import concurrent.futures
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

from kami.config import RunSpec, run_spec
from kami.store.service import ServiceRepository
from tests.helpers import assert_metrics_equal
from tests.service_helpers import ServiceCase, document


class TestRuns(ServiceCase):
    def test_worker_results_equal_engine_and_cli(self):
        run_id = self.queue()
        self.start(run_id)
        state = self.wait(run_id)
        self.assertEqual(state["status"], "succeeded", state.get("error"))
        snapshot = RunSpec.from_dict(state["run_spec"])
        sim = run_spec(snapshot)
        repo = ServiceRepository.open(self.db)
        try:
            assert_metrics_equal(self, repo.run_metrics(run_id), sim.metrics())
            for a, b in zip(repo.run_timeseries(run_id), sim.timeseries.rows):
                assert_metrics_equal(self, a, b)
            self.assertEqual(len(repo.run_timeseries(run_id)), len(sim.timeseries.rows))
            from kami.eventlog import load
            artifact = repo.run_artifacts(run_id)[0]
            self.assertEqual(load(artifact["path"]), list(sim.log))
            self.assertEqual(artifact["rows"], len(sim.log))
        finally:
            repo.close()
        spec_file = Path(self.tmp.name) / "snapshot.json"
        spec_file.write_text(json.dumps(state["run_spec"]), encoding="utf-8")
        folder = Path(self.tmp.name) / "cli"
        proc = subprocess.run([sys.executable, "-m", "kami", "run", "--spec", str(spec_file), "--out", str(folder)],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        actual = self.client.get(f"{self.api}/runs/{run_id}/metrics").json()["summary"]
        cli = json.loads((folder / "metrics.json").read_text())
        for key, value in actual.items():
            self.assertEqual(value, cli[key] if value is not None else None)
        self.assertEqual(state["events"], sim.events_processed)
        self.assertEqual(state["progress"]["fraction"], 1.0)
        self.assertEqual(self.client.post(f"{self.api}/runs/{run_id}/start").status_code, 409)

    def test_concurrent_start_cancel_and_single_service(self):
        a, b = self.queue(document(True)), self.queue(document(True))
        barrier = threading.Barrier(2)
        def start(i):
            barrier.wait()
            return i, self.client.post(f"{self.api}/runs/{i}/start").status_code
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(start, (a, b)))
        self.assertEqual(sorted(code for _, code in results), [202, 409])
        chosen = next(i for i, code in results if code == 202)
        self.wait(chosen, terminal=False)
        from kami.service.supervisor import Supervisor
        other = Supervisor(self.db, self.artifacts)
        with self.assertRaises(RuntimeError):
            other.open()
        worker = self.app.state.supervisor.process
        begin = time.monotonic()
        response = self.client.post(f"{self.api}/runs/{chosen}/cancel")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "cancelled")
        self.assertLessEqual(time.monotonic() - begin, 3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.client.get(f"{self.api}/runs/{chosen}/metrics").status_code, 409)
        queued = b if chosen == a else a
        self.assertEqual(self.client.post(f"{self.api}/runs/{queued}/cancel").json()["status"], "cancelled")
        self.assertEqual(self.client.post(f"{self.api}/runs/{queued}/start").status_code, 409)

    def test_build_failure_worker_exit_spawn_failure_and_persist_failure(self):
        doc = document()
        doc["behavior"] = {"registry": str(Path(self.tmp.name) / "missing-registry")}
        failed = self.queue(doc)
        self.start(failed)
        self.assertEqual(self.wait(failed)["status"], "failed")
        # No partial summary is advertised for failure during artifact persistence.
        self.artifacts.write_text("file instead of directory", encoding="utf-8")
        failed = self.queue()
        self.start(failed)
        self.assertEqual(self.wait(failed)["status"], "failed")
        self.assertEqual(self.client.get(f"{self.api}/runs/{failed}/metrics").status_code, 409)
        self.artifacts.unlink()
        failed = self.queue()
        with patch("multiprocessing.process.BaseProcess.start", side_effect=OSError("spawn unavailable")):
            self.assertEqual(self.client.post(f"{self.api}/runs/{failed}/start").status_code, 409)
        self.assertEqual(self.wait(failed)["error_code"], "spawn_failed")
        failed = self.queue(document(True))
        self.start(failed)
        self.wait(failed, terminal=False)
        self.app.state.supervisor.process.terminate()
        self.assertEqual(self.wait(failed)["error_code"], "worker_exited")

    def test_failed_result_transaction_rolls_back_summary(self):
        repo = ServiceRepository.open(self.db)
        try:
            repo.conn.execute("CREATE TRIGGER fail_timeseries BEFORE INSERT ON run_metric_timeseries "
                              "BEGIN SELECT RAISE(ABORT, 'test persistence failure'); END")
        finally:
            repo.close()
        run_id = self.queue()
        self.start(run_id)
        state = self.wait(run_id)
        self.assertEqual(state["status"], "failed")
        self.assertIn("test persistence failure", state["error"])
        repo = ServiceRepository.open(self.db)
        try:
            self.assertEqual(repo.run_metrics(run_id), {})
            self.assertEqual(repo.run_timeseries(run_id), [])
        finally:
            repo.close()

    def test_monitor_failure_stops_worker_before_releasing_slot(self):
        run_id = self.queue(document(True))
        with patch("kami.store.service.ServiceRepository.progress", side_effect=OSError("progress write failed")):
            self.start(run_id)
            state = self.wait(run_id)
            self.assertEqual(state["error_code"], "monitor_failed")
            deadline = time.monotonic() + 3
            while self.app.state.supervisor.process is not None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertIsNone(self.app.state.supervisor.process)
        next_id = self.queue()
        self.start(next_id)
        self.assertEqual(self.wait(next_id)["status"], "succeeded")

    def test_terminal_is_immutable_and_recovery_only_owns_service_runs(self):
        repo = ServiceRepository.open(self.db)
        try:
            source = RunSpec.from_dict(document())
            legacy = repo.create_run(source)
            managed = repo.queue_run(source)
            # A legacy CLI run also prevents API admission while it is running.
            with self.assertRaises(ValueError):
                repo.claim(managed, "token")
            repo.finish_run(legacy, "succeeded")
            repo.claim(managed, "token")
            repo.finish(managed, "token", "cancelled")
            self.assertFalse(repo.finish(managed, "token", "succeeded"))
            another_legacy = repo.create_run(source)
            self.assertEqual(repo.recover(), [])
            self.assertEqual(repo.get_run(another_legacy)["status"], "running")
            repo.finish_run(another_legacy, "failed")
        finally:
            repo.close()
