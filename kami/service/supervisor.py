"""A single service supervisor, an OS-locked engine worker and persisted run ownership."""
from __future__ import annotations

import multiprocessing
import queue
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from kami.service.locks import FileLock
from kami.service.stream import Broker
from kami.service.worker import execute_worker
from kami.store.service import Conflict, ServiceRepository


class Supervisor:
    def __init__(self, db, artifacts, interval_s=0.25, history_size=256):
        if str(db) == ":memory:":
            raise ValueError("service cần SQLite file để worker truy cập cùng dữ liệu")
        if not 0 < interval_s <= 60:
            raise ValueError("interval_s phải trong (0, 60]")
        if type(history_size) is not int or history_size < 2:
            raise ValueError("history_size phải là số nguyên ≥ 2")
        self.db = str(Path(db).resolve())
        self.artifacts = str(Path(artifacts).resolve())
        self.interval_s = interval_s
        self.service_lock = FileLock(self.db + ".service.lock")
        self.execution_lock = self.db + ".execution.lock"
        self.broker = Broker(history_size)
        self.lock = threading.RLock()
        self.process = self.monitor = self.messages = self.lifeline = None
        self.run_id = self.owner = None
        self.closed = True

    @contextmanager
    def repository(self):
        repo = ServiceRepository.open(self.db, migrate_db=False)
        try:
            yield repo
        finally:
            repo.close()

    def open(self):
        self.service_lock.acquire()
        try:
            # Wait briefly for an orphan's watchdog. Never admit a new worker while the old lock is held.
            deadline = time.monotonic() + 5
            while True:
                try:
                    execution = FileLock(self.execution_lock).acquire()
                    break
                except RuntimeError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.05)
            try:
                repo = ServiceRepository.open(self.db)
                try:
                    repo.recover()
                finally:
                    repo.close()
            finally:
                execution.close()
            self.closed = False
            return self
        except BaseException:
            self.service_lock.close()
            raise

    def detail(self, run_id):
        with self.repository() as repo:
            return repo.detail(run_id)

    def start(self, run_id):
        # A terminal DB commit can precede worker process exit; wait for the short cleanup only.
        with self.lock:
            monitor, process, previous_id = self.monitor, self.process, self.run_id
        if process is not None and monitor is not None:
            state = self.detail(previous_id)
            if state["status"] != "running" or not process.is_alive():
                process.join(timeout=1)
                monitor.join(timeout=1)
        with self.lock:
            if self.closed:
                raise Conflict("service đã dừng")
            if self.process is not None:
                raise Conflict("đang có worker running hoặc đang dọn dẹp")
            owner = uuid.uuid4().hex
            with self.repository() as repo:
                repo.claim(run_id, owner)
            ctx = multiprocessing.get_context("spawn")
            receive, lifeline = ctx.Pipe(duplex=False)
            messages = ctx.Queue(maxsize=256)
            process = ctx.Process(target=execute_worker,
                                  args=(self.db, self.artifacts, run_id, owner, self.execution_lock,
                                        messages, receive, self.interval_s), daemon=True)
            self.run_id, self.owner = run_id, owner
            try:
                process.start()
            except BaseException as exc:
                receive.close()
                lifeline.close()
                messages.close()
                with self.repository() as repo:
                    repo.finish(run_id, owner, "failed", str(exc), "spawn_failed")
                raise Conflict("không khởi động được worker") from exc
            receive.close()
            self.process, self.messages, self.lifeline = process, messages, lifeline
            self.broker.publish(run_id, "progress", {"phase": "loading", "fraction": 0.0, "eta_s": None})
            self.monitor = threading.Thread(target=self._monitor, args=(process, messages, run_id, owner), daemon=True)
            self.monitor.start()
            return self.detail(run_id)

    def _monitor(self, process, messages, run_id, owner):
        try:
            with self.repository() as repo:
                while True:
                    try:
                        kind, data = messages.get(timeout=0.05)
                        if kind == "progress":
                            repo.progress(run_id, owner, data)
                        self.broker.publish(run_id, kind, data)
                    except queue.Empty:
                        if not process.is_alive():
                            break
                process.join()
                with self.lock:
                    repo.finish(run_id, owner, "failed", f"worker thoát với mã {process.exitcode}", "worker_exited")
                    state = repo.detail(run_id)
                    self.broker.publish(run_id, "terminal", {"run_id": run_id, "status": state["status"],
                                                            "error_code": state["error_code"]})
        except BaseException as exc:
            with self.lock:
                self._stop(process)
                with self.repository() as repo:
                    repo.finish(run_id, owner, "failed", str(exc), "monitor_failed")
        finally:
            # Execution lock is OS-released before clearing the local worker slot.
            with self.lock:
                if process.is_alive():
                    self._stop(process)
                if self.process is process:
                    self.lifeline.close()
                    self.process = self.messages = self.lifeline = None
                    self.run_id = self.owner = None
            messages.close()

    @staticmethod
    def _stop(process):
        if process.is_alive():
            process.terminate()
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)
        if process.is_alive():
            raise Conflict("worker chưa dừng; vẫn giữ slot thực thi")

    def cancel(self, run_id):
        with self.lock:
            with self.repository() as repo:
                repo.managed(run_id)
                status = repo.get_run(run_id)["status"]
                if status == "queued":
                    repo.cancel_queued(run_id)
                elif status == "running" and self.run_id == run_id and self.process is not None:
                    self._stop(self.process)
                    repo.finish(run_id, self.owner, "cancelled")
                else:
                    raise Conflict("run không còn queued/running")
                state = repo.detail(run_id)
                self.broker.publish(run_id, "terminal", {"run_id": run_id, "status": state["status"],
                                                        "error_code": state["error_code"]})
                return state

    def close(self):
        with self.lock:
            self.closed = True
            if self.process is not None:
                self._stop(self.process)
                with self.repository() as repo:
                    repo.finish(self.run_id, self.owner, "failed", "service shutdown", "interrupted")
        if self.monitor is not None:
            self.monitor.join(timeout=3)
            if self.monitor.is_alive():
                raise RuntimeError("monitor chưa dừng; không nhả khoá service")
        self.service_lock.close()
